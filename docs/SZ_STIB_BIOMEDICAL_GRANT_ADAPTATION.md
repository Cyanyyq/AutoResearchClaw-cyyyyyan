# SZ-STIB 生物医学基金选题适配改造说明

## 背景

AutoResearchClaw 原始流程更偏向算法论文自动写作：默认提示词强调 benchmark、SOTA、leaderboard、NeurIPS/ICML/ICLR 式实验，Stage 3 生成检索策略后，Stage 4 只读取少数字段，Stage 5 还会为了凑够固定数量自动补充候选论文。

用于“深圳市科技创新局 2026 年度基础研究专项自然科学基金计划面上项目”选题评估时，这些设计容易带来三类偏差：

- 中文生物医学课题被抽成少量英文 token，检索词质量下降。
- LLM 输出的 `merged_queries`、数据库专用查询没有被 Stage 4 读取，优质 PubMed/OpenAlex 查询丢失。
- Stage 5 为了补齐 15 篇文献，会把低相关综述或跨领域论文重新补入 shortlist。

## 已改造内容

### 1. 生物医学/基金语境识别

新增生物医学基金语境识别，覆盖以下关键词：

- 中文：基金、标书、申报、队列、流行病、代谢组、心肾代谢、糖尿病、心血管、肾病、多病共存、深圳等。
- 英文：biomedical、clinical、epidemiology、cohort、PubMed、metabolomics、UK Biobank、NMR、CKM、CMM、multimorbidity 等。

识别为生物医学基金语境后，检索和筛选逻辑会切换到队列/疾病/生物标志物优先模式。

### 2. Stage 3 查询提取修复

Stage 4 现在会读取更多常见 search plan 字段：

- `search_strategies[*].queries`
- `queries`
- `search_queries`
- `database_queries`
- `merged_queries`
- `queries_by_source`
- `pubmed_queries`
- `openalex_queries`
- `semantic_scholar_queries`
- `scholar_queries`

这样 LLM 生成的 PubMed、OpenAlex、Semantic Scholar 查询不会因为字段名不同而被丢弃。

### 3. 中文课题 fallback 检索词

当中文课题无法抽出足够英文检索词时，会生成稳定的生物医学默认查询，例如：

- `UK Biobank NMR metabolomics`
- `cardiometabolic multimorbidity metabolomics`
- `cardiovascular kidney metabolic syndrome cohort`
- `CKM syndrome metabolomics cohort`
- `NMR metabolomics type 2 diabetes UK Biobank`
- `NMR metabolomics cardiovascular disease UK Biobank`
- `NMR metabolomics chronic kidney disease UK Biobank`

生物医学语境下不再自动加入 `benchmark`、`survey`、`deep learning` 等算法论文默认扩展词。

### 4. Stage 5 文献筛选改造

生物医学基金语境下，Stage 5 会先按领域信号重新排序候选文献，优先保留含有 UK Biobank、NMR、metabolomics、CKM、CMM、cardiometabolic multimorbidity、risk prediction、prospective cohort 等信号的论文。

同时，生物医学语境下不再强制把 shortlist 补到 15 篇。若 LLM 严格筛选后只保留少量高相关论文，系统会保留这个结果，而不是用泛综述或低相关论文补齐。

### 5. Semantic Scholar 限流处理

Semantic Scholar 客户端新增：

- 自动读取环境变量 `SEMANTIC_SCHOLAR_API_KEY` 或 `S2_API_KEY`。
- 有 API key 时按约 1 RPS 节流；无 key 时更保守。
- 遇到 429 时优先尊重 `Retry-After` 响应头。

建议运行前设置：

```bash
export SEMANTIC_SCHOLAR_API_KEY="你的 Semantic Scholar API key"
```

## 默认 Prompt 改造

`researchclaw/prompts.py` 和 `prompts.default.yaml` 均已同步调整：

- `topic_init`：从算法论文的 benchmark/SOTA 叙事，扩展为数据资源、队列、注册库、外部验证、效应量和公共卫生价值。
- `search_strategy`：明确要求 YAML 必须包含 `search_strategies[*].queries`，并要求生物医学课题优先生成 PubMed/OpenAlex 友好英文查询。
- `literature_screen`：筛选标准从算法方法/benchmark 扩展到队列、终点、标志物、预测指标、验证设计和疾病发现。

## 验证

已通过定向测试：

```bash
uv run --extra dev pytest tests/test_rc_executor.py::TestExpandSearchQueries tests/test_rc_literature.py::TestSemanticScholar -q
```

结果：

```text
13 passed
```

同时通过语法编译检查：

```bash
.venv/bin/python3 -m compileall researchclaw/pipeline/stage_impls/_literature.py researchclaw/literature/semantic_scholar.py researchclaw/prompts.py researchclaw/pipeline/executor.py
```

## 后续建议

后续用于 SZ-STIB 项目选题评估时，建议配置中显式写入：

- `research.domains`: 包含 `epidemiology`、`biomedical`、`metabolomics`、`UK Biobank` 等词。
- `web_search.enabled`: 开启。
- `llm.s2_api_key` 或环境变量 `SEMANTIC_SCHOLAR_API_KEY`: 填入 Semantic Scholar key。

这样 Stage 1-5 会更稳定地围绕“队列数据 + 代谢组/多组学 + 糖尿病/心脑血管/肾病/心肾代谢共病 + 基金选题可行性”展开，而不是回到算法论文自动写作模式。
