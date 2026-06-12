# Reality Audit Report — 项目实际状态审计

版本：v1.0  
审计日期：2026-06-12  
审计范围：全项目（文档、代码、测试、配置、数据库）

---

## 1. 执行摘要

项目整体处于 **MVP 核心闭环可运行但存在关键缺口** 状态。95 个测试全部通过，10 个 API 端点全部实现，但以下关键功能缺失：

| 缺口 | 严重度 | 影响 |
|---|---|---|
| STEP 解析使用 Mock 数据 | **Critical** | 无法解析真实 STEP 文件 |
| 图片生成未集成 | **High** | PDF 无装配示意图 |
| 前端未开发 | **High** | 工程师无法通过 UI 审核 |
| PDF 导出未人工验证 | **Medium** | 生成质量未知 |

---

## 2. 文档审计

### 2.1 文档清单

| 文档 | 版本 | 状态 | 与实际一致性 |
|---|---|---|---|
| 01_PRD.md | v1.0 | Accepted | ✅ 一致 |
| 02_ADR.md | v1.0 | Accepted | ✅ 一致 |
| 03_ARCHITECTURE.md | v2.0 | Accepted | ⚠️ 部分一致（Review UI 未实现） |
| 04_DOMAIN_MODEL.md | v1.0 | Accepted | ✅ 一致 |
| 05_CONTRACT.md | v1.0 | Accepted | ✅ 一致 |
| 06_DATABASE.md | v1.0 | Accepted | ⚠️ 部分一致（无 Alembic 迁移） |
| 07_EPICS.md | v2.0 | Accepted | ❌ 不一致（Epic 状态与实际不完全匹配） |
| 08_REPOSITORY_RULES.md | v2.0 | Accepted | ✅ 一致 |
| 09_TESTING_STRATEGY.md | v2.0 | Accepted | ✅ 一致 |
| 10_TASK_TEMPLATE.md | v2.0 | Accepted | ✅ 一致 |
| 11_DEFINITION_OF_DONE.md | v2.0 | Accepted | ✅ 一致 |
| PROJECT_STATUS.md | v1.0 | Accepted | ❌ 不一致（Epic 状态需要更新） |
| CLAUDE.md | v2.0 | — | ⚠️ Commit 格式与 08_REPOSITORY_RULES.md 不一致 |

### 2.2 文档问题详情

1. **PROJECT_STATUS.md 过期**: 声称 Epic-4"等待启动"，实际 Epic-4 已完成
2. **CLAUDE.md commit 格式错误**: 第85行写 `<Epic-ID>/<Story-ID> <描述> [Type]`，正确格式应为 `<type>(<scope>): <description>`（见 08_REPOSITORY_RULES.md 第72-73行）
3. **.env.example 存在 bug**: 第14行写 `LLM_API_KEY=your_api_key_here`，应为 `IMAGE_API_KEY=your_api_key_here`
4. **07_EPICS.md 状态不准确**: 声称全部 Epic 完成，但实际存在 PARTIAL 状态

---

## 3. Epic 实际完成状态

### Epic-1: STEP 文件解析与 ProductGraph 生成

| 维度 | 状态 | 详情 |
|---|---|---|
| API | ✅ 完成 | POST /api/v1/step/analyze + GET /api/v1/product-graphs/{id} |
| Service | ⚠️ PARTIAL | StepAnalysisService 使用硬编码 DEMO_PRODUCT_GRAPH，非真实 STEP 解析 |
| Repository | ✅ 完成 | StepFileRepository + ProductGraphRepository |
| Database | ✅ 完成 | step_files + product_graphs 表，含外键与索引 |
| Tests | ✅ 完成 | 8 unit + 3 contract + 3 E2E = 14 tests |
| 真实 STEP | ❌ 未实现 | ILD1x20-100.step (113K行) 存在但不会被解析 |

**判定: PARTIAL** — 核心功能 (STEP→ProductGraph) 使用 Mock 数据，ADR-006 标记为 Critical Risk

### Epic-2: DraftProcessGraph 生成与审核

| 维度 | 状态 | 详情 |
|---|---|---|
| API | ✅ 完成 | 4 endpoints (generate/get/review/get-approved) |
| Service | ✅ 完成 | ProcessGenerationService (规则引擎 + LLM) + ReviewService |
| LLM 集成 | ✅ 完成 | Volcano Engine (DeepSeek), 测试时 template fallback |
| Repository | ✅ 完成 | DraftProcessRepository + ApprovedProcessRepository + ReviewDecisionRepository |
| Database | ✅ 完成 | draft_process_graphs + approved_process_graphs + review_decisions |
| Tests | ✅ 完成 | 9 unit + 8 contract + 5 E2E = 22 tests |
| 领域规则 | ✅ 完成 | 5 条装配规则全部验证通过 |

**判定: COMPLETE**

### Epic-3: ApprovedProcessGraph 与 AssemblyInstruction

