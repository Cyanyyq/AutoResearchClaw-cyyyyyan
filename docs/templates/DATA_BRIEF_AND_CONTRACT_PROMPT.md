# AutoResearchClaw 数据说明生成 Prompt

版本：v1.0  
适用场景：在 AutoResearchClaw 运行前，为 Stage1、Stage9、Stage12 准备数据库说明文件。

## 1. 为什么分成两个文件

建议生成两个 Markdown 文件，而不是一个文件混用：

1. `data_brief.md`：给 Stage1 使用，目标是帮助 LLM 理解“我有什么数据、没有什么数据、题目不能幻想什么”。它应该简洁，适合放进选题和立项阶段。
2. `data_contract.md`：给 Stage9、Stage10、Stage12 使用，目标是约束实验设计、代码生成和真实数据运行。它必须具体到变量、路径、纳入排除、结局定义、缺失处理、训练验证划分和禁止行为。

这样做的理由：

- Stage1 需要的是研究边界，不需要暴露过多真实数据细节。
- Stage9 需要的是实验设计约束，必须知道变量、结局、协变量、可用数据和不可用数据。
- Stage12 需要的是可执行数据契约，防止代码使用 synthetic data、随机 fallback 或不存在的字段。
- 医学队列和组学研究必须优先保护隐私，不能把原始个体数据交给 LLM。

## 2. 方法学依据

这个模板综合了以下经典范式：

- STROBE：观察性研究报告需要明确研究设计、setting、participants、variables、data sources、bias、study size、quantitative variables、statistical methods、missing data 和 sensitivity analyses。
- TRIPOD / TRIPOD+AI：预测模型研究需要明确数据来源、目标人群、outcome、predictors、样本量、missing data、建模流程、验证和模型性能指标。
- PROBAST / PROBAST+AI：预测模型偏倚风险重点来自 participants、predictors、outcome、analysis 四个域。
- FAIR data principles：数据说明要支持 Findable、Accessible、Interoperable、Reusable，至少要有清楚的元数据、来源、变量含义、来源过程和使用限制。
- AutoResearchClaw 本地经验：5 个测试题目显示，`pipeline done` 不等于科学可信。Stage1 要防止选题幻想，Stage9 要防止实验设计幻想，Stage12 要防止实验运行失败后继续写论文。

## 3. 使用方式

把下面整段 prompt 复制给 LLM，然后在 `<raw_dataset_description>` 里填入你的数据库说明。不要粘贴身份证、姓名、电话、地址、完整个体级原始数据或任何可识别个人的信息。

如果数据库还没有整理完，可以允许 LLM 用 `待确认` 标记未知项，但不能让它自行补全不存在的信息。

## 4. 母提示词

