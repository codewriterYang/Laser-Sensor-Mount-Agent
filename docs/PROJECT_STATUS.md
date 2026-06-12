# PROJECT_STATUS — 项目状态追踪

版本：v2.0
状态：Accepted
最后更新：2026.6.12

---

## 1. 当前版本

| 项目 | 值 |
|---|---|
| **文档版本** | v2.0 |
| **应用版本** | v0.4.0 |
| **开发阶段** | Epic-1~4 MVP 核心闭环完成 |

---

## 2. Epic 状态总览

| Epic | 名称 | 实际判定 | 完成日期 |
|---|---|---|---|
| **Epic-1** | STEP 文件解析与 ProductGraph 生成 | ✅ COMPLETE | 2026.6.12 |
| **Epic-2** | DraftProcessGraph 生成与审核 | ✅ COMPLETE | 2026.6.12 |
| **Epic-3** | ApprovedProcessGraph 与 AssemblyInstruction | ✅ COMPLETE | 2026.6.12 |
| **Epic-4** | MVP 边界与 Demo | ✅ COMPLETE | 2026.6.12 |
| **Epic-5** | Assembly Knowledge Flywheel | ⏸️ Deferred（非 MVP） | — |

---

## 3. 本轮交付成果 (Phase 3: MVP 核心闭环)

### 真实 STEP 解析器
- **文件**：`src/app/services/step_parser.py`
- **功能**：ISO 10303-21 实体解析，提取 PRODUCT 名称/几何体数量/装配检测
- **验证**：成功解析 ILD1x20-100.step（10 个 MANIFOLD_SOLID_BREP 几何体）
- **集成**：`StepAnalysisService.analyze()` 使用真实解析器

### 图片生成服务
- **文件**：`src/app/services/image_service.py`
- **功能**：Doubao Seedream 4.5 图像生成（OpenAI-compatible API）
- **集成**：`InstructionService` 为每步生成装配示意图，嵌入 PDF

### 前端 SPA
- **文件**：`src/app/static/index.html`
- **功能**：5 步工作流 — Upload → ProductGraph → DraftProcess → Review → PDF
- **路由**：`GET /` → 前端页面，`/static` → 静态资源

---

## 4. API 端点清单（全部 10 个）

| # | 端点 | 方法 | 状态 |
|---|---|---|---|
| 1 | /api/v1/step/analyze | POST | ✅ |
| 2 | /api/v1/product-graphs/{id} | GET | ✅ |
| 3 | /api/v1/process/generate | POST | ✅ |
| 4 | /api/v1/process/{id} | GET | ✅ |
| 5 | /api/v1/process/review | POST | ✅ |
| 6 | /api/v1/approved-process/{id} | GET | ✅ |
| 7 | /api/v1/instruction/render | POST | ✅ |
| 8 | /api/v1/instruction/{id} | GET | ✅ |
| 9 | /api/v1/instruction/export-pdf | POST | ✅ |
| 10 | / (前端 SPA) | GET | ✅ |

---

## 5. 工程交付物

| 层 | 文件 | 说明 |
|---|---|---|
| API | `src/app/main.py` | FastAPI 应用 + 静态文件服务 |
| Step Parser | `src/app/services/step_parser.py` | **NEW** 真实 ISO 10303-21 解析器 |
| Step Analysis | `src/app/services/step_analysis_service.py` | 集成真实解析器 |
| Process Gen | `src/app/services/process_generation_service.py` | 规则引擎 + LLM |
| LLM | `src/app/services/llm_service.py` | DeepSeek 文本生成 |
| Review | `src/app/services/review_service.py` | 工程师审核处理 |
| Instruction | `src/app/services/instruction_service.py` | 渲染 + 图片 + PDF |
| Image | `src/app/services/image_service.py` | **NEW** Doubao 图片生成 |
| Frontend | `src/app/static/index.html` | **NEW** SPA 前端 |
| ORM | `src/app/models/orm.py` | 6 张表 SQLAlchemy |
| Schema | `src/app/models/schemas.py` | Pydantic（SectionSchema 新增 imagePath） |
| Repositories | `src/app/repositories/` (6 files) | CRUD 持久化 |
| Config | `src/app/config.py` | LLM + Image 配置 |

---

## 6. 测试结果

| 测试类型 | 通过 | 说明 |
|---|---|---|
| **Contract Test** | 20 | Epic-1~3 全部端点 |
| **Unit Test** | 43 | Epic-1/2/3 Service + **StepParser (7 new)** |
| **Integration Test** | 17 | 全部 6 个 Repository |
| **E2E Test** | 22 | Epic-1/2/3/4 完整链路 |
| **总计** | **102** | **0 failed, 0 skipped** |

**E2E 验证**：使用真实 ILD1x20-100.step 完成完整链路 → PDF 输出成功。

---

## 7. 文档一致性状态

| 文档 | 状态 |
|---|---|
| 01_PRD.md ↔ 实际 | ✅ |
| 03_ARCHITECTURE.md ↔ 实际 | ✅（Review UI 已实现为前端 SPA） |
| 05_CONTRACT.md ↔ 实际 | ✅ |
| 06_DATABASE.md ↔ 实际 | ✅ |
| 07_EPICS.md ↔ PROJECT_STATUS.md | ✅ |
| CLAUDE.md commit 格式 | ✅ 已修正 |
| .env.example | ✅ 已修正 IMAGE_API_KEY |

---

## 8. 技术债（已知）

| # | 项 | 严重度 |
|---|---|---|
| 1 | FastAPI `on_event` 已弃用 | Low |
| 2 | 无 Alembic 迁移 | Low |
| 3 | 无显式数据库索引 | Low |
