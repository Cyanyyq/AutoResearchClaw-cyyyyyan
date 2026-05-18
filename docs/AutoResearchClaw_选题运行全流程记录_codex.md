# AutoResearchClaw 选题运行全流程记录（Codex）

生成日期：2026-05-15  
记录对象：SZ-STIB 面上项目选题中，Codex 使用 AutoResearchClaw 的 stage1-5 运行过程  
用途：作为后续与 AutoProjectClaw 运行流程逐项对照、定位 AutoProjectClaw 改造方向的基准材料。

## 1. 本轮任务背景

用户希望围绕“深圳市科技创新局 2026 年度基础研究专项自然科学基金计划面上项目”进行选题评估，并曾要求使用：

```text
/Users/yangyiqun/codex_work/AutoResearchClaw
```

完整运行 stage1-5，要求联网搜索，输出覆盖到：

```text
/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/SZ-STIB/AutoresearchClaw选题/codex
```

本记录只整理 `codex` 子目录，也就是 Codex 运行 AutoResearchClaw 的过程。`cc-glm` 子目录是另一套运行结果，后续可另行对照。

## 2. 当前有效输出目录

```text
/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/SZ-STIB/AutoresearchClaw选题/codex
```

建议阅读顺序：

```text
AutoResearchClaw_stage1-5_联网重跑报告.md
stage-01/goal.md
stage-02/problem_tree.md
stage-03/search_plan.yaml
stage-03/queries.json
stage-04/search_meta.json
stage-05/shortlist.jsonl
kb/
pipeline_summary.json
checkpoint.json
```

其中：

- `AutoResearchClaw_stage1-5_联网重跑报告.md` 是当时运行后写的人工总结。
- `stage-01` 到 `stage-05` 是主流程产物。
- `kb/` 是 AutoResearchClaw 自动归档的 Markdown 知识库。
- `checkpoint.json` 记录最后完成到 stage5。
- `pipeline_summary.json` 记录 resume 后 stage4-5 的运行摘要。

## 3. 运行配置

有效配置文件：

```text
AutoresearchClaw选题/codex/config.codex.yaml
```

关键设置：

```yaml
project:
  name: "SZ-STIB AutoResearchClaw Topic Selection"
  mode: "full-auto"
  language: "zh-CN"
  dry_run: false

llm:
  provider: "acp"
  acp:
    agent: "codex"
    cwd: "/Users/yangyiqun/codex_work/AutoResearchClaw"
    session_name: "researchclaw-codex-sz-stib"

research:
  field: "流行病学; 代谢组学; 心肾代谢; 慢病多病共存; UK Biobank"
  keywords:
    - "UK Biobank"
    - "NMR metabolomics"
    - "cardiometabolic multimorbidity"
    - "type 2 diabetes"
    - "cardiovascular disease"
    - "chronic kidney disease"
    - "CKM syndrome"
    - "risk prediction"
    - "Shenzhen cohort"

literature_search:
  enabled: true
  year_min: 2023
  sources:
    - "pubmed"
    - "openalex"
    - "semantic_scholar"
    - "arxiv"
  max_queries: 12
  limit_per_query: 40

pipeline:
  checkpoint_enabled: true
  resume_from_checkpoint: true
  auto_approve_gates: true
  target_stage: "LITERATURE_SCREEN"
```

本次不是 dry-run。LLM provider 为 `acp`，agent 为 `codex`。但需要注意：该项目本身设计更偏论文自动化和 ML conference pipeline，因此后续 `deliverables/` 中仍出现 `neurips_2025.sty` 这类模板残留。

## 4. 可复现运行命令

进入项目并激活环境：

```bash
cd /Users/yangyiqun/codex_work/AutoResearchClaw
source .venv/bin/activate
```

完整 stage1-5 运行意图命令：

