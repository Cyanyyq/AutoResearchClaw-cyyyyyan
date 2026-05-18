# AutoResearchClaw 正式运行 SOP

版本：v1.0  
适用项目：`/Users/yangyiqun/codex_work/AutoResearchClaw`

## 0. 核心原则

不要直接批量生成最终论文。

正式流程必须分三段：

1. `Stage01-09`：批量选题筛选
2. `Stage10-12`：真实数据 pilot
3. `Stage13-23`：完整论文生成 + full audit + 人工分析

只有前一阶段审计通过，才进入下一阶段。

## 1. 固定路径

```bash
PROJECT=/Users/yangyiqun/codex_work/AutoResearchClaw
ROOT=/Users/yangyiqun/Library/CloudStorage/坚果云-yqyangyangyq@163.com/project/Autoresearchclaw/codex
```

进入项目：

```bash
cd /Users/yangyiqun/codex_work/AutoResearchClaw
source .venv/bin/activate
```

## 2. 运行前检查

检查本地关键脚本是否可编译：

```bash
python3 -m py_compile \
  researchclaw/pipeline/code_agent.py \
  researchclaw/pipeline/stage_impls/_code_generation.py \
  researchclaw/pipeline/stage_impls/_execution.py \
  researchclaw/cli.py \
  scripts/audit_researchclaw_batch.py
```

检查是否有旧任务或 ACP 进程残留：

```bash
pgrep -fl 'run_codex|researchclaw run|acpx|codex-acp'
```

确认没有任务正在运行后，才可以清理旧 ACP：

```bash
pkill -f codex-acp
```

注意：不要在不确认的情况下清理进程，避免杀掉正在运行的任务。

## 3. 准备题目文件

每行一个题目，例如：

```bash
topics_screening.txt
```

题目要求：

- 每个题目聚焦一个小临床问题
- 明确人群、暴露或组学类型、结局、分析目标
- 不要一次写成大而全的总课题
- 不要把真实个体数据写进题目

示例：

```text
中心性肥胖人群中，支链氨基酸与 T2D 发病风险：是否独立于胰岛素抵抗替代指标？
```

## 4. 第一阶段：Stage01-09 选题筛选

目的：批量判断题目是否值得做，不进入代码生成、实验运行和论文写作。

推荐命令：

```bash
AUTORESEARCHCLAW_MAX_PARALLEL=2 \
AUTORESEARCHCLAW_HITL_MODE=co-pilot \
./run_codex_copilot_batch.sh topics_screening.txt --to-stage EXPERIMENT_DESIGN
```

如果只是粗筛，可以用：

```bash
AUTORESEARCHCLAW_HITL_MODE=full-auto
```

但最终必须人工查看 `Stage09`。

筛选阶段审计：

```bash
scripts/audit_researchclaw_batch.py "$ROOT" --prefix <batch_prefix> --profile screening
```

`Stage09` 通过标准：

- `stage-09/stage_health.json` 为 `done`
- 没有进入 `Stage10`
- `exp_plan.yaml` 中研究目标、数据需求、baseline、metrics 清楚
- 没有假定不存在的数据
- 人工确认该题目值得进入真实数据 pilot

未通过时，不进入后续阶段。

## 5. 第二阶段前置：准备真实数据 pilot

必须先写数据说明文件，建议命名：

```bash
data_contract.md
```

内容至少包括：

- 数据来源：体检队列、UKB 或公开数据
- 样本范围：年份、纳入排除、中心性肥胖定义
- 结局定义：T2D、CKD、CVD、共病等
- 暴露变量：BCAA、代谢物、蛋白、基因、多组学变量等
- 协变量：年龄、性别、BMI、腰围、吸烟、饮酒、药物、实验批次等
- 文件路径：只给本地路径，不给原始敏感数据
- 缺失处理、训练/验证划分、随访时间、删失规则
- 明确要求：只能使用这些真实数据，缺数据必须停止报告

隐私注意：

- 不要把身份证、姓名、电话、住址、原始个体明细发给 LLM
- 尽量使用脱敏后的分析数据或变量字典
- 本地路径可以给，敏感原始数据内容不要复制进 prompt

## 6. 第二阶段：Stage01-12 真实数据 pilot

目的：验证真实数据是否能支持该题目，先跑实验，不直接写论文。

建议不要从原 5 个大批次里抽单个目录硬续跑，容易出现 topic index 对不上。更稳的做法是把筛选出的 1-2 个题目单独放入新文件，例如：

```bash
topics_pilot.txt
```

