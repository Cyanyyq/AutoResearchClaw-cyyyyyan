# Codex 生物医学基金选题适配改造交接说明

本文档记录本轮 Codex 对 AutoResearchClaw 的改造，供后续 Agent 快速判断：改了哪里、为什么改、后续如果出问题该怎么定位和继续修改。

## 改造目标

将 AutoResearchClaw 从默认的“算法/ML 论文自动生成”工作流，调整为更适合以下场景：

- 深圳市科技创新局 2026 年度基础研究专项自然科学基金计划面上项目
- 生物医学、流行病学、队列研究、UK Biobank、代谢组学、心肾代谢/糖尿病/心脑血管/肾病方向
- Stage 1-5 的选题推演、联网文献检索、文献筛选与证据提取

本轮重点解决三个问题：

- Stage 3 生成了较好的数据库检索词，但 Stage 4 读不到 `merged_queries` 等字段，导致好查询被丢弃。
- 中文生物医学课题 fallback 时被抽成少量英文 token，系统自动补 `benchmark`、`survey`、`deep learning`，检索跑偏到算法论文。
- Stage 5 原逻辑强制补齐 15 篇 shortlist，容易把低相关或跨领域论文补回来。

## 修改文件总览

### 核心逻辑

- `researchclaw/pipeline/stage_impls/_literature.py`
  - 新增生物医学/基金语境识别。
  - 新增稳定的生物医学默认查询生成。
  - 修复 Stage 3 search plan 查询字段读取。
  - 生物医学语境下禁用 benchmark/deep learning 式查询扩展。
  - Stage 5 增加领域信号排序，并取消生物医学语境下的强制补齐 15 篇。

- `researchclaw/literature/semantic_scholar.py`
  - 支持从环境变量读取 Semantic Scholar API key。
  - 调整有 key/无 key 的请求节流。
  - 429 时尊重 `Retry-After` 响应头。

- `researchclaw/pipeline/executor.py`
  - 将新增 helper 重新导出给既有测试入口使用。

### Prompt 与配置模板

- `researchclaw/prompts.py`
  - 内置默认 prompt 从算法 benchmark/SOTA 叙事扩展为队列、数据资源、终点、标志物、外部验证、效应量、公共卫生价值。

- `prompts.default.yaml`
  - 同步更新用户可复制修改的默认 prompt 模板，避免后续自定义 prompt 继续继承算法论文偏置。

### 测试

- `tests/test_rc_executor.py`
  - 新增对 `merged_queries` 读取、生物医学查询扩展、中文课题 fallback、生物医学语境识别的回归测试。

- `tests/test_rc_literature.py`
  - 新增 Semantic Scholar 环境变量 API key 和 `Retry-After` 的回归测试。

### 文档

- `docs/SZ_STIB_BIOMEDICAL_GRANT_ADAPTATION.md`
  - 面向项目使用者的改造说明。

- `docs/CODEX_BIOMEDICAL_ADAPTATION_HANDOFF.md`
  - 本文件，面向后续 Agent/维护者的交接说明。

## 关键实现细节

### 1. 生物医学/基金语境识别

位置：`researchclaw/pipeline/stage_impls/_literature.py`

新增：

- `_BIOMEDICAL_CONTEXT_MARKERS`
- `_is_biomedical_grant_context(topic, domains)`

识别依据包括：

- 中文：基金、标书、申报、队列、流行病、代谢组、心肾代谢、糖尿病、心血管、肾病、多病共存、深圳等。
- 英文：biomedical、clinical、epidemiology、cohort、PubMed、metabolomics、UK Biobank、NMR、CKM、CMM、multimorbidity 等。

后续如发现某个真实项目没有被识别为生物医学基金语境，优先在 `_BIOMEDICAL_CONTEXT_MARKERS` 中补关键词。

### 2. Stage 3 查询字段读取

位置：`_extract_queries_from_plan(plan)`

现在会读取：

- `search_strategies[*].queries`
- `search_phases[*].queries`
- `phases[*].queries`
- `queries`
- `search_queries`
- `database_queries`
- `merged_queries`
- `queries_by_source`
- `pubmed_queries`
- `openalex_queries`
- `semantic_scholar_queries`
- `scholar_queries`