| 维度 | 状态 | 详情 |
|---|---|---|
| API | ✅ 完成 | 3 endpoints (render/get/export-pdf) |
| Service | ⚠️ PARTIAL | InstructionService 渲染文字+PDF，但图片生成未集成 |
| Repository | ✅ 完成 | InstructionRepository |
| Database | ✅ 完成 | assembly_instructions 表 |
| PDF 导出 | ✅ 完成 | FPDF2 生成 PDF（文字内容+5 种 Section） |
| 图片生成 | ❌ 未实现 | IMAGE_MODEL/IMAGE_API_KEY 已配置但无调用代码 |
| Tests | ✅ 完成 | 8 unit + 4 contract + 3 E2E = 15 tests |

**判定: PARTIAL** — 图片生成 (DeepSeek→Doubao Seedream) 未集成

### Epic-4: MVP 边界与 Demo

| 维度 | 状态 | 详情 |
|---|---|---|
| E2E 完整链路 | ✅ 完成 | test_complete_pipeline_e2e 通过 |
| MVP 边界验证 | ✅ 完成 | 无知识飞轮/AR/自学习端点暴露 |
| 真实 STEP | ❌ 未用 | 仍用 mock 数据 |
| 前端 | ❌ 未开发 | 无 UI 界面 |

**判定: PARTIAL** — E2E 测试用 Mock 数据通过，但需真实数据验证

### Epic-5: Assembly Knowledge Flywheel

**判定: DEFERRED** — 非 MVP 范围

---

## 4. API 实际状态

### 4.1 端点清单

| # | 端点 | 方法 | 状态 | Contract |
|---|---|---|---|---|
| 1 | /api/v1/step/analyze | POST | ✅ 运行中 | 05_CONTRACT.md §4.1 |
| 2 | /api/v1/product-graphs/{id} | GET | ✅ 运行中 | 05_CONTRACT.md §4.2 |
| 3 | /api/v1/process/generate | POST | ✅ 运行中 | 05_CONTRACT.md §5.1 |
| 4 | /api/v1/process/{id} | GET | ✅ 运行中 | 05_CONTRACT.md §5.2 |
| 5 | /api/v1/process/review | POST | ✅ 运行中 | 05_CONTRACT.md §6.1 |
| 6 | /api/v1/approved-process/{id} | GET | ✅ 运行中 | 05_CONTRACT.md §6.2 |
| 7 | /api/v1/instruction/render | POST | ✅ 运行中 | 05_CONTRACT.md §7.1 |
| 8 | /api/v1/instruction/{id} | GET | ✅ 运行中 | 05_CONTRACT.md §7.2 |
| 9 | /api/v1/instruction/export-pdf | POST | ✅ 运行中 | 05_CONTRACT.md §8.1 |
| 10 | (stub) | — | 0 个 Stub | — |

### 4.2 API 标准响应格式

- 成功: `{"success": true, "data": {...}, "timestamp": "..."}` ✅
- 错误: `{"success": false, "error": {"code": "...", "message": "..."}, "timestamp": "..."}` ✅
- 错误码: STEP_FILE_INVALID, STEP_PARSE_FAILED, PRODUCT_GRAPH_NOT_FOUND, PROCESS_NOT_FOUND, PROCESS_GENERATION_FAILED, REVIEW_REQUIRED, INVALID_REVIEW_ACTION, APPROVED_PROCESS_NOT_FOUND, INSTRUCTION_NOT_FOUND, RENDER_FAILED, PDF_EXPORT_FAILED, INTERNAL_SERVER_ERROR ✅

---

## 5. 数据库实际状态

### 5.1 表清单

| # | 表名 | 列数 | FK | 与 06_DATABASE.md 一致 |
|---|---|---|---|---|
| 1 | step_files | 7 (id, file_name, file_path, file_size, status, created_at, updated_at) | — | ✅ |
| 2 | product_graphs | 6 (id, step_file_id, graph_json, status, created_at, updated_at) | step_files.id | ✅ |
| 3 | draft_process_graphs | 7 (id, product_graph_id, graph_json, status, generated_by, created_at, updated_at) | product_graphs.id | ✅ |
| 4 | review_decisions | 7 (id, process_id, step_id, action, reason, reviewer, created_at) | draft_process_graphs.id | ✅ |
| 5 | approved_process_graphs | 6 (id, draft_process_id, graph_json, approved_by, approved_at, created_at) | draft_process_graphs.id | ✅ |
| 6 | assembly_instructions | 5 (id, approved_process_id, instruction_json, pdf_path, created_at) | approved_process_graphs.id | ✅ |

### 5.2 数据库问题

1. **无 Alembic 迁移**: 06_DATABASE.md §14 要求使用 Alembic，实际使用 `Base.metadata.create_all()` 直接建表
2. **无显式索引**: 06_DATABASE.md §11 要求的 4 个索引未显式创建（SQLite 外键列不会自动建索引）

