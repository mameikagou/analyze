# GSD 路径指令速查

GSD 标准流程：**Discuss → Plan → Execute → Verify**

---

## 1. 调研阶段（Discuss / Research）

| 指令 | 用途 |
|------|------|
| `/gsd-discuss-phase` | **首选**。Socratic 式提问，把模糊需求拆成具体任务、澄清边界条件。适合"想做但还没想清楚"的场景。 |
| `/gsd-research-phase` | 已明确目标，需要调研技术方案（如选型、架构设计）。产出 `RESEARCH.md` 供后续 plan 使用。 |

> 建议：除非调研已经很清楚，否则先用 `discuss`，能让 plan 阶段少走很多弯路。

---

## 2. 生成计划（Plan）

| 指令 | 用途 |
|------|------|
| `/gsd-plan-phase` | 根据 discuss / research 的产出，生成 `PLAN.md`。包含任务拆解、依赖关系、验证标准、执行顺序。 |

> 执行后会输出到 `.planning/phases/{编号}-{名称}/PLAN.md`。

---

## 3. 执行与进度更新（Execute）

| 指令 | 用途 |
|------|------|
| `/gsd-execute-phase` | **全量执行**。一次性跑完当前 phase 的所有 plan，适合专心编码的时段。 |
| `/gsd-next` | **单步推进**。只执行 plan 里的下一个任务，适合碎片化工作流。 |
| `/gsd-pause-work` | 临时中断，保存当前执行上下文。 |
| `/gsd-resume-work` | 恢复之前 `pause-work` 保存的上下文，继续执行。 |

> 执行过程中，GSD 会自动在 `PLAN.md` 中更新任务状态（`[x]` 标记已完成）。

---

## 4. 更新计划本身（Plan 变更）

执行中发现计划有遗漏、顺序不对、需求变更时：

| 方式 | 适用场景 |
|------|---------|
| **直接编辑 `PLAN.md`** | 小改：增删任务、调整顺序、补充说明。 |
| **重新跑 `/gsd-plan-phase`** | 大改：需求推翻、前期假设不成立、需要重新生成完整计划。 |

---

## 5. 其他高频指令

| 指令 | 用途 |
|------|------|
| `/gsd-progress` | 查看当前项目整体进度、活跃 phase、待办状态。 |
| `/gsd-check-todos` | 列出所有待办任务，选一个开始执行。 |
| `/gsd-code-review` | 对当前 phase 的代码变更做审查，产出 `REVIEW.md`。 |
| `/gsd-verify-work` | 执行完成后验证功能是否符合预期（对话式 UAT）。 |
| `/gsd-session-report` | 生成会话总结报告（含 token 估算、完成任务、代码变更摘要）。 |

---

## 一句话流程

> `discuss` 聊清楚 → `plan-phase` 出计划 → `execute-phase` / `next` 一步步做 → 计划变了改 `PLAN.md` 或重跑 `plan-phase`。