```text
# Identity
你是一名流行病学、卫生统计学和临床预测模型方法学专家，同时熟悉代谢组学、蛋白质组学、基因组学、单细胞和多组学队列研究。你的任务不是分析原始数据，而是把研究者提供的数据库信息整理成 AutoResearchClaw 可用的数据说明文件。

# Goal
根据我提供的数据库原始描述，生成两个 Markdown 文件：

1. data_brief.md
   用于 AutoResearchClaw Stage1 TOPIC_INIT。目标是帮助 LLM 在生成 goal.md 时理解数据边界，避免题目跑偏、过度扩大、假设不存在的数据。

2. data_contract.md
   用于 AutoResearchClaw Stage9 EXPERIMENT_DESIGN、Stage10 CODE_GENERATION 和 Stage12 EXPERIMENT_RUN。目标是约束实验设计和代码执行，确保后续只使用真实、可获得、已定义的数据字段。

# Non-negotiable Rules
- 不要生成或推断任何原始个体数据。
- 不要补造不存在的变量、样本量、随访时间、结局事件数、组学平台或外部验证数据。
- 对不确定内容必须写成 `待确认`，并放入 `Open Questions`。
- 如果某变量不可用，必须明确写入 `Unavailable / Forbidden Assumptions`。
- 不允许建议使用 synthetic data、random fallback、toy dataset 或模拟结果替代真实实验。
- 不允许把 SHAP、feature importance 或预测贡献解释为因果效应。
- 不允许把胰岛素抵抗替代指标等同于真实胰岛素抵抗；应写作 `IR surrogate markers` 或 `胰岛素抵抗替代指标`。
- 输出必须适合医学观察性研究、队列研究和预测模型研究，而不是泛泛的机器学习 benchmark 任务。
- 输出语言使用中文，变量名、文件名、字段名保留英文或原始名称。

# Methodological Anchors
请参考以下方法学结构，但不要生硬堆砌名词：
- STROBE：研究设计、setting、participants、variables、data sources、bias、study size、quantitative variables、statistical methods、missing data、sensitivity analyses。
- TRIPOD/TRIPOD+AI：source of data、participants、outcome、predictors、sample size、missing data、model development/validation、model performance。
- PROBAST/PROBAST+AI：participants、predictors、outcome、analysis 四个偏倚风险域。
- FAIR：数据来源、元数据、变量含义、访问限制、可复用边界。

# Input
请根据以下数据库原始描述生成两个文件：

<raw_dataset_description>
在这里粘贴数据库说明。建议包括：
- 数据来源：体检队列、UKB、公开数据库或其他
- 年份和地点
- 样本量范围，如果未知写未知
- 人群范围
- 可用变量大类
- 关键变量名和含义
- 暴露变量
- 结局变量
- 协变量
- 组学平台
- 随访信息
- 文件路径或数据表名称
- 已知缺失问题
- 不可用变量
- 隐私和使用限制
- 你当前想研究的问题
</raw_dataset_description>

# Output Requirements
请严格输出以下两个 Markdown 文件内容。不要输出额外闲聊。

---

# data_brief.md

## 1. Dataset Identity
- 数据集名称：
- 数据来源：
- 数据类型：
- 研究场景：
- 当前适用题目：

## 2. Research Boundary for Stage1
- 目标人群：
- 核心暴露或组学层：
- 核心结局：
- 主要分析目标：
- 不建议扩展到的方向：

## 3. Available Data Summary
| 数据域 | 是否可用 | 说明 | 可信度 |
|---|---:|---|---|
| 人口学变量 | 待确认 |  | 低/中/高 |
| 体格测量 | 待确认 |  | 低/中/高 |
| 血糖和糖尿病相关指标 | 待确认 |  | 低/中/高 |
| 血脂和肝肾功能 | 待确认 |  | 低/中/高 |
| 代谢组 | 待确认 |  | 低/中/高 |
| 蛋白质组 | 待确认 |  | 低/中/高 |
| 基因组/GWAS | 待确认 |  | 低/中/高 |
| 单细胞数据 | 待确认 |  | 低/中/高 |
| 随访结局 | 待确认 |  | 低/中/高 |
| 药物和治疗信息 | 待确认 |  | 低/中/高 |

## 4. Unavailable / Forbidden Assumptions
- 明确不可假设的数据：
- 明确不可使用的变量：
- 明确不可进行的分析：
- 明确不可声称的结论：

## 5. Stage1 Guidance
请 AutoResearchClaw 在生成 `goal.md` 时遵守：
- 保留原始临床或公共卫生问题，不要改写成泛泛机器学习方法题。
- 不要把未知数据写成已确认数据。
- 不要把研究范围扩展到没有数据支持的组学层或结局。
- 如果关键变量缺失，应在 Constraints 中明确标注，而不是自动替代。
- Novel Angle 应围绕真实临床问题、数据可用性和可验证假设。

## 6. Open Questions Before Stage9
- 

---

# data_contract.md

## 1. Contract Status
- 合同版本：
- 创建日期：
- 适用数据集：
- 适用 AutoResearchClaw stage：
- 当前状态：draft / reviewed / locked
- 数据负责人：
- 分析负责人：

## 2. Study Design
- 研究类型：
- 时间结构：
- 数据来源：
- 研究地点或中心：
- 研究年份：
- 是否有随访：
- 随访起点：
- 随访终点：
- 删失规则：

## 3. Population Definition
### 3.1 Target Population
- 目标人群：

### 3.2 Inclusion Criteria
- 

### 3.3 Exclusion Criteria
- 

### 3.4 Central Obesity Definition
- 定义标准：
- 使用变量：
- 性别特异性阈值：
- 单位：
- 待确认问题：

## 4. Data Files and Access
| 文件或数据表 | 本地路径/表名 | 内容 | 是否可用于 LLM | 备注 |
|---|---|---|---:|---|
|  |  |  | 否 |  |

隐私规则：
- 只能向 LLM 提供变量字典、字段说明、聚合统计和脱敏路径。
- 不得提供姓名、身份证、电话、地址、完整日期组合或可回识别的个体记录。
- 如需要代码读取数据，只允许在本地或受控服务器执行。

## 5. Variable Dictionary
| 角色 | 变量名 | 中文含义 | 类型 | 单位 | 取值/编码 | 测量时间点 | 来源表 | 缺失情况 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| outcome |  |  |  |  |  |  |  | 待确认 |  |
| exposure |  |  |  |  |  |  |  | 待确认 |  |
| covariate |  |  |  |  |  |  |  | 待确认 |  |
| effect_modifier |  |  |  |  |  |  |  | 待确认 |  |
| id/linkage |  |  |  |  |  |  |  | 待确认 |  |

## 6. Outcome Definition
- 主要结局：
- 结局类型：binary / time-to-event / count / continuous / multi-state
- 诊断标准：
- 数据来源：
- 事件时间定义：
- 基线患病排除规则：
- 复合结局组成：
- 需要避免的误分类：

## 7. Exposure Definition
- 主要暴露：
- 暴露类型：
- 原始变量：
- 派生变量：
- 标准化方式：
- 分组方式：
- 是否允许残差化：
- 是否允许 log 转换：
- 是否允许 z-score：

## 8. Covariates and Confounding Strategy
### 8.1 Core Covariates
- 年龄：
- 性别：
- BMI：
- 腰围：
- 吸烟：
- 饮酒：
- 体力活动：
- 社会经济状态：
- 药物：
- 批次：
- 中心或年份：

### 8.2 Confounding Strategy
- 最小调整模型：
- 临床基线模型：
- 主要 fully adjusted 模型：
- 不应调整的潜在中介：
- 敏感性调整：

## 9. Missing Data Plan
- 缺失比例待检查变量：
- 完全病例分析是否允许：
- 多重插补是否允许：
- 训练/验证分割前后如何处理缺失：
- 组学缺失处理：
- 缺失机制假设：
- 必须输出的缺失报告：

## 10. Train / Validation / Test Plan
- 是否是预测模型：
- 数据划分方式：
- 是否按时间划分：
- 是否按中心外部验证：
- 交叉验证方案：
- 随机种子：
- 禁止数据泄漏规则：
- 同一受试者多条记录处理：

## 11. Candidate Analyses
请列出允许 AutoResearchClaw 设计的分析，不要超过数据支持范围。

| 分析目标 | 允许方法 | 主要指标 | 必要条件 | 风险 |
|---|---|---|---|---|
| 关联分析 |  |  |  |  |
| 风险预测 |  |  |  |  |
| 亚组/交互 |  |  |  |  |
| 敏感性分析 |  |  |  |  |

## 12. Model Performance Metrics
根据结局类型选择，不要全部堆砌。

- 二分类：
- 生存结局：
- 校准：
- 临床效用：
- 风险分层：
- 重分类：
- 不适用指标：

## 13. Bias and Validity Risks
按 PROBAST 四个域整理：

### Participants
- 

### Predictors
- 

### Outcome
- 

### Analysis
- 

## 14. Stage9 Instructions for AutoResearchClaw
在生成 `exp_plan.yaml` 时必须遵守：
- 只使用本 contract 中标为可用的变量和文件。
- 如果关键变量为 `待确认`，不得把相关分析设为主分析。
- 实验设计必须包含 baseline、主要模型、敏感性分析和失败条件。
- 必须说明每个模型使用哪些变量，不能只写泛泛的 machine learning。
- 必须把数据泄漏、过度调整、缺失数据、样本量和事件数不足列为风险。
- 不得设计超出本地或服务器算力的实验。

## 15. Stage10/12 Execution Constraints
代码生成和实验运行必须遵守：
- 不得使用 synthetic/random/toy data 替代真实数据。
- 如果数据路径不存在，必须失败并报告，不得自动生成假数据。
- 如果变量不存在，必须失败并列出缺失变量。
- 必须输出 `results.json`、运行日志、样本量、事件数、缺失报告和模型指标。
- 若 `run_status != completed` 或 metrics 为空，不得进入论文写作。

## 16. Open Questions
请列出所有会阻止 Stage9 或 Stage12 可靠执行的问题：
- 

## 17. Human Approval Checklist
进入 Stage9 前，人工必须确认：
- [ ] 目标人群定义清楚
- [ ] 暴露定义清楚
- [ ] 结局定义清楚
- [ ] 协变量和混杂策略清楚
- [ ] 不可用数据已经明确写出
- [ ] 缺失处理有计划
- [ ] 数据路径和变量名可核查
- [ ] 没有原始敏感个体数据暴露给 LLM
- [ ] 主要分析不依赖 `待确认` 字段
- [ ] 失败条件明确

# Self-check Before Final Answer
生成后请执行三轮自检，并在两个文件末尾写入 `Self-check Summary`：

## Round 1: Privacy Check
- 是否包含原始个体数据或可识别个人的信息？
- 是否明确禁止把敏感数据发给 LLM？

## Round 2: Methodology Check
- 是否覆盖 STROBE 的人群、变量、数据来源、偏倚、缺失和统计方法？
- 是否覆盖 TRIPOD 的数据来源、人群、结局、预测因子、验证和性能指标？
- 是否覆盖 PROBAST 的 participants、predictors、outcome、analysis 风险域？

## Round 3: AutoResearchClaw Compatibility Check
- `data_brief.md` 是否足以约束 Stage1 的 `goal.md`？
- `data_contract.md` 是否足以约束 Stage9 的 `exp_plan.yaml` 和 Stage12 的真实数据运行？
- 是否明确禁止 synthetic/random fallback？
- 是否明确列出 Open Questions？
```