如果后续 LLM 或 cc-glm 生成了新的字段名，应该优先扩展 `_extract_queries_from_plan()`，不要在 Stage 4 里另写一套解析逻辑。

### 3. 生物医学默认查询

位置：`_build_biomedical_default_search_queries(topic_text)`

当前默认查询包括：

- `UK Biobank NMR metabolomics`
- `cardiometabolic multimorbidity metabolomics`
- `cardiovascular kidney metabolic syndrome cohort`
- `CKM syndrome metabolomics cohort`
- `NMR metabolomics type 2 diabetes UK Biobank`
- `NMR metabolomics cardiovascular disease UK Biobank`
- `NMR metabolomics chronic kidney disease UK Biobank`
- `metabolomic signatures prospective cohort`
- `metabolomic risk score cardiometabolic`
- `Nightingale NMR metabolomics disease atlas`

注意：

- 这里是“兜底查询”，不是最终课题限定。
- 如果后续 SZ-STIB 课题发生明显变化，比如转向单细胞、蛋白组、深圳本地体检队列，应在这里补相应 query phrase。
- 不建议在这里加入过长 PubMed 布尔表达式，因为代码后续会对过长查询做缩短处理。

### 4. 生物医学查询扩展

位置：`_expand_search_queries(queries, topic, biomedical_context=False)`

原逻辑会添加：

- `survey`
- `benchmark`
- `comparison`

新逻辑：

- 非生物医学语境仍保留原算法论文扩展方式。
- 生物医学/基金语境只追加 `_build_biomedical_default_search_queries()`，不再自动加入 `benchmark`、`deep learning`。

如果后续发现算法论文场景受影响，应检查调用时 `biomedical_context` 是否误判为 `True`。

### 5. Stage 5 文献筛选

位置：`_execute_literature_screen()`

新增：

- `_BIOMEDICAL_HIGH_SIGNAL_PHRASES`
- `_score_candidate_for_topic()`
- 生物医学语境下按领域信号、引用数、年份排序。
- 如果高信号候选足够，先把低信号候选排除在 LLM token budget 之外。
- 生物医学语境下不再自动补齐 15 篇。

当前规则：

- 非生物医学语境：仍然尽量补到 15 篇，保持算法论文 related work 的原行为。
- 生物医学语境：`_MIN_SHORTLIST = 5`，且 LLM 返回少量严格 shortlist 时不补齐。

如果后续出现 shortlist 太少：

1. 先看 Stage 4 的 `candidates.jsonl` 是否检索不足。
2. 再看 Stage 3 的 `queries.json` 是否查询太窄。
3. 最后再考虑调低 Stage 5 的高信号阈值或增加默认查询。

不要直接恢复“强制补齐 15 篇”，否则会重新引入低相关论文。

### 6. Semantic Scholar 限流

位置：`researchclaw/literature/semantic_scholar.py`

新增行为：

- `search_semantic_scholar()` 和 `batch_fetch_papers()` 都会自动读取：
  - `SEMANTIC_SCHOLAR_API_KEY`
  - `S2_API_KEY`
- 有 key 时使用 `_AUTH_RATE_LIMIT_SEC = 1.1`。
- 无 key 时使用 `_RATE_LIMIT_SEC = 1.5`。
- 429 时读取 `Retry-After`，等待时间为 `max(Retry-After, exponential_backoff)`。

如果后续仍频繁 429：

- 确认 shell 中是否真的导出了 key：

```bash
echo "$SEMANTIC_SCHOLAR_API_KEY"
```

- 检查配置是否通过 `llm.s2_api_key` 传入。
- 减少 Stage 4 查询数或 `limit_per_query`。
- 保留 circuit breaker，不建议删除。

## Prompt 改造说明

### `topic_init`

从：

- benchmark
- SOTA
- leaderboard

改为兼容：

- benchmark
- dataset
- cohort
- registry
- data resource
- external validation
- calibration
- effect sizes
- public-health value

### `search_strategy`

新增硬约束：

- YAML 必须有 `search_strategies[*].queries`。
- 如果生成 `merged_queries` 或数据库专用查询，必须把最好的可执行查询复制进 `search_strategies[*].queries`。
- 生物医学/基金课题优先 PubMed/OpenAlex 友好英文查询。
- 不主动加 benchmark/SOTA/deep learning，除非课题明确需要。