```bash
researchclaw run \
  --config "/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/SZ-STIB/AutoresearchClaw选题/codex/config.codex.yaml" \
  --output "/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/SZ-STIB/AutoresearchClaw选题/codex" \
  --auto-approve \
  --to-stage LITERATURE_SCREEN
```

由于 stage3 `queries.json` 最初存在检索词降级问题，运行中人工中断并修正 `stage-03/queries.json`，随后从 checkpoint 继续：

```bash
researchclaw run \
  --config "/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/SZ-STIB/AutoresearchClaw选题/codex/config.codex.yaml" \
  --output "/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/SZ-STIB/AutoresearchClaw选题/codex" \
  --auto-approve \
  --resume \
  --to-stage LITERATURE_SCREEN
```

## 5. 运行 ID 与 checkpoint

本次输出中存在两个 run id：

```text
stage1-3: rc-20260514-082717-ff5368
stage4-5: rc-20260514-083803-ff5368
```

原因：

- stage1-3 先完成。
- stage3 之后发现 `queries.json` 与 `search_plan.yaml` 不一致，需要人工修正。
- 修正后使用 `--resume` 继续运行 stage4-5，因此 stage4-5 记录了新的 run id。

最终 checkpoint：

```json
{
  "last_completed_stage": 5,
  "last_completed_name": "LITERATURE_SCREEN",
  "run_id": "rc-20260514-083803-ff5368"
}
```

`pipeline_summary.json` 只记录 resume 后 stage4-5：

```json
{
  "stages_executed": 2,
  "stages_done": 2,
  "from_stage": 4,
  "final_stage": 5,
  "final_status": "done"
}
```

因此判断“整个 stage1-5 是否完成”不能只看 `pipeline_summary.json`，还要结合 `stage-01` 到 `stage-05` 的 `stage_health.json`、`decision.json` 和 `checkpoint.json`。

## 6. 各阶段实际运行结果

### Stage 1: TOPIC_INIT

目录：

```text
stage-01/
```

输出：

```text
goal.md
hardware_profile.json
stage_health.json
decision.json
```

状态：

```json
{
  "stage_id": "01-topic_init",
  "status": "done",
  "duration_sec": 132.96,
  "artifacts_count": 2
}
```

生成方向：

```text
心肾代谢综合征（CKM）早期进展的代谢残余风险分层
```

建议题目：

```text
基于 UK Biobank NMR 代谢组学的 CKM 早期进展代谢残余风险识别及深圳人群转化验证
```

核心判断：

- 不把“中心性肥胖 + 代谢组学异质性”作为核心创新点。
- 将科学问题转向 CKM 0-2 期人群向 CKM 3-4 期或 CMM 进展的代谢残余风险。
- UKB NMR 用作发现队列。
- 深圳社区/体检人群用作迁移性评价或临床代理评分验证。

### Stage 2: PROBLEM_DECOMPOSE

目录：

```text
stage-02/
```

输出：

```text
problem_tree.md
topic_evaluation.json
stage_health.json
decision.json
```

状态：

```json
{
  "stage_id": "02-problem_decompose",
  "status": "done",
  "duration_sec": 244.29,
  "artifacts_count": 1
}
```

拆出的核心子问题：

1. CKM 0-2 期人群中，NMR 代谢组是否能识别传统 CKM 分期之外的代谢残余风险。
2. 哪些代谢通路对应 CKM 早期向晚期进展，而不是只对应单一疾病发生。
3. CKM 0/1 -> 2 与 CKM 2 -> 3/4 是否存在不同代谢转移特征。
4. 能否构建低维、可解释、可迁移的 CKM 代谢残余风险评分。
5. 深圳社区/体检人群若无 NMR，可以验证 CKM 分期、风险梯度和临床代理评分。
6. 代谢残余风险是否在糖尿病前期、新发 T2D、高血压、肥胖、eGFR 轻度下降等本地高风险亚群中更有价值。
7. 代谢评分能否指导体检后随访策略。

主要风险提示：