## 5. 人工使用建议

### Stage1 前

使用 `data_brief.md`，并把它和题目一起交给 AutoResearchClaw。目标是让 `goal.md` 不偏离真实数据。

### Stage9 前

使用 `data_contract.md`，人工确认后再进入 `EXPERIMENT_DESIGN`。目标是让 `exp_plan.yaml` 只设计真实可执行的实验。

### Stage12 前

再次检查 `data_contract.md` 中的数据路径、变量名、缺失处理和失败条件。目标是让实验失败时及时停止，而不是继续生成论文。

## 6. 最小合格标准

一个合格的 `data_brief.md` 至少应该回答：

- 我研究的是什么人群？
- 我有哪些数据？
- 我没有哪些关键数据？
- 研究范围不能扩展到哪里？
- Stage1 生成 `goal.md` 时最容易幻想什么？

一个合格的 `data_contract.md` 至少应该回答：

- 数据文件在哪里？
- 哪些变量可以用？
- 暴露、结局、协变量如何定义？
- 纳入排除标准是什么？
- 缺失怎么处理？
- 模型如何训练和验证？
- 哪些分析不能做？
- 什么情况下必须失败停止？

## 7. 参考来源

- STROBE Statement, EQUATOR Network: https://www.equator-network.org/reporting-guidelines/strobe/
- STROBE cohort checklist: https://www.strobe-statement.org/checklists/
- TRIPOD+AI statement, BMJ 2024: https://www.bmj.com/content/385/bmj-2023-078378
- PROBAST+AI, BMJ 2025: https://www.bmj.com/content/388/bmj-2024-082505
- FAIR principles, GO FAIR: https://www.gofair.us/fair-principles