运行到 `Stage12`：

```bash
AUTORESEARCHCLAW_MAX_PARALLEL=1 \
AUTORESEARCHCLAW_HITL_MODE=co-pilot \
./run_codex_copilot_batch.sh topics_pilot.txt --to-stage EXPERIMENT_RUN
```

pilot 阶段审计：

```bash
scripts/audit_researchclaw_batch.py "$ROOT" --prefix <pilot_prefix> --profile pilot
```

`Stage12` 通过标准：

- `stage-12/runs/run-1.json` 的 `status=completed`
- `stage-12/runs/results.json` 存在
- metrics 非空
- 没有 synthetic/random fallback
- 模型没有明显数据泄漏
- 结果方向、效应大小、指标合理
- 人工确认值得继续写作

未通过时，停止，不进入论文阶段。

## 7. 第三阶段：Stage13-23 完整论文流程

只有 `Stage12` pilot 通过后，才允许继续完整流程。

续跑命令：

```bash
AUTORESEARCHCLAW_MAX_PARALLEL=1 \
AUTORESEARCHCLAW_HITL_MODE=co-pilot \
./run_codex_resume_batch.sh topics_pilot.txt <pilot_prefix>
```

完整审计：

```bash
scripts/audit_researchclaw_batch.py "$ROOT" --prefix <pilot_prefix> --profile full --quality-threshold 7
```

full audit 通过标准：

- `pipeline_summary.json` 不是 `degraded=true`
- `Stage12` 实验成功
- `Stage20` 质量分建议大于等于 7
- `verification_report.json` 正常
- `references_verified.bib` 不是异常小文件
- 论文表格数值和 `results.json` 一致
- 没有“截断、数值不一致、不可采信、N/A 关键字段”等风险词
- 人工复核方法、结果、图表、引用

未通过时，不能作为可用论文，只能作为调试材料。

## 8. 运行中监控

查看进程：

```bash
pgrep -fl 'run_codex|researchclaw run|acpx|codex-acp'
```

查看日志：

```bash
tail -n 80 <run_dir>/run.log
tail -n 80 <run_dir>/resume-*.log
```

查看关键状态：

```bash
cat <run_dir>/pipeline_summary.json
cat <run_dir>/stage-12/runs/run-1.json
cat <run_dir>/stage-20/quality_report.json
```

重点关注：

- 当前 stage
- 是否出现 `ACP prompt failed`
- 是否出现 `degraded=true`
- `Stage12` 是否真的 completed
- metrics 是否为空
- `Stage20` 质量分是否低
- 引用文件是否异常小

## 9. 常见失败处理

### ACP prompt failed

处理方式：

- 降低并发到 1
- 换新 session 续跑
- 确认无旧 `codex-acp` 残留
- 不要直接相信恢复后的论文，必须重新跑 audit

### Stage12 failed

处理方式：

- 不继续写论文
- 检查代码是否读到真实数据
- 检查变量名、路径、缺失、结局定义
- 修复后重新 pilot

### degraded=true

处理方式：

- 不作为可用论文
- 只能作为调试材料
- 需要人工修复或重跑

### 引用文件异常小

处理方式：

- 视为 full audit 失败
- 不能用于正式稿

## 10. 并发建议

当前 16GB M4 机器建议：

| 阶段 | 推荐并发 |
|---|---:|
| Stage01-09 选题筛选 | 2 稳，3 勉强 |
| Stage10-12 真实数据 pilot | 1-2 |
| Stage13-23 完整论文流程 | 1 |

正式数据 pilot 和最终论文阶段建议都用并发 1。

## 11. 当前优先题目

本轮 5 个题目中，优先进入真实数据 pilot 的是：

```text
中心性肥胖人群中，支链氨基酸与 T2D 发病风险：是否独立于胰岛素抵抗替代指标？
```

原因：

- 它是本轮唯一通过 `pilot` 审计的题目
- 研究问题聚焦
- 数据需求相对可控
- 更适合作为体检队列或 UKB 小样本 pilot

注意：它仍不能直接作为最终论文，必须接入真实数据后重新跑 `Stage12`。

## 12. 最终判断

旧策略：

```text
批量跑完整 AutoResearchClaw，直接产出最终论文
```

不可靠。

新策略：

```text
Stage09 选题筛选 -> Stage12 真实数据 pilot -> full audit -> 人工分析/精修
```

作为正式运行范式更稳。

最终原则：

```text
pipeline done 不等于科学结果可信。
只有 audit 通过 + 人工复核通过，才允许进入正式分析和写作。
```