- CKM stage 3 的亚临床 CVD 指标在 UKB 和深圳本地数据中可能不完整。
- 深圳本地数据如果没有 NMR，不能声称直接外部验证 NMR 代谢物。
- 观察性代谢组结果不能直接写成因果机制证明。
- 既往项目避重要求不能把中心性肥胖作为主轴。

### Stage 3: SEARCH_STRATEGY

目录：

```text
stage-03/
```

输出：

```text
search_plan.yaml
queries.json
sources.json
stage_health.json
decision.json
```

状态：

```json
{
  "stage_id": "03-search_strategy",
  "status": "done",
  "duration_sec": 107.88,
  "artifacts_count": 3
}
```

`search_plan.yaml` 生成了较好的项目型检索设计，包括：

- preferred titles
- avoid titles
- inclusion/exclusion criteria
- merged queries
- priority evidence map
- proposed analysis route
- risk controls
- screening fields
- source verification plan

推荐题目方向包括：

```text
基于UK Biobank NMR代谢组和深圳体检人群验证的心肾代谢早期进展残余风险识别研究
心肾代谢综合征早期阶段转移的代谢组特征及其深圳社区人群风险分层验证
面向心肾代谢多病共存预防的NMR代谢残余风险评分构建与本地化验证
```

避开的题目包括：

```text
中心性肥胖代谢组异质性及糖尿病心代谢共病风险研究
基于中心性肥胖的代谢组分型研究
```

#### Stage3 人工修正

`search_plan.yaml` 里原本有高质量 `merged_queries`，例如：

```text
UK Biobank NMR metabolomics multimorbidity diabetes cardiovascular kidney disease
cardiometabolic multimorbidity metabolomics risk prediction UK Biobank
CKM syndrome metabolomics cohort study
NMR metabolomics type 2 diabetes cardiovascular disease chronic kidney disease
metabolomic signatures cardiometabolic multimorbidity prospective cohort
```

但 AutoResearchClaw 的 stage3 解析器没有正确读取 `merged_queries` 字段，导致最初进入 `queries.json` 的检索词降级为类似：

```text
2026 UK Biobank SZMB UK Biobank
2026 UK Biobank SZMB benchmark
2026 UK Biobank SZMB survey
```

这些 query 不适合正式 stage4 文献检索。因此在 stage4 正式完成前中断运行，手动将 `stage-03/queries.json` 改为 12 条明确的 CKM/NMR/UKB/CMM 检索词，并将 `year_min` 设为 2023。

最终有效 `queries.json`：

```json
{
  "queries": [
    "UK Biobank NMR metabolomics multimorbidity diabetes cardiovascular kidney disease",
    "cardiometabolic multimorbidity metabolomics risk prediction UK Biobank",
    "cardiovascular kidney metabolic syndrome CKM metabolomics cohort",
    "NMR metabolomics type 2 diabetes cardiovascular disease chronic kidney disease UK Biobank",
    "metabolomic signatures cardiometabolic multimorbidity prospective cohort",
    "UK Biobank NMR metabolomics chronic kidney disease incident",
    "UK Biobank metabolomics type 2 diabetes coronary heart disease stroke",
    "cardiometabolic multimorbidity metabolic signature cohort study",
    "CKM stages mortality UK Biobank cardiovascular kidney metabolic syndrome",
    "Nightingale NMR metabolomics disease atlas UK Biobank 2025",
    "metabolomics cardiometabolic multimorbidity multi-state transition",
    "metabolomic risk score cardiovascular kidney metabolic syndrome"
  ],
  "year_min": 2023
}
```

`sources.json` 中 13 个网页/文献来源被 `web_fetch` 验证，包含 AHA CKM advisory、UKB NMR atlas、UKB NMR disease atlas、UKB annual report、CKD NMR、CMM 相关 UKB publication 页面等。

### Stage 4: LITERATURE_COLLECT

目录：

```text
stage-04/
```

输出：

