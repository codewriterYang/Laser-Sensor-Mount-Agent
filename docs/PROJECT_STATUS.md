# PROJECT_STATUS — 项目状态追踪

版本：v4.0
状态：Accepted
最后更新：2026.6.13

---

## 1. 当前版本

| 项目 | 值 |
|---|---|
| **文档版本** | v4.0 |
| **应用版本** | v0.6.0 |
| **开发阶段** | Epic-1~4 MVP 核心闭环完成 + 渲染器重构 + 图片模式重构 |

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

## 3. 本轮交付成果 (Phase 5: 图片模式重构 + 收尾)

### 三种图片生成模式（重新定义）
- **对比图**（reference_only）：线框参考图 + AI 生图（规则 Prompt，不接 DeepSeek）
- **仅参考图**：只有线框参考图，无 AI
- **文本加生图**（text_and_image）：DeepSeek 生成 Prompt → Seedream img2img

### LLM Prompt 生成
- `llm_service.py` 新增 `generate_image_prompt` 方法
- `image_service.py` 的 `_generate_ai_bytes` 支持 `use_llm` 参数
- 仅 `text_and_image` 模式使用 DeepSeek，其他模式用规则模板

### 渲染器改进
- 固定等轴测视角 `(25°, -30°)`
- 缩放基于可见零件
- 面填充（半透明体积感）
- STEP 颜色直接提取（不依赖 part_info 匹配）

### 前端修复
- BOM 刷新 loading 状态
- 模式选择器渲染中锁定
- 审核完成消息去重（三阶段统一单条 badge）
- Lightbox 鼠标滚轮缩放

### 文档清理
- 8 个过时审计文档归档到 `docs/archive/`
- `PROJECT_CHECKLIST.md` 项目收尾清单

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

## 3. 本轮交付成果 (Phase 4: 渲染器重构)

### reference_renderer 重构
- **文件**：`src/app/services/reference_renderer.py`
- **改进**：
  - 固定等轴测视角 `(25°, -30°)`，所有步骤一致
  - 缩放基于可见零件包围盒，零件占画布主体
  - 全局坐标归位，零件保持 STEP 中的真实位置
  - per-part 颜色支持（从 STEP COLOUR_RGB 自动提取）
  - 修复 x/y 坐标混算 bug
  - 颜色值 clamp 到 `[0, 255]` 防止极端角度溢出

### image_service 改进
- **文件**：`src/app/services/image_service.py`
- **改进**：
  - 直接从 STEP 文件提取颜色（不依赖 part_info 匹配）
  - 步骤编号改用循环索引（防止审核后编号不连续）

### 前端改进
- **文件**：src/app/static/index.html
- **改进**：
  - BOM 刷新按钮 loading 状态（⏳→✅→恢复）
  - 上传时 loading 反馈（半透明+禁止点击）
  - 模式选择器渲染中锁定，完成后恢复
  - Lightbox 鼠标滚轮缩放
  - 修复 BOM stats `custom_files` 访问 TypeError

### 日志优化
- **文件**：src/app/main.py
- **改进**：过滤 favicon.ico、chrome.devtools.json 等噪音 access log

---

## 3. 历史交付成果 (Phase 3: MVP 核心闭环)

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
| **Unit Test** | 119 | Service + Renderer + BOM + Quality + Multiview |
| **Integration Test** | 17 | 全部 6 个 Repository |
| **E2E Test** | 17 | Epic-1/2/3/4 完整链路 |
| **总计** | **161** | **0 failed, 0 skipped** |

**E2E 验证**：使用真实 ILD1x20-100.step 完成完整链路 → PDF 输出成功。

---

## 7. 文档一致性状态

| 文档 | 状态 |
|---|---|
| 01_PRD.md ↔ 实际 | ✅ |
| 03_ARCHITECTURE.md ↔ 实际 | ✅ |
| 05_CONTRACT.md ↔ 实际 | ✅ |
| 06_DATABASE.md ↔ 实际 | ✅ |
| 07_EPICS.md ↔ PROJECT_STATUS.md | ✅ |
| PROJECT_STATUS.md | ✅ v3.0 已更新 |
| docs/archive/ | ✅ 8 个过时审计文档已归档 |

---

## 8. 技术债（已知）

| # | 项 | 严重度 |
|---|---|---|
| 1 | FastAPI `on_event` 已弃用 | Low |
| 2 | 无 Alembic 迁移 | Low |
| 3 | 无显式数据库索引 | Low |
