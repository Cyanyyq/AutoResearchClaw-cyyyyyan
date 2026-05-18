"""Stages 3-6: Search strategy, literature collection, screening, and knowledge extraction."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from researchclaw.adapters import AdapterBundle
from researchclaw.config import RCConfig
from researchclaw.llm.client import LLMClient
from researchclaw.pipeline._helpers import (
    StageResult,
    _build_fallback_queries,
    _chat_with_prompt,
    _extract_topic_keywords,
    _extract_yaml_block,
    _get_evolution_overlay,
    _parse_jsonl_rows,
    _read_prior_artifact,
    _safe_filename,
    _safe_json_loads,
    _utcnow_iso,
    _write_jsonl,
)
from researchclaw.pipeline.stages import Stage, StageStatus
from researchclaw.prompts import PromptManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------

_SEARCH_STOP_WORDS = {
    "a", "an", "the", "of", "for", "in", "on", "and", "or", "with",
    "to", "by", "from", "its", "is", "are", "was", "be", "as", "at",
    "via", "using", "based", "study", "analysis", "empirical",
    "towards", "toward", "into", "exploring", "comparison", "tasks",
    "effectiveness", "investigation", "comprehensive", "novel",
    "challenge", "challenges", "gaps", "gap", "critical", "survey", "review",
    "ts", "py", "pdat", "all", "project", "research",
}

_BIOMEDICAL_CONTEXT_MARKERS = {
    "biomed", "biomedical", "medicine", "medical", "clinical", "epidemiology",
    "cohort", "pubmed", "metabolomics", "metabolomic", "diabetes",
    "cardiovascular", "kidney", "ckd", "ckm", "cmm", "cvd", "t2d",
    "multimorbidity", "biobank", "uk biobank", "ukb", "nmr",
    "队列", "流行病", "代谢组", "心肾代谢", "糖尿病", "心血管",
    "肾病", "多病共存", "人群",
}
_BIOMEDICAL_DEFAULT_QUERY_LIMIT = 8

_BIOMEDICAL_QUERY_PHRASES = (
    "UK Biobank NMR metabolomics",
    "cardiometabolic multimorbidity metabolomics",
    "cardiovascular kidney metabolic syndrome",
    "CKM syndrome metabolomics cohort",
    "NMR metabolomics type 2 diabetes",
    "NMR metabolomics cardiovascular disease",
    "NMR metabolomics chronic kidney disease",
    "metabolomic signatures prospective cohort",
    "metabolomic risk score cardiometabolic",
    "Nightingale NMR metabolomics disease atlas",
)

_BIOMEDICAL_HIGH_SIGNAL_PHRASES = (
    "uk biobank", "nightingale", "nmr", "metabolomics", "metabolomic",
    "cardiometabolic", "multimorbidity", "ckm", "cardiovascular-kidney",
    "cardiovascular kidney", "chronic kidney", "ckd", "type 2 diabetes",
    "diabetes", "cardiovascular disease", "coronary heart disease", "stroke",
    "prospective cohort", "risk prediction", "metabolic signature",
    "metabolomic signature", "glyca", "lipoprotein", "residual risk",
)


def _extract_search_terms(text: str) -> list[str]:
    """Extract ASCII search terms from *text* after removing common noise."""
    return [
        w for w in re.split(r"[^a-zA-Z0-9]+", text)
        if w.lower() not in _SEARCH_STOP_WORDS and len(w) > 1
    ]


def _is_biomedical_grant_context(
    topic: str, domains: tuple[str, ...] | list[str] = ()
) -> bool:
    """Return True for biomedical or epidemiology grant topics."""
    haystack = f"{topic} {' '.join(domains)}".lower()
    return any(
        _context_marker_matches(haystack, marker)
        for marker in _BIOMEDICAL_CONTEXT_MARKERS
    )


def _context_marker_matches(haystack: str, marker: str) -> bool:
    """Match short English markers as tokens while keeping Chinese substring matching."""
    marker = marker.lower()
    if re.fullmatch(r"[a-z0-9]+", marker):
        pattern = rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])"
        return re.search(pattern, haystack) is not None
    if re.fullmatch(r"[a-z0-9][a-z0-9 ]+[a-z0-9]", marker):
        pattern = re.escape(marker).replace(r"\ ", r"\s+")
        return (
            re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", haystack)
            is not None
        )
    return marker in haystack


def _add_unique_query(out: list[str], seen: set[str], query: str) -> None:
    query = re.sub(r"\s+", " ", query).strip()
    if not query:
        return
    key = query.lower()
    if key not in seen:
        seen.add(key)
        out.append(query)


def _collect_query_strings(value: Any) -> list[str]:
    """Collect strings from a query-specific YAML/JSON subtree."""
    queries: list[str] = []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        for item in value:
            queries.extend(_collect_query_strings(item))
        return queries
    if isinstance(value, dict):
        for item in value.values():
            queries.extend(_collect_query_strings(item))
    return queries


def _extract_queries_from_plan(plan: dict[str, Any]) -> list[str]:
    """Extract Stage 4 search queries from common plan schemas.

    Earlier versions only read ``search_strategies[*].queries`` and top-level
    ``queries``. Biomedical grant planning prompts often group high-quality
    database strings under ``merged_queries`` or ``*_queries``. This helper
    accepts both shapes so good PubMed/OpenAlex-style queries are not lost.
    """
    raw_queries: list[str] = []

    strategies = (
        plan.get("search_strategies")
        or plan.get("search_phases")
        or plan.get("phases")
        or []
    )
    if isinstance(strategies, list):
        for strat in strategies:
            if isinstance(strat, dict):
                raw_queries.extend(_collect_query_strings(strat.get("queries", [])))

    for key in (
        "queries",
        "search_queries",
        "database_queries",
        "merged_queries",
        "queries_by_source",
        "pubmed_queries",
        "openalex_queries",
        "semantic_scholar_queries",
        "scholar_queries",
    ):
        if key in plan:
            raw_queries.extend(_collect_query_strings(plan.get(key)))

    seen: set[str] = set()
    unique: list[str] = []
    for query in raw_queries:
        _add_unique_query(unique, seen, query)
    return unique


def _extract_year_min_from_plan(plan: dict[str, Any], *, default: int = 2020) -> int:
    """Extract a lower publication year from plan filters/search scope."""
    filters = plan.get("filters", {})
    if isinstance(filters, dict) and filters.get("min_year"):
        try:
            return int(filters["min_year"])
        except (ValueError, TypeError):
            pass
    scope = plan.get("search_scope", {})
    if isinstance(scope, dict) and scope.get("years"):
        years = re.findall(r"\d{4}", str(scope["years"]))
        if years:
            return min(int(y) for y in years)
    return default


def _coerce_biomedical_query_limit(limit: int | None) -> int:
    if limit is None:
        return _BIOMEDICAL_DEFAULT_QUERY_LIMIT
    try:
        return max(1, int(limit))
    except (TypeError, ValueError):
        return _BIOMEDICAL_DEFAULT_QUERY_LIMIT


def _build_biomedical_default_search_queries(
    topic_text: str,
    *,
    limit: int | None = None,
) -> list[str]:
    """Generate stable biomedical queries from Chinese/English grant topics."""
    query_limit = _coerce_biomedical_query_limit(limit)
    lower = topic_text.lower()
    queries: list[str] = []
    seen: set[str] = set()

    def has_any(*needles: str) -> bool:
        return any(n.lower() in lower for n in needles)

    if has_any("uk biobank", "ukb") and has_any("nmr", "metabolomics", "代谢组"):
        _add_unique_query(queries, seen, "UK Biobank NMR metabolomics")
    if has_any("多病共存", "multimorbidity", "cmm"):
        _add_unique_query(queries, seen, "cardiometabolic multimorbidity metabolomics")
        _add_unique_query(
            queries,
            seen,
            "cardiometabolic multimorbidity risk prediction cohort",
        )
    if has_any("ckm", "心肾代谢", "cardiovascular-kidney-metabolic"):
        _add_unique_query(queries, seen, "cardiovascular kidney metabolic syndrome cohort")
        _add_unique_query(queries, seen, "CKM syndrome metabolomics cohort")
    if has_any("糖尿病", "diabetes", "t2d"):
        _add_unique_query(queries, seen, "NMR metabolomics type 2 diabetes UK Biobank")
    if has_any("心血管", "cardiovascular", "stroke", "coronary"):
        _add_unique_query(queries, seen, "NMR metabolomics cardiovascular disease UK Biobank")
    if has_any("肾", "kidney", "ckd"):
        _add_unique_query(queries, seen, "NMR metabolomics chronic kidney disease UK Biobank")

    for query in _BIOMEDICAL_QUERY_PHRASES:
        if len(queries) >= query_limit:
            break
        _add_unique_query(queries, seen, query)
    return queries[:query_limit]


def _score_candidate_for_topic(
    row: dict[str, Any],
    topic_keywords: list[str],
    *,
    biomedical_context: bool,
) -> float:
    """Cheap relevance score used before token-budget truncation."""
    title = str(row.get("title", "")).lower()
    abstract = str(row.get("abstract", "")).lower()
    venue = str(row.get("venue", "")).lower()
    text_blob = f"{title} {abstract} {venue}"
    score = float(row.get("keyword_overlap", 0) or 0)
    score += 0.25 * sum(1 for kw in topic_keywords if kw in text_blob)
    if biomedical_context:
        for phrase in _BIOMEDICAL_HIGH_SIGNAL_PHRASES:
            if phrase in title:
                score += 3.0
            elif phrase in abstract:
                score += 1.0
    return score


def _passes_topic_prefilter(
    *,
    overlap: int,
    relevance_score: float,
    biomedical_context: bool,
) -> bool:
    if biomedical_context:
        return overlap >= 2 or relevance_score >= 3.0
    return overlap >= 1


def _expand_search_queries(
    queries: list[str],
    topic: str,
    *,
    biomedical_context: bool = False,
    biomedical_query_limit: int | None = None,
) -> list[str]:
    """Expand search queries for broader literature coverage.

    Generates additional queries by extracting key phrases from the topic
    and creating focused sub-queries. This ensures we find papers even when
    the original queries are too narrow or specific for arXiv.
    """
    expanded = list(queries)  # keep originals
    seen = {q.lower().strip() for q in queries}

    if biomedical_context:
        for query in _build_biomedical_default_search_queries(
            topic,
            limit=biomedical_query_limit,
        ):
            _add_unique_query(expanded, seen, query)
        return expanded

    # Extract key phrases from topic by splitting on common delimiters
    # e.g. "Comparing A, B, and C on X with Y" → ["A", "B", "C", "X", "Y"]
    topic_words = topic.split()

    # Generate shorter, broader queries from the topic
    if len(topic_words) > 5:
        # First 5 words as a broader query
        broad = " ".join(topic_words[:5])
        if broad.lower().strip() not in seen:
            expanded.append(broad)
            seen.add(broad.lower().strip())

        # Last 5 words as another perspective
        tail = " ".join(topic_words[-5:])
        if tail.lower().strip() not in seen:
            expanded.append(tail)
            seen.add(tail.lower().strip())

    # Add "survey" and "benchmark" variants of the topic
    for suffix in ("survey", "benchmark", "comparison"):
        # Take first 4 content words + suffix
        short_topic = " ".join(topic_words[:4])
        variant = f"{short_topic} {suffix}"
        if variant.lower().strip() not in seen:
            expanded.append(variant)
            seen.add(variant.lower().strip())

    return expanded


# ---------------------------------------------------------------------------
# Stage executors
# ---------------------------------------------------------------------------


def _execute_search_strategy(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    problem_tree = _read_prior_artifact(run_dir, "problem_tree.md") or ""
    topic = config.research.topic
    plan: dict[str, Any] | None = None
    sources: list[dict[str, Any]] | None = None
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "search_strategy")
        sp = _pm.for_stage("search_strategy", evolution_overlay=_overlay, topic=topic, problem_tree=problem_tree)
        resp = _chat_with_prompt(
            llm,
            sp.system,
            sp.user,
            json_mode=sp.json_mode,
            max_tokens=sp.max_tokens,
        )
        payload = _safe_json_loads(resp.content, {})
        if isinstance(payload, dict):
            yaml_text = str(payload.get("search_plan_yaml", "")).strip()
            if yaml_text:
                try:
                    parsed = yaml.safe_load(_extract_yaml_block(yaml_text))
                except yaml.YAMLError:
                    parsed = None
                if isinstance(parsed, dict):
                    plan = parsed
            src = payload.get("sources", [])
            if isinstance(src, list):
                sources = [item for item in src if isinstance(item, dict)]
    if plan is None:
        # Build smart fallback queries by extracting key terms from topic
        # instead of using the raw (often very long) topic string.
        _fallback_queries = _build_fallback_queries(topic)
        plan = {
            "topic": topic,
            "generated": _utcnow_iso(),
            "search_strategies": [
                {
                    "name": "keyword_core",
                    "queries": _fallback_queries[:5],
                    "sources": ["arxiv", "semantic_scholar", "openreview"],
                    "max_results_per_query": 60,
                },
                {
                    "name": "backward_forward_citation",
                    "queries": _fallback_queries[5:10] or _fallback_queries[:3],
                    "sources": ["semantic_scholar", "google_scholar"],
                    "depth": 1,
                },
            ],
            "filters": {
                "min_year": 2020,
                "language": ["en"],
                "peer_review_preferred": True,
            },
            "deduplication": {"method": "title_doi_hash", "fuzzy_threshold": 0.9},
        }
    if not sources:
        sources = [
            {
                "id": "arxiv",
                "name": "arXiv",
                "type": "api",
                "url": "https://export.arxiv.org/api/query",
                "status": "available",
                "query": topic,
                "verified_at": _utcnow_iso(),
            },
            {
                "id": "semantic_scholar",
                "name": "Semantic Scholar",
                "type": "api",
                "url": "https://api.semanticscholar.org/graph/v1/paper/search",
                "status": "available",
                "query": topic,
                "verified_at": _utcnow_iso(),
            },
        ]
    if config.openclaw_bridge.use_web_fetch:
        for src in sources:
            try:
                response = adapters.web_fetch.fetch(str(src.get("url", "")))
                src["status"] = (
                    "verified"
                    if response.status_code in (200, 301, 302, 405)
                    else "unreachable"
                )
                src["http_status"] = response.status_code
            except Exception:  # noqa: BLE001
                src["status"] = "unknown"
    (stage_dir / "search_plan.yaml").write_text(
        yaml.dump(plan, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    (stage_dir / "sources.json").write_text(
        json.dumps(
            {"sources": sources, "count": len(sources), "generated": _utcnow_iso()},
            indent=2,
        ),
        encoding="utf-8",
    )

    # F1.5: Extract queries from plan for Stage 4 real literature search
    queries_list: list[str] = []
    biomedical_context = _is_biomedical_grant_context(
        topic, config.research.domains
    )
    biomedical_query_limit = config.research.biomedical_query_limit
    year_min = 2023 if biomedical_context else 2020
    if isinstance(plan, dict):
        queries_list = _extract_queries_from_plan(plan)
        year_min = _extract_year_min_from_plan(plan, default=year_min)

    # --- Sanitize queries: shorten overly long queries ---
    # LLMs often produce the full topic title as a query, which is too long for
    # arXiv and Semantic Scholar (they work best with 3-8 keyword queries).
    _MAX_QUERY_LEN = 60  # characters — beyond this, shorten to keywords
    _SEARCH_SUFFIXES = ["benchmark", "survey", "seminal", "state of the art"]

    def _shorten_query(q: str, max_kw: int = 6) -> str:
        """Shorten a query to *max_kw* keywords, preserving any trailing suffix."""
        q_stripped = q.strip()
        # Check if query ends with a known search suffix
        suffix = ""
        q_core = q_stripped
        for sfx in _SEARCH_SUFFIXES:
            if q_stripped.lower().endswith(sfx):
                suffix = sfx
                q_core = q_stripped[: -len(sfx)].strip()
                break
        # Extract keywords from the core part
        kws = _extract_search_terms(q_core)
        shortened = " ".join(kws[:max_kw])
        if suffix:
            shortened = f"{shortened} {suffix}"
        return shortened

    if queries_list:
        sanitized: list[str] = []
        for q in queries_list:
            if len(q) > _MAX_QUERY_LEN:
                shortened = _shorten_query(q)
                if shortened.strip():
                    sanitized.append(shortened)
            else:
                sanitized.append(q)
        queries_list = sanitized

    def _build_default_search_queries(topic_text: str) -> list[str]:
        """Generate concept-style search queries from the topic instead of copying the title."""
        if biomedical_context:
            return _build_biomedical_default_search_queries(
                topic_text,
                limit=biomedical_query_limit,
            )
        _words = _extract_search_terms(topic_text)
        if not _words:
            return [topic_text[:60]]
        kw_primary = " ".join(_words[:6])
        kw_short = " ".join(_words[:4])
        kw_alt = " ".join(_words[1:5]) if len(_words) > 4 else kw_short
        return [
            kw_primary,
            f"{kw_short} benchmark",
            f"{kw_short} survey",
            kw_alt,
            f"{kw_short} recent advances",
        ]

    if not queries_list:
        queries_list = _build_default_search_queries(topic)

    # Ensure minimum query diversity — if dedup leaves too few, add variants
    _all_kw = _extract_search_terms(topic)
    _seen_q: set[str] = set()
    unique_queries: list[str] = []
    for q in queries_list:
        q_lower = q.strip().lower()
        if q_lower and q_lower not in _seen_q:
            _seen_q.add(q_lower)
            unique_queries.append(q.strip())
    # If we have fewer than 5 unique queries, generate supplemental keyword variants
    if len(unique_queries) < 5 and (biomedical_context or len(_all_kw) >= 3):
        if biomedical_context:
            supplements = _build_biomedical_default_search_queries(
                topic,
                limit=biomedical_query_limit,
            )
        else:
            supplements = [
                " ".join(_all_kw[:4]) + " survey",
                " ".join(_all_kw[:4]) + " benchmark",
                " ".join(_all_kw[1:5]),  # shifted window for diversity
                " ".join(_all_kw[:3]) + " comparison",
                " ".join(_all_kw[:3]) + " deep learning",
                " ".join(_all_kw[2:6]),  # another shifted window
            ]
        for s in supplements:
            s_lower = s.strip().lower()
            if s_lower not in _seen_q:
                _seen_q.add(s_lower)
                unique_queries.append(s.strip())
            if len(unique_queries) >= biomedical_query_limit:
                break
    queries_list = unique_queries
    (stage_dir / "queries.json").write_text(
        json.dumps({"queries": queries_list, "year_min": year_min}, indent=2),
        encoding="utf-8",
    )
    return StageResult(
        stage=Stage.SEARCH_STRATEGY,
        status=StageStatus.DONE,
        artifacts=("search_plan.yaml", "sources.json", "queries.json"),
        evidence_refs=(
            "stage-03/search_plan.yaml",
            "stage-03/sources.json",
            "stage-03/queries.json",
        ),
    )


def _execute_literature_collect(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    """Stage 4: Collect literature — prefer real APIs, fallback to LLM."""
    topic = config.research.topic

    # Read queries.json from Stage 3 (F1.5 output)
    queries_text = _read_prior_artifact(run_dir, "queries.json")
    queries_data = _safe_json_loads(queries_text or "{}", {})
    queries: list[str] = queries_data.get("queries", [topic])
    year_min: int = queries_data.get("year_min", 2020)

    # --- Try real API search first ---
    candidates: list[dict[str, Any]] = []
    bibtex_entries: list[str] = []
    real_search_succeeded = False

    try:
        from researchclaw.literature.search import (
            search_papers_multi_query,
            papers_to_bibtex,
        )

        # Expand queries for broader coverage. Biomedical/grant topics use
        # cohort and disease-oriented variants instead of benchmark/survey noise.
        expanded_queries = _expand_search_queries(
            queries,
            config.research.topic,
            biomedical_context=_is_biomedical_grant_context(
                config.research.topic, config.research.domains
            ),
            biomedical_query_limit=config.research.biomedical_query_limit,
        )
        logger.info(
            "[literature] Searching %d queries (expanded from %d) "
            "across OpenAlex → S2 → arXiv…",
            len(expanded_queries),
            len(queries),
        )
        papers = search_papers_multi_query(
            expanded_queries,
            limit_per_query=40,
            year_min=year_min,
            s2_api_key=config.llm.s2_api_key,
        )
        if papers:
            real_search_succeeded = True
            # Count by source
            src_counts: dict[str, int] = {}
            for p in papers:
                src_counts[p.source] = src_counts.get(p.source, 0) + 1
                d = p.to_dict()
                d["collected_at"] = _utcnow_iso()
                candidates.append(d)
                bibtex_entries.append(p.to_bibtex())
            src_str = ", ".join(f"{s}: {n}" for s, n in src_counts.items())
            logger.info(
                "[literature] Found %d papers (%s)", len(papers), src_str
            )
    except Exception:  # noqa: BLE001
        logger.warning(
            "[rate-limit] Literature search failed — falling back to LLM",
            exc_info=True,
        )

    # --- Inject foundational/seminal papers ---
    try:
        from researchclaw.data import load_seminal_papers
        seminal = load_seminal_papers(topic)
        if seminal:
            _existing_titles = {c.get("title", "").lower() for c in candidates}
            _injected = 0
            for sp in seminal:
                if sp.get("title", "").lower() not in _existing_titles:
                    candidates.append({
                        "id": f"seminal-{sp.get('cite_key', '')}",
                        "title": sp.get("title", ""),
                        "source": "seminal_library",
                        "url": "",
                        "year": sp.get("year", 2020),
                        "abstract": f"Foundational paper on {', '.join(sp.get('keywords', [])[:3])}.",
                        "authors": [{"name": sp.get("authors", "")}],
                        "cite_key": sp.get("cite_key", ""),
                        "venue": sp.get("venue", ""),
                        "collected_at": _utcnow_iso(),
                    })
                    _injected += 1
            if _injected:
                logger.info("Stage 4: Injected %d seminal papers from seed library", _injected)
    except Exception:  # noqa: BLE001
        logger.debug("Seminal paper injection skipped", exc_info=True)

    # --- Fallback: LLM-generated candidates ---
    if not candidates and llm is not None:
        plan_text = _read_prior_artifact(run_dir, "search_plan.yaml") or ""
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "literature_collect")
        sp = _pm.for_stage("literature_collect", evolution_overlay=_overlay, topic=topic, plan_text=plan_text)
        resp = _chat_with_prompt(
            llm,
            sp.system,
            sp.user,
            json_mode=sp.json_mode,
            max_tokens=sp.max_tokens,
        )
        payload = _safe_json_loads(resp.content, {})
        if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
            candidates = [row for row in payload["candidates"] if isinstance(row, dict)]

    # --- Web search augmentation (Tavily/DDG + Google Scholar + Crawl4AI) ---
    web_context_parts: list[str] = []
    if config.web_search.enabled:
        try:
            from researchclaw.web.agent import WebSearchAgent
            import os

            tavily_key = config.web_search.tavily_api_key or os.environ.get(
                config.web_search.tavily_api_key_env, ""
            )
            web_agent = WebSearchAgent(
                tavily_api_key=tavily_key,
                enable_scholar=config.web_search.enable_scholar,
                enable_crawling=config.web_search.enable_crawling,
                enable_pdf=config.web_search.enable_pdf_extraction,
                max_web_results=config.web_search.max_web_results,
                max_scholar_results=config.web_search.max_scholar_results,
                max_crawl_urls=config.web_search.max_crawl_urls,
            )
            web_result = web_agent.search_and_extract(
                topic, search_queries=queries,
            )

            # Convert Google Scholar papers into candidates
            for sp in web_result.scholar_papers:
                _existing_titles = {
                    str(c.get("title", "")).lower().strip() for c in candidates
                }
                if sp.title.lower().strip() not in _existing_titles:
                    lit_paper = sp.to_literature_paper()
                    d = lit_paper.to_dict()
                    d["collected_at"] = _utcnow_iso()
                    candidates.append(d)
                    bibtex_entries.append(lit_paper.to_bibtex())

            # Save web search context for downstream stages
            web_context = web_result.to_context_string(max_length=20_000)
            if web_context.strip():
                (stage_dir / "web_context.md").write_text(
                    web_context, encoding="utf-8"
                )
                web_context_parts.append(web_context)

            # Save full web search metadata
            (stage_dir / "web_search_result.json").write_text(
                json.dumps(web_result.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )

            logger.info(
                "[web-search] Added %d scholar papers, %d web results, %d crawled pages",
                len(web_result.scholar_papers),
                len(web_result.web_results),
                len(web_result.crawled_pages),
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "[web-search] Web search augmentation failed — continuing with academic APIs only",
                exc_info=True,
            )

    # --- Ultimate fallback: placeholder data ---
    # BUG-L2: Do NOT overwrite real_search_succeeded here — it was already
    # set correctly in the search block above. Overwriting would mislabel
    # LLM-hallucinated or seminal papers as "real search" results.
    if not candidates:
        logger.warning("Stage 4: All literature searches failed — using placeholder papers")
        candidates = [
            {
                "id": f"candidate-{idx + 1}",
                "title": f"[Placeholder] Study {idx + 1} on {topic}",
                "source": "arxiv" if idx % 2 == 0 else "semantic_scholar",
                "url": f"https://example.org/{_safe_filename(topic.lower())}/{idx + 1}",
                "year": 2024,
                "abstract": f"This candidate investigates {topic} and reports preliminary findings.",
                "collected_at": _utcnow_iso(),
                "is_placeholder": True,
            }
            for idx in range(max(20, config.research.daily_paper_count or 20))
        ]

    # Write candidates
    out = stage_dir / "candidates.jsonl"
    _write_jsonl(out, candidates)

    # BUG-50 fix: Generate BibTeX from candidates when real search failed
    # (LLM/placeholder fallback paths don't populate bibtex_entries)
    if not bibtex_entries and candidates:
        for c in candidates:
            if c.get("is_placeholder"):
                continue
            _ck = c.get("cite_key", "")
            if not _ck:
                # Derive cite_key from first author surname + year
                _authors = c.get("authors", [])
                _surname = "unknown"
                if isinstance(_authors, list) and _authors:
                    _a0 = _authors[0] if isinstance(_authors[0], str) else (_authors[0].get("name", "") if isinstance(_authors[0], dict) else "")
                    _surname = _a0.split()[-1].lower() if _a0.strip() else "unknown"
                _yr = c.get("year", 2024)
                _title_word = "".join(
                    w[0] for w in str(c.get("title", "study")).split()[:3]
                ).lower()
                _ck = f"{_surname}{_yr}{_title_word}"
            _title = c.get("title", "Untitled")
            _year = c.get("year", 2024)
            _author_str = ""
            _raw_authors = c.get("authors", [])
            if isinstance(_raw_authors, list):
                _names = []
                for _a in _raw_authors:
                    if isinstance(_a, str):
                        _names.append(_a)
                    elif isinstance(_a, dict):
                        _names.append(_a.get("name", ""))
                _author_str = " and ".join(n for n in _names if n)
            bibtex_entries.append(
                f"@article{{{_ck},\n"
                f"  title={{{_title}}},\n"
                f"  author={{{_author_str or 'Unknown'}}},\n"
                f"  year={{{_year}}},\n"
                f"  url={{{c.get('url', '')}}},\n"
                f"}}"
            )
        logger.info(
            "Stage 4: Generated %d BibTeX entries from candidates (fallback)",
            len(bibtex_entries),
        )

    # Write references.bib (F2.4)
    artifacts = ["candidates.jsonl"]
    if web_context_parts:
        artifacts.append("web_context.md")
    if (stage_dir / "web_search_result.json").exists():
        artifacts.append("web_search_result.json")
    if bibtex_entries:
        bib_content = "\n\n".join(bibtex_entries) + "\n"
        (stage_dir / "references.bib").write_text(bib_content, encoding="utf-8")
        artifacts.append("references.bib")
        logger.info(
            "Stage 4: Wrote %d BibTeX entries to references.bib", len(bibtex_entries)
        )

    # Write search metadata
    (stage_dir / "search_meta.json").write_text(
        json.dumps(
            {
                "real_search": real_search_succeeded,
                "queries_used": queries,
                "year_min": year_min,
                "total_candidates": len(candidates),
                "bibtex_entries": len(bibtex_entries),
                "ts": _utcnow_iso(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    artifacts.append("search_meta.json")

    return StageResult(
        stage=Stage.LITERATURE_COLLECT,
        status=StageStatus.DONE,
        artifacts=tuple(artifacts),
        evidence_refs=tuple(f"stage-04/{a}" for a in artifacts),
    )


_MAX_ABSTRACT_LEN = 800  # Truncate long abstracts to reduce token usage
_MAX_CANDIDATES_CHARS = 30_000  # Cap total candidates text sent to LLM


def _execute_literature_screen(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    candidates_text = _read_prior_artifact(run_dir, "candidates.jsonl") or ""

    # --- P1-1: keyword relevance pre-filter ---
    # Before LLM screening, drop papers whose title+abstract share no keywords
    # with the research topic.  This catches cross-domain noise cheaply.
    topic_keywords = _extract_topic_keywords(
        config.research.topic, config.research.domains
    )
    biomedical_context = _is_biomedical_grant_context(
        config.research.topic, config.research.domains
    )
    filtered_rows: list[dict[str, Any]] = []
    dropped_count = 0
    for raw_line in candidates_text.strip().splitlines():
        row = _safe_json_loads(raw_line, {})
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "")).lower()
        abstract = str(row.get("abstract", "")).lower()
        text_blob = f"{title} {abstract}"
        overlap = sum(1 for kw in topic_keywords if kw in text_blob)
        relevance_score = _score_candidate_for_topic(
            row,
            topic_keywords,
            biomedical_context=biomedical_context,
        )
        # T2.2: Generic workflows keep the recall-oriented >=1 keyword guard.
        # Biomedical grant workflows additionally require either two topic hits
        # or a high-signal biomedical phrase so one generic token cannot crowd
        # out UKB/NMR/CKM/CMM papers before LLM screening.
        if _passes_topic_prefilter(
            overlap=overlap,
            relevance_score=relevance_score,
            biomedical_context=biomedical_context,
        ):
            row["keyword_overlap"] = overlap
            row["_topic_relevance_score"] = relevance_score
            filtered_rows.append(row)
        else:
            dropped_count += 1
    # If pre-filter dropped everything, fall back to original (safety valve)
    if not filtered_rows:
        filtered_rows = _parse_jsonl_rows(candidates_text)
        for row in filtered_rows:
            row["_topic_relevance_score"] = _score_candidate_for_topic(
                row,
                topic_keywords,
                biomedical_context=biomedical_context,
            )
    if biomedical_context and filtered_rows:
        # OpenAlex returns high-citation general medical reviews first. Rank by
        # domain signal before token truncation so LLM screening sees topical
        # UKB/NMR/CKM/CMM papers instead of broad off-topic reviews.
        filtered_rows.sort(
            key=lambda r: (
                float(r.get("_topic_relevance_score", 0) or 0),
                int(r.get("citation_count", 0) or 0),
                int(r.get("year", 0) or 0),
            ),
            reverse=True,
        )
        high_signal = [
            r for r in filtered_rows
            if float(r.get("_topic_relevance_score", 0) or 0) >= 3.0
        ]
        if len(high_signal) >= 10:
            filtered_rows = high_signal
    # Truncate abstracts and strip authors to reduce token usage
    for row in filtered_rows:
        abstract = row.get("abstract", "")
        if isinstance(abstract, str) and len(abstract) > _MAX_ABSTRACT_LEN:
            row["abstract"] = abstract[:_MAX_ABSTRACT_LEN] + "..."
        # Strip authors list — not needed for screening and inflates tokens
        row.pop("authors", None)

    # Rebuild candidates_text from filtered rows
    candidates_text = "\n".join(
        json.dumps(r, ensure_ascii=False) for r in filtered_rows
    )
    # Cap total candidates text size to avoid blowing token budget
    if len(candidates_text) > _MAX_CANDIDATES_CHARS:
        # Truncate at newline boundary to avoid cutting mid-JSON-line
        candidates_text = candidates_text[:_MAX_CANDIDATES_CHARS].rsplit("\n", 1)[0]
        logger.info(
            "Candidates text truncated to %d chars for screening",
            len(candidates_text),
        )
    logger.info(
        "Domain pre-filter: kept %d, dropped %d (keywords: %s)",
        len(filtered_rows),
        dropped_count,
        topic_keywords[:8],
    )

    shortlist: list[dict[str, Any]] = []
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "literature_screen")
        sp = _pm.for_stage(
            "literature_screen",
            evolution_overlay=_overlay,
            topic=config.research.topic,
            domains=", ".join(config.research.domains)
            if config.research.domains
            else "general",
            quality_threshold=config.research.quality_threshold,
            candidates_text=candidates_text,
        )
        resp = _chat_with_prompt(
            llm,
            sp.system,
            sp.user,
            json_mode=sp.json_mode,
            max_tokens=sp.max_tokens,
        )
        payload = _safe_json_loads(resp.content, {})
        if isinstance(payload, dict) and isinstance(payload.get("shortlist"), list):
            shortlist = [row for row in payload["shortlist"] if isinstance(row, dict)]
    # T2.2: Ensure minimum shortlist size for algorithm-paper workflows.
    # Biomedical grant workflows prefer strict relevance over padding with
    # generic reviews, so they do not auto-supplement a partial LLM shortlist.
    _MIN_SHORTLIST = 5 if biomedical_context else 15
    if not shortlist:
        rows = (
            filtered_rows[:_MIN_SHORTLIST]
            if filtered_rows
            else _parse_jsonl_rows(candidates_text)[:_MIN_SHORTLIST]
        )
        for idx, item in enumerate(rows):
            item["relevance_score"] = round(0.75 - idx * 0.02, 3)
            item["quality_score"] = round(0.72 - idx * 0.015, 3)
            item["keep_reason"] = "Template screened entry"
            shortlist.append(item)
    elif len(shortlist) < _MIN_SHORTLIST and not biomedical_context:
        # T2.2: LLM returned too few — supplement from filtered candidates
        existing_titles = {
            str(s.get("title", "")).lower().strip() for s in shortlist
        }
        for row in filtered_rows:
            if len(shortlist) >= _MIN_SHORTLIST:
                break
            title_lower = str(row.get("title", "")).lower().strip()
            if title_lower and title_lower not in existing_titles:
                row.setdefault("relevance_score", 0.5)
                row.setdefault("quality_score", 0.5)
                row.setdefault("keep_reason", "Supplemented to meet minimum shortlist")
                shortlist.append(row)
                existing_titles.add(title_lower)
        logger.info(
            "Stage 5: Supplemented shortlist to %d papers (minimum: %d)",
            len(shortlist), _MIN_SHORTLIST,
        )
    elif biomedical_context:
        logger.info(
            "Stage 5: Biomedical/grant context detected; keeping %d strictly "
            "screened papers without padding",
            len(shortlist),
        )
    for row in shortlist:
        row.pop("_topic_relevance_score", None)
    out = stage_dir / "shortlist.jsonl"
    _write_jsonl(out, shortlist)
    return StageResult(
        stage=Stage.LITERATURE_SCREEN,
        status=StageStatus.DONE,
        artifacts=("shortlist.jsonl",),
        evidence_refs=("stage-05/shortlist.jsonl",),
    )


def _execute_knowledge_extract(
    stage_dir: Path,
    run_dir: Path,
    config: RCConfig,
    adapters: AdapterBundle,
    *,
    llm: LLMClient | None = None,
    prompts: PromptManager | None = None,
) -> StageResult:
    shortlist = _read_prior_artifact(run_dir, "shortlist.jsonl") or ""

    # Inject web context from Stage 4 if available
    web_context = _read_prior_artifact(run_dir, "web_context.md") or ""
    if web_context:
        shortlist = shortlist + "\n\n--- Web Search Context ---\n" + web_context[:10_000]

    cards_dir = stage_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    cards: list[dict[str, Any]] = []
    if llm is not None:
        _pm = prompts or PromptManager()
        _overlay = _get_evolution_overlay(run_dir, "knowledge_extract")
        sp = _pm.for_stage("knowledge_extract", evolution_overlay=_overlay, shortlist=shortlist)
        resp = _chat_with_prompt(
            llm,
            sp.system,
            sp.user,
            json_mode=sp.json_mode,
            max_tokens=sp.max_tokens,
        )
        payload = _safe_json_loads(resp.content, {})
        if isinstance(payload, dict) and isinstance(payload.get("cards"), list):
            cards = [item for item in payload["cards"] if isinstance(item, dict)]
    if not cards:
        rows = _parse_jsonl_rows(shortlist)
        for idx, paper in enumerate(rows[:6]):
            title = str(paper.get("title", f"Paper {idx + 1}"))
            cards.append(
                {
                    "card_id": f"card-{idx + 1}",
                    "title": title,
                    "problem": f"How to improve {config.research.topic}",
                    "method": "Template method summary",
                    "data": "Template dataset",
                    "metrics": "Template metric",
                    "findings": "Template key finding",
                    "limitations": "Template limitation",
                    "citation": str(paper.get("url", "")),
                    "cite_key": str(paper.get("cite_key", "")),
                }
            )
    for idx, card in enumerate(cards):
        card_id = _safe_filename(str(card.get("card_id", f"card-{idx + 1}")))
        parts = [f"# {card.get('title', card_id)}", ""]
        for key in (
            "cite_key",
            "problem",
            "method",
            "data",
            "metrics",
            "findings",
            "limitations",
            "citation",
        ):
            parts.append(f"## {key.title()}")
            parts.append(str(card.get(key, "")))
            parts.append("")
        (cards_dir / f"{card_id}.md").write_text("\n".join(parts), encoding="utf-8")
    return StageResult(
        stage=Stage.KNOWLEDGE_EXTRACT,
        status=StageStatus.DONE,
        artifacts=("cards/",),
        evidence_refs=("stage-06/cards/",),
    )