```text
candidates.jsonl
references.bib
search_meta.json
web_context.md
web_search_result.json
stage_health.json
decision.json
```

状态：

```json
{
  "stage_id": "04-literature_collect",
  "status": "done",
  "duration_sec": 304.66,
  "artifacts_count": 5
}
```

`search_meta.json`：

```json
{
  "real_search": true,
  "year_min": 2023,
  "total_candidates": 343,
  "bibtex_entries": 342
}
```

文件行数：

```text
343  stage-04/candidates.jsonl
3077 stage-04/references.bib
60   stage-04/web_context.md
171  stage-04/web_search_result.json
```

联网情况：

- OpenAlex 返回主要候选池。
- Semantic Scholar 出现 429 并触发 circuit breaker。
- arXiv 出现 503/429 或服务错误并触发 circuit breaker。
- `web_context.md` 包含 DuckDuckGo 网页结果，其中有 UKB NMR atlas、UKB NMR CKD、CMM 等页面。

主要问题：

- 候选池虽然多，但 OpenAlex 高被引排序带来大量噪声。
- `candidates.jsonl` 前几条就出现 Long COVID、dementia、ESC cardiomyopathy guideline、NAFLD guideline 等高被引但不贴题文献。
- 因此 `references.bib` 不能直接作为正式标书参考文献库。

### Stage 5: LITERATURE_SCREEN

目录：

```text
stage-05/
```

输出：

```text
shortlist.jsonl
stage_health.json
decision.json
```

状态：

```json
{
  "stage_id": "05-literature_screen",
  "status": "done",
  "duration_sec": 55.99,
  "artifacts_count": 1
}
```

`shortlist.jsonl` 共 15 条。

前 5 条相对有保留价值：

1. **Atlas of plasma NMR biomarkers for health and disease in 118,461 individuals from the UK Biobank**
   - 高度相关，可作为 UKB NMR 发现队列核心依据。
2. **Small molecule metabolites: discovery of biomarkers and therapeutic targets**
   - 可作代谢组学 biomarker 背景综述。
3. **Diabetic vascular diseases: molecular mechanisms and therapeutic strategies**
   - 可作糖尿病心脑肾血管共同机制背景，不是核心方法文献。
4. **The crucial role and mechanism of insulin resistance in metabolic disease**
   - 可作胰岛素抵抗共同机制背景。
5. **Applications of multi-omics analysis in human diseases**
   - 可作多组学整合方法背景，直接相关性有限。

后 10 条多为系统为了满足最小 shortlist 数量自动补足，`keep_reason` 为：

```text
Supplemented to meet minimum shortlist
```

其中包括 NAFLD guideline、microbiota-gut-brain、depression、COPD、adrenal incidentaloma、obesity and cancer、PCOS 等，和本项目直接相关性不足。正式写标书时不建议采用。

## 7. KB 子文件夹的作用

`kb/` 是 AutoResearchClaw 自动生成的 markdown knowledge base，不是额外分析结果，也不是缓存垃圾。

当前结构：

```text
kb/questions/
kb/decisions/
kb/literature/
```

作用：

- `kb/questions/`：归档 stage1 topic init、stage2 problem decompose 这类“问题形成”材料。
- `kb/decisions/`：归档 stage3 search strategy 这类“决策/策略”材料。
- `kb/literature/`：归档 stage4 literature collect 和 stage5 literature screen 材料。

这些文件通常是 stage 输出的 markdown 镜像或合并版本，用于后续检索、记忆、resume、跨阶段引用。`cc-glm` 运行中没有这个目录，主要是因为当时配置/运行路径没有把 `knowledge_base.root` 指向输出目录，或没有启用同样的 knowledge_base/openclaw_bridge 归档设置。

本次 Codex 配置中明确启用了：

```yaml
knowledge_base:
  backend: "markdown"
  root: ".../AutoresearchClaw选题/codex/kb"

openclaw_bridge:
  use_memory: true
  kb_root: ".../AutoresearchClaw选题/codex/kb"
```

