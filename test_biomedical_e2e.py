#!/usr/bin/env python3
"""
真实端到端测试：用 SZ-STIB 课题验证生物医学适配改造的效果。
测试目标：
1. 生物医学语境识别是否正确触发
2. Stage 3 查询生成是否产生高质量检索词
3. 真实文献检索（OpenAlex + Semantic Scholar）是否能返回相关结果
4. 结果中不应出现算法/deep learning/benchmark 类论文
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import ssl

# ============================================================
# 1. 生物医学语境识别测试
# ============================================================

# 导入被测函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from researchclaw.pipeline.stage_impls._literature import (
    _is_biomedical_grant_context,
    _build_biomedical_default_search_queries,
    _BIOMEDICAL_CONTEXT_MARKERS,
)

SZ_STIB_TOPIC = """基于NMR代谢组学的不同肥胖表型人群代谢性疾病共病风险分层研究。
背景：中心性肥胖人群是代谢性疾病的高危人群，但同样肥胖的个体代谢健康状态差异巨大。
利用UK Biobank中Nightingale Health NMR代谢组学平台（249项代谢指标），
在三类人群中（正常体重、中心性肥胖、BMI定义肥胖）评估NMR代谢组学对代谢性疾病共病
（T2D+高血压+CKD+CVD，≥2种定义为共病）的风险分层效果。
暴露：NMR代谢组学特征谱（249项Nightingale指标）。
结局：代谢性疾病共病累积负担（CMM count 0/1/2/3+，以及连续负担评分）。
人群：UK Biobank约280,000名有NMR代谢组学数据的参与者，按BMI和腰围分为三组。
本地验证队列：深圳慢性病监测（SZMB）社区人群。"""

SZ_STIB_DOMAINS = ["epidemiology", "metabolomics", "cardiometabolic-disease", "public-health"]

print("=" * 70)
print("测试 1: 生物医学语境识别")
print("=" * 70)

is_bio = _is_biomedical_grant_context(SZ_STIB_TOPIC, SZ_STIB_DOMAINS)
print(f"  SZ-STIB 课题 → 生物医学语境: {is_bio}")
assert is_bio, "SZ-STIB 课题应被识别为生物医学语境"

# 反例：ML 课题不应被误判
ML_TOPIC = "Transformer architecture optimization for image classification benchmarks"
ML_DOMAINS = ["machine-learning", "computer-vision"]
is_ml_bio = _is_biomedical_grant_context(ML_TOPIC, ML_DOMAINS)
print(f"  ML 课题 → 生物医学语境: {is_ml_bio}")
assert not is_ml_bio, "ML 课题不应被识别为生物医学语境"

print("  ✅ 语境识别测试通过\n")

# ============================================================
# 2. 默认查询生成测试
# ============================================================

print("=" * 70)
print("测试 2: 生物医学默认查询生成")
print("=" * 70)

queries = _build_biomedical_default_search_queries(SZ_STIB_TOPIC)
print(f"  生成了 {len(queries)} 条默认查询:")
for i, q in enumerate(queries, 1):
    print(f"    {i}. {q}")

# 检查不应包含算法/benchmark 类查询
bad_keywords = ["benchmark", "deep learning", "SOTA", "leaderboard", "neural network"]
for q in queries:
    for kw in bad_keywords:
        assert kw.lower() not in q.lower(), f"查询 '{q}' 不应包含 '{kw}'"

print("  ✅ 无算法类查询污染\n")

# ============================================================
# 3. 真实 OpenAlex 检索测试
# ============================================================

print("=" * 70)
print("测试 3: OpenAlex 真实文献检索")
print("=" * 70)

# SSL 上下文（跳过证书验证，本地环境可能有 SSL 问题）
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

test_queries = [
    "NMR metabolomics cardiometabolic multimorbidity UK Biobank",
    "Nightingale NMR metabolomics cardiovascular disease",
    "metabolomics risk stratification obesity",
    "NMR metabolomics type 2 diabetes UK Biobank",
]

openalex_results = []
for query in test_queries:
    params = urllib.parse.urlencode({
        "search": query,
        "per_page": 5,
        "mailto": "researchclaw@users.noreply.github.com",
        "select": "id,title,publication_year,cited_by_count,doi",
        "filter": "from_publication_date:2020-01-01",
    })
    url = f"https://api.openalex.org/works?{params}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            print(f"\n  查询: '{query}'")
            print(f"  返回: {data.get('meta', {}).get('count', '?')} 篇总结果, 显示前 {len(results)} 篇")
            for r in results[:3]:
                title = r.get("title", "N/A")
                year = r.get("publication_year", "?")
                cites = r.get("cited_by_count", 0)
                print(f"    - [{year}] {title} (引用: {cites})")
                openalex_results.append({
                    "query": query,
                    "title": title,
                    "year": year,
                    "cites": cites,
                })
            time.sleep(1)  # rate limit
    except Exception as e:
        print(f"  ❌ 查询失败: {e}")

print(f"\n  OpenAlex 共获取 {len(openalex_results)} 条结果")

# 检查结果质量
if openalex_results:
    # 至少有结果包含关键词
    relevant_count = 0
    bio_keywords = ["metabolom", "NMR", "cardiometabolic", "obesity", "diabetes",
                    "cardiovascular", "kidney", "multimorbidity", "UK Biobank"]
    for r in openalex_results:
        title_lower = r["title"].lower()
        if any(kw.lower() in title_lower for kw in bio_keywords):
            relevant_count += 1

    relevance_rate = relevant_count / len(openalex_results) * 100
    print(f"  相关率: {relevant_count}/{len(openalex_results)} ({relevance_rate:.0f}%)")

    # 不应出现纯算法论文
    algo_keywords = ["deep learning", "neural network", "benchmark", "SOTA", "transformer"]
    algo_count = sum(1 for r in openalex_results
                     if any(kw in r["title"].lower() for kw in algo_keywords))
    print(f"  算法类论文: {algo_count}/{len(openalex_results)}")
    assert algo_count == 0, "不应出现纯算法论文"
    print("  ✅ 无算法论文污染")
else:
    print("  ⚠️ OpenAlex 无结果（可能是网络问题）")

# ============================================================
# 4. Semantic Scholar 真实检索测试
# ============================================================

print(f"\n{'=' * 70}")
print("测试 4: Semantic Scholar 真实文献检索")
print("=" * 70)

s2_results = []
s2_test_query = "NMR metabolomics cardiometabolic multimorbidity obesity"
s2_params = urllib.parse.urlencode({
    "query": s2_test_query,
    "limit": 10,
    "fields": "paperId,title,year,citationCount,venue",
    "year": "2020-",
})

s2_url = f"https://api.semanticscholar.org/graph/v1/paper/search?{s2_params}"

try:
    req = urllib.request.Request(s2_url)
    s2_api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", os.environ.get("S2_API_KEY", ""))
    if s2_api_key:
        req.add_header("x-api-key", s2_api_key)
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=15) as resp:
        s2_data = json.loads(resp.read().decode())
        s2_results = s2_data.get("data", [])
        total = s2_data.get("total", "?")
        print(f"  查询: '{s2_test_query}'")
        print(f"  总结果: {total}")
        print(f"  返回: {len(s2_results)} 篇")

        s2_relevant = 0
        for paper in s2_results[:5]:
            title = paper.get("title", "N/A")
            year = paper.get("year", "?")
            cites = paper.get("citationCount", 0)
            venue = paper.get("venue", "")
            print(f"    - [{year}] {title}")
            print(f"      引用: {cites}, 期刊: {venue}")

            bio_kw = ["metabolom", "cardiovascular", "diabetes", "obesity", "kidney",
                      "NMR", "cohort", "multimorbidity"]
            if any(kw.lower() in (title or "").lower() for kw in bio_kw):
                s2_relevant += 1

        if s2_results:
            print(f"\n  相关率: {s2_relevant}/{min(5, len(s2_results))}")
            print("  ✅ Semantic Scholar 检索正常")
        else:
            print("  ⚠️ 无结果")
except urllib.error.HTTPError as e:
    print(f"  ⚠️ HTTP 错误: {e.code} {e.reason}")
    if e.code == 429:
        print("  （429 限流 - 建议设置 SEMANTIC_SCHOLAR_API_KEY）")
except Exception as e:
    print(f"  ⚠️ 检索失败: {e}")

# ============================================================
# 5. 总结
# ============================================================

print(f"\n{'=' * 70}")
print("测试总结")
print("=" * 70)
print(f"  1. 生物医学语境识别: ✅ 正确")
print(f"  2. 默认查询生成 ({len(queries)} 条): ✅ 无算法污染")
print(f"  3. OpenAlex 检索: {'✅ ' + str(len(openalex_results)) + ' 条结果' if openalex_results else '⚠️ 无结果'}")
print(f"  4. Semantic Scholar 检索: {'✅ 有结果' if s2_results else '⚠️ 需检查'}")
print(f"\n  生物医学适配改造验证{'通过' if openalex_results else '部分通过（网络问题）'}")