---

## 6. Domain Model 实际状态

### 6.1 聚合根

| 聚合根 | 定义 | ORM | Schema | Repository | 状态 |
|---|---|---|---|---|---|
| ProductGraph | ✅ | ✅ ProductGraph | ✅ ProductGraphSchema | ✅ ProductGraphRepository | Mock 数据 |
| DraftProcessGraph | ✅ | ✅ DraftProcessGraph | ✅ DraftProcessGraphSchema | ✅ DraftProcessRepository | ✅ |
| ApprovedProcessGraph | ✅ | ✅ ApprovedProcessGraph | ✅ ApprovedProcessGraphSchema | ✅ ApprovedProcessRepository | ✅ |
| AssemblyInstruction | ✅ | ✅ AssemblyInstruction | ✅ AssemblyInstructionSchema | ✅ InstructionRepository | ✅ |
| ReviewDecision | ✅ (值对象) | ✅ ReviewDecision | ✅ ReviewDecisionSchema | ✅ ReviewDecisionRepository | ✅ |

### 6.2 领域规则验证

| 规则 | 代码位置 | 测试验证 |
|---|---|---|
| Parent Before Child | process_generation_service.py NODE_TYPE_PRIORITY | ✅ |
| Base First | NODE_TYPE_PRIORITY["base"]=1 | ✅ test_base_plate_is_first_step |
| Fastener Last | NODE_TYPE_PRIORITY["screw"]=4 | ✅ |
| Washer Follow Fastener | NODE_TYPE_PRIORITY["washer"]=5 | ✅ test_washer_after_screw |
| Sensor After Mount | NODE_TYPE_PRIORITY priority ordering | ✅ test_sensor_after_bracket |

---

## 7. 测试覆盖状态

### 7.1 测试统计

| 测试类型 | 数量 | 通过 | 失败 | 覆盖 Epic |
|---|---|---|---|---|
| Contract | 20 | 20 | 0 | Epic-1 ~ Epic-3 |
| Unit | 36 | 36 | 0 | Epic-1 ~ Epic-3 |
| Integration | 17 | 17 | 0 | Epic-1 ~ Epic-3 |
| E2E | 22 | 22 | 0 | Epic-1 ~ Epic-4 |
| **总计** | **95** | **95** | **0** | — |

### 7.2 测试缺失项

| 缺失项 | 说明 |
|---|---|
| 无真实 STEP 解析测试 | 因为解析器未实现 |
| 无图片生成测试 | 因为功能未集成 |
| 无前端测试 | 因为前端未开发 |
| 无 PDF 内容验证测试 | 只验证文件存在，不验证内容 |

---

## 8. 技术债清单

| # | 技术债 | 严重度 | 位置 |
|---|---|---|---|
| 1 | STEP 解析 Mock | Critical | step_analysis_service.py:32-52 |
| 2 | 图片生成未集成 | High | instruction_service.py |
| 3 | 前端未开发 | High | — |
| 4 | .env.example IMAGE_API_KEY 错误 | Medium | .env.example:14 |
| 5 | CLAUDE.md commit 格式过时 | Medium | CLAUDE.md:85 |
| 6 | FastAPI on_event 已弃用 | Low | main.py:67 |
| 7 | 无 Alembic 迁移 | Low | database.py |
| 8 | 无显式数据库索引 | Low | orm.py |
| 9 | pdf_path 更新绕过 Repository | Low | instruction_service.py:180-181 |
| 10 | PROJECT_STATUS.md 状态过时 | Medium | docs/PROJECT_STATUS.md |

---

## 9. Epic 判定汇总

| Epic | 名称 | 判定 | 关键缺口 |
|---|---|---|---|
| Epic-1 | STEP 文件解析与 ProductGraph 生成 | **PARTIAL** | STEP 解析 Mock |
| Epic-2 | DraftProcessGraph 生成与审核 | **COMPLETE** | — |
| Epic-3 | ApprovedProcessGraph 与 AssemblyInstruction | **PARTIAL** | 图片生成未集成 |
| Epic-4 | MVP 边界与 Demo | **PARTIAL** | 真实 STEP + 前端 |
| Epic-5 | Assembly Knowledge Flywheel | **DEFERRED** | 非 MVP |

---

## 10. 建议优先级

| 优先级 | 行动 | Epic |
|---|---|---|
| P0 | 实现真实 STEP 文件解析器 | Epic-1 |
| P1 | 集成图片生成 (DeepSeek→Doubao) | Epic-3 |
| P2 | 开发前端 UI | Epic-4 |
| P3 | 修复 .env.example bug | — |
| P3 | 更新 PROJECT_STATUS.md, CLAUDE.md, 07_EPICS.md | — |
| P4 | 添加 Alembic 迁移 | — |
| P4 | 添加数据库索引 | — |