因此生成 `kb/` 是预期行为。

## 8. 为什么只运行到 stage5

AutoResearchClaw 是 23-stage pipeline：

```text
1  TOPIC_INIT
2  PROBLEM_DECOMPOSE
3  SEARCH_STRATEGY
4  LITERATURE_COLLECT
5  LITERATURE_SCREEN
6  KNOWLEDGE_EXTRACT
7  SYNTHESIS
8  HYPOTHESIS_GEN
9  EXPERIMENT_DESIGN
10 CODE_GENERATION
...
23 CITATION_VERIFY
```

本次只运行到 stage5 的原因不是失败，而是任务目标本来就是“选题评估 + 联网文献筛选”。Stage6 以后会进入知识抽取、假设生成、实验设计、代码生成、实验运行、论文写作等流程，更接近完整论文自动化。

对于 SZ-STIB 标书选题来说：

- stage1-2 用于形成科学问题。
- stage3 用于形成检索策略。
- stage4 用于收集文献。
- stage5 用于初筛文献和形成可继续讨论的方向。

继续跑到 stage6-12 反而会把项目带向论文/算法实验路线，这也是 AutoResearchClaw 与 AutoProjectClaw 的核心差异之一。

## 9. 本次运行得到的有效选题方向

AutoResearchClaw stage1-2 中最有价值的方向是：

```text
基于 UK Biobank NMR 代谢组学的 CKM 早期进展代谢残余风险识别及深圳人群转化验证
```

更适合申报书表述为：

```text
基于 UK Biobank NMR 代谢组学的心肾代谢早期进展残余风险识别及深圳社区人群验证研究
```

优点：

- 避开“中心性肥胖 + 代谢组学异质性”既往项目重叠风险。
- 把 CKM/CMM 作为临床问题主线。
- 以 UKB NMR 做发现，以深圳社区/体检人群做转化或代理验证。
- 兼容 T2D、CVD、CKD、高血压、肥胖等已有研究基础。
- 若深圳本地无 NMR，仍可转为“临床代理评分”和“风险梯度验证”。

局限：

- 标题里 UKB 主导性很强，作为深圳市项目可能被质疑本地性不足。
- 如果正式申报，建议将 UKB 放到前期基础/发现队列，把深圳人群放到题目和研究内容主位。

## 10. 运行中暴露的问题

### 10.1 项目定位偏论文/ML pipeline

AutoResearchClaw 原始目标是论文自动化，stage2 评价中曾出现“更适合医学/公共卫生基金，不足以支撑 top ML conference”的倾向。这说明系统仍会不自觉把问题往 ML conference、benchmark、algorithmic novelty 上拉。

对 SZ-STIB 面上项目而言，这不是最优目标函数。

### 10.2 Stage3 查询字段解析问题

`search_plan.yaml` 中有好的 `merged_queries`，但解析器没有自动把它们转换进 `queries.json`。如果没有人工修正，stage4 会用很差的检索词联网搜索。

这是本次运行中最关键的流程 bug。

### 10.3 Stage4 检索候选噪声大

虽然 `real_search: true`，并且候选数量达到 343 条，但候选池主要来自 OpenAlex，高被引排序导致大量泛化医学综述和指南进入结果。

数量不能代表质量。

### 10.4 Semantic Scholar 和 arXiv 受限

运行时：

- Semantic Scholar 返回 429。
- arXiv 返回 503/429 或 timeout。

后续已经在项目中配置 Semantic Scholar API key，并为 S2 增加了限流/SSL 相关修复，但这次 `codex` 输出是在 key 配置和后续改造之前生成的。

### 10.5 Stage5 为凑数量补无关文献

`shortlist.jsonl` 后 10 条是自动补足，不是严格筛选结果。这个行为会让 shortlist 看起来完整，但实际降低证据质量。

### 10.6 后续产物仍有 NeurIPS 模板残留