### `literature_screen`

筛选标准从“methods, benchmarks, findings”扩展为：

- methods
- cohorts
- datasets
- endpoints
- biomarkers
- prediction metrics
- validation designs
- directly applicable findings

## 验证命令

定向测试：

```bash
uv run --extra dev pytest tests/test_rc_executor.py::TestExpandSearchQueries tests/test_rc_literature.py::TestSemanticScholar -q
```

预期：

```text
13 passed
```

语法检查：

```bash
.venv/bin/python3 -m compileall \
  researchclaw/pipeline/stage_impls/_literature.py \
  researchclaw/literature/semantic_scholar.py \
  researchclaw/prompts.py \
  researchclaw/pipeline/executor.py
```

diff 基础检查：

```bash
git diff --check -- \
  researchclaw/pipeline/stage_impls/_literature.py \
  researchclaw/literature/semantic_scholar.py \
  researchclaw/prompts.py \
  researchclaw/pipeline/executor.py \
  prompts.default.yaml \
  tests/test_rc_executor.py \
  tests/test_rc_literature.py
```

## 常见问题与排查

### Stage 3 的 `queries.json` 仍然很差

优先检查：

1. `stage-03/search_plan.yaml` 是否包含高质量查询。
2. 高质量查询是否落在 `_extract_queries_from_plan()` 支持的字段里。
3. 课题和 `research.domains` 是否能触发 `_is_biomedical_grant_context()`。
4. 是否被 `_shorten_query()` 缩得过短。

处理方式：

- 如果 `search_plan.yaml` 好但 `queries.json` 差，改 `_extract_queries_from_plan()`。
- 如果 `search_plan.yaml` 本身差，改 `search_strategy` prompt。
- 如果中文课题 fallback 差，改 `_build_biomedical_default_search_queries()`。

### Stage 4 检索结果不足

优先检查：

1. 是否打开联网搜索。
2. Semantic Scholar 是否 429。
3. OpenAlex/S2/arXiv 是否至少有一个来源成功。
4. `queries_used` 和 `year_min` 是否过窄。

处理方式：

- 有 key 但仍 429：降低查询数或增加请求间隔。
- 查询太窄：增加默认 query phrase。
- 年份太新：检查 `_extract_year_min_from_plan()` 或 search plan 的 `filters.min_year`。

### Stage 5 shortlist 太少

这是生物医学语境下的预期倾向：宁可少，也不要补低相关论文。

排查顺序：

1. `stage-04/candidates.jsonl` 是否有足够相关候选。
2. `topic_keywords` 是否能覆盖疾病、暴露、结局和数据资源。
3. `_BIOMEDICAL_HIGH_SIGNAL_PHRASES` 是否覆盖当前课题关键词。
4. LLM 的 `literature_screen` prompt 是否过严。

处理方式：

- 优先增强 Stage 3/4 查询。
- 其次扩充 `_BIOMEDICAL_HIGH_SIGNAL_PHRASES`。
- 最后再考虑把 `_MIN_SHORTLIST` 从 5 调到 8 或 10。

### 算法论文场景被误判为生物医学

排查：

- 查看 topic 和 domains 中是否包含 `clinical`、`cohort`、`benchmark` 之外的医学词。
- `_BIOMEDICAL_CONTEXT_MARKERS` 是否过宽。

处理方式：

- 收窄 marker。
- 或在配置中避免把非医学项目 domains 写成 `medical`、`clinical` 等。

## 后续维护建议

- 把 `research.domains` 明确写成 `epidemiology`、`biomedical`、`metabolomics`、`UK Biobank` 等，有助于稳定触发生物医学路径。
- 新增研究方向时，优先补默认查询和高信号短语，而不是修改 Stage 5 补齐逻辑。
- 不要把真实 UKB 个体数据、变量分布或敏感表格发送到联网搜索；检索词中出现变量名、疾病名、暴露名风险较低。
- 如果要继续比较 AutoResearchClaw 和 AutoProjectClaw，建议固定同一 topic、同一 prompt、同一输出目录结构，只比较 Stage 3-5 的 `queries.json`、`candidates.jsonl`、`shortlist.jsonl` 和最终 synthesis。
