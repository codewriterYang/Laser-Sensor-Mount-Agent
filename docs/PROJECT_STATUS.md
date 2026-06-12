# PROJECT_STATUS — 项目状态追踪

版本：v1.0
状态：Accepted
最后更新：2026.6.12

---

## 1. 当前版本

| 项目 | 值 |
|---|---|
| **文档版本** | v2.0 |
| **应用版本** | v0.2.0 |
| **开发阶段** | Epic-2 完成，准备进入 Epic-3 |

---

## 2. Epic 状态总览

| Epic | 名称 | 状态 | 完成日期 |
|---|---|---|---|
| **Epic-1** | STEP 文件解析与 ProductGraph 生成 | ✅ Completed | 2026.6.11 |
| **Epic-2** | DraftProcessGraph 生成与审核 | ✅ Completed | 2026.6.12 |
| **Epic-3** | ApprovedProcessGraph 与 AssemblyInstruction | 🔲 Pending | — |
| **Epic-4** | MVP 边界与 Demo | 🔲 Pending | — |
| **Epic-5** | Assembly Knowledge Flywheel | 🔲 Pending（非 MVP） | — |

---

## 3. 已完成 Epic

### Epic-1：STEP 文件解析与 ProductGraph 生成

**完成日期**：2026.6.11
**状态**：Completed

**交付成果**：

| 层 | 文件 | 说明 |
|---|---|---|
| API | `src/app/main.py` | POST /api/v1/step/analyze + GET /api/v1/product-graphs/{id} |
| Service | `src/app/services/step_analysis_service.py` | MVP Demo ProductGraph + 状态机 |
| Repository | `src/app/repositories/step_file_repository.py` | StepFile CRUD + 状态管理 |
| Repository | `src/app/repositories/product_graph_repository.py` | ProductGraph CRUD + 状态管理 |
| Schema | `src/app/models/schemas.py` | 完整 Pydantic Schema（匹配 05_CONTRACT.md） |
| ORM | `src/app/models/orm.py` | 6 张表 SQLAlchemy 模型 |
| Database | `src/app/database.py` | SQLite 引擎 + Session 工厂 |

**E2E 验证结果**：

```
POST /api/v1/step/analyze → 200
  stepFileId: <uuid>
  productGraphId: <uuid>
  status: parsed

GET /api/v1/product-graphs/{id} → 200
  nodes: 6（1 assembly + 5 parts）
  edges: 8（contains / attached_to / fastened_by）

GET /api/v1/product-graphs/dead → 404
  error: PRODUCT_GRAPH_NOT_FOUND
```

### Epic-2：DraftProcessGraph 生成与审核

**完成日期**：2026.6.12
**状态**：Completed

**交付成果**：

| 层 | 文件 | 说明 |
|---|---|---|
| API | `src/app/main.py` | 4 个 Epic-2 端点（generate/get process + review/get approved） |
| Service | `src/app/services/process_generation_service.py` | 规则引擎（5 条装配规则）+ 步骤生成 |
| Service | `src/app/services/review_service.py` | 审核处理（accept/modify/delete/insert） |
| Repository | `src/app/repositories/draft_process_repository.py` | DraftProcessGraph CRUD |
| Repository | `src/app/repositories/approved_process_repository.py` | ApprovedProcessGraph CRUD |
| Repository | `src/app/repositories/review_decision_repository.py` | ReviewDecision CRUD |

---

## 4. 进行中 Epic

_当前无进行中 Epic。Epic-2 已完成，Epic-3 等待启动。_

---

## 5. 待开发 Epic

### Epic-3：ApprovedProcessGraph 与 AssemblyInstruction
- Feature-1：ApprovedProcessGraph 生成
- Feature-2：Instruction Service（PDF 渲染）
- 预计 Task 数：13

### Epic-4：MVP 边界与 Demo
- Feature-1：End-to-End Workflow 验证
- Feature-2：MVP Scope 验证
- 预计 Task 数：9

### Epic-5：Assembly Knowledge Flywheel（非 MVP）
- 预计 Task 数：15

---

## 6. 最新测试结果

**测试执行时间**：2026.6.12

| 测试类型 | 通过 | 跳过 | 失败 | 说明 |
|---|---|---|---|---|
| **Contract Test** | 15 | 5 | 0 | 跳过项为 Epic-3 端点（501） |
| **Unit Test** | 28 | 0 | 0 | Epic-1 + Epic-2 全部 Service |
| **Integration Test** | 14 | 0 | 0 | 全部 Repository CRUD |
| **E2E Test** | 8 | 0 | 0 | Epic-1 + Epic-2 完整链路 |
| **总计** | **69** | **5** | **0** | |

**命令**：

```bash
python -m pytest src/tests/ -v
# 69 passed, 5 skipped in 3.79s
```

---

## 7. 下一步行动

| 优先级 | 行动 | 说明 |
|---|---|---|
| **P0** | 启动 Epic-3 Analysis | 对照 Architecture / Contract / Domain 分析 Epic-3 范围 |
| **P0** | 输出 Epic-3 Implementation Plan | 按 Feature → Story → Task 拆解 |
| **P1** | 实现 ApprovedProcessGraph | Feature-1：正式流程生成 |
| **P1** | 实现 Instruction Service | Feature-2：PDF 渲染 |
| **P2** | 更新 PROJECT_STATUS.md | Epic-3 启动后同步更新 |

---

## 8. 文档一致性状态

| 检查项 | 状态 |
|---|---|
| CLAUDE.md ↔ PROJECT_STATUS.md ↔ 07_EPICS.md | ✅ 一致 |
| Epic-1 状态：三份文档均为 Completed | ✅ |
| Epic-2 状态：三份文档均为 Completed | ✅ |
| 开发流程：三份文档均为 Epic-Driven | ✅ |
| 提交粒度：Conventional Commits | ✅ |