`deliverables/neurips_2025.sty` 出现在输出目录中，说明 AutoResearchClaw 的产物包装仍保留机器学习会议模板。用于基金项目选题时，这类文件没有实际价值。

## 11. 与 AutoProjectClaw 对照时的关键点

这部分只列对照维度，不下最终结论。

### 11.1 输入组织

AutoResearchClaw：

- 输入是一个大段 `research.topic`。
- 直接让 stage1 生成 SMART goal。
- 对“避重备忘录、数据字典、深圳项目模板”没有 AutoProjectClaw 那种显式 context pack。

AutoProjectClaw：

- 有 Stage0 `CONTEXT_PACK`。
- 明确纳入 grant profile、investigator、assumptions、sources、data_dictionary_dirs。

### 11.2 科学问题形成

AutoResearchClaw：

- stage1-2 的科学问题推演很强。
- 能提出“CKM 早期进展 + 代谢残余风险 + 深圳转化验证”这种有价值切入点。

AutoProjectClaw：

- 更强调申报结构、研究内容递进和本地数据边界。
- 但科学问题的前沿感和文献推演深度弱一些。

### 11.3 检索策略

AutoResearchClaw：

- `search_plan.yaml` 质量不错。
- 但 parser 没有正确消费 `merged_queries`，需要人工修 `queries.json`。

AutoProjectClaw：

- Stage3 更结构化地按 aim/dimension 生成 query。
- 但默认模板也会过宽，并且曾把中文 aim 直接放入英文检索式。

### 11.4 文献收集

AutoResearchClaw：

- 候选多，联网确实打开。
- 但 OpenAlex 噪声大，Semantic Scholar/arXiv 被限流或服务错误影响。

AutoProjectClaw：

- 主流程检索数量更少。
- 后续人工 `quality_supplement` 更聚焦，更接近标书证据筛选。

### 11.5 最终输出用途

AutoResearchClaw：

- 更适合做科学问题启发、UKB NMR/CKM/CMM 前沿扫描。
- 直接输出不太像基金项目选题报告。

AutoProjectClaw：

- 更适合作为基金标书选题工具。
- 但 Stage5 需要改造成真正证据驱动的候选题动态评分。

## 12. 后续改造启示

如果要把 AutoProjectClaw 完善成更强的项目选题系统，可以从 AutoResearchClaw 吸收以下优点：

1. 保留 `stage_health.json` 和 `decision.json` 这种每阶段运行追踪。
2. 增加 `checkpoint.json`，便于中断后 resume。
3. 增加 markdown KB 归档，但要让用户能清楚知道 `kb/` 是什么。
4. 保留 stage1-2 对科学问题和文献前沿的深度推演能力。
5. 改进 Stage3 query 解析，避免“好 search_plan 没进入 queries.json”。
6. 改进 Stage5 文献筛选，禁止为了满足最小数量补无关文献。

同时，AutoProjectClaw 不应照搬 AutoResearchClaw 的：

- NeurIPS/ML conference 模板。
- benchmark/SOTA 导向。
- stage6 以后论文实验自动化逻辑。
- 将 UKB 写成项目唯一主数据源的倾向。

## 13. 当前结论

本次 Codex 对 AutoResearchClaw 的 stage1-5 运行是完整的：

- stage1-3 先完成。
- stage3 人工修正 `queries.json`。
- 使用 `--resume` 完成 stage4-5。
- 最终 checkpoint 到 `LITERATURE_SCREEN`。
- stage4 确认真实联网检索。
- stage5 生成 15 条 shortlist。

但它不是一份可直接用于标书的最终选题报告。它更像一份“科学问题发现 + 文献雷达”材料。正式用于 SZ-STIB 标书时，应吸收其 CKM/NMR/CMM 前沿切入点，再交给 AutoProjectClaw 这样的项目型流程处理 grant profile、避重、深圳本地性、研究内容结构和数据可实施性。

