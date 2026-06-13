# TASK: Laser-Sensor-Mount-Agent 项目收尾与最终交付

版本：v2.0
状态：Active
最后更新：2026.6.13

---

你现在是：

Senior Principal Software Engineer + DevOps / Security Reviewer + AI System Auditor

---

## 项目状态（基于真实仓库）

**项目：** Laser-Sensor-Mount-Agent
**技术栈：** Python 3.13 / FastAPI / SQLite / SQLAlchemy / Pydantic / FPDF2 / OpenAI SDK
**AI 模型：** DeepSeek V4-flash（文本）+ Doubao Seedream 4.5（图片）
**测试：** 161 passed, 0 failed
**Git：** main 分支，15 个本地 commit 待 push
**虚拟环境：** .venv/ (Python 3.13.9)
**Docker：** 未创建

---

## ⚠️ 核心原则

**Think First. Act Later.**

禁止：直接改代码、大规模重构、未审查就部署、跳过分析直接输出结论
必须：先审查全项目 → 再给报告 → 再执行改动（如必要）

---

## Phase 1 — Git 清理

- [x] `.gitignore` 已完善（排除测试文件、BOM 数据、工具目录）
- [x] 过时审计文档已移至 `docs/archive/`
- [ ] 8 个 docs 删除未 staged → 需 commit
- [ ] `README.md` 需创建

---

## Phase 2 — 代码完整性

### 2.1 核心闭环

```
STEP 上传 → STEP Parser → ProductGraph → DraftProcessGraph
→ 工程师审核 → ApprovedProcessGraph → AssemblyInstruction
→ 图片生成（参考图 + AI 生图）→ PDF 导出
```

- [x] STEP → ProductGraph：真实 ISO 10303-21 解析器
- [x] ProductGraph → DraftProcessGraph：规则引擎 + LLM
- [x] DraftProcessGraph → ApprovedProcessGraph：三阶段审核
- [x] 图片生成：参考图 + AI（三种模式可选）
- [x] PDF 导出：FPDF2 + CJK 字体 + 图片嵌入
- [x] 前端 SPA：5 步工作流 + 三阶段审核 UI

### 2.2 三种图片生成模式

| 模式 | DeepSeek | Seedream | 说明 |
|------|----------|----------|------|
| 对比图 | ❌ | ✅ 规则 Prompt | 参考图 + AI 图并排 |
| 仅参考图 | ❌ | ❌ | 只有线框参考图 |
| 文本加生图 | ✅ | ✅ LLM Prompt | DeepSeek 生成 Prompt → AI 生图 |

### 2.3 API 端点

Contract 端点（10 个）+ 扩展端点（8 个）= 共 18 个

---

## Phase 3 — 测试体系

- [x] Contract Test: 20 个
- [x] Unit Test: 119 个
- [x] Integration Test: 17 个
- [x] E2E Test: 17 个
- [x] 总计: 161 passed, 0 failed

---

## Phase 4 — 文档完整性

- [x] `05_CONTRACT.md`：API 契约（权威来源）
- [x] `03_ARCHITECTURE.md`：系统架构
- [x] `07_EPICS.md`：史诗定义
- [x] `PROJECT_STATUS.md`：项目状态 v4.0
- [x] `PROJECT_CHECKLIST.md`：收尾清单（本文件）
- [ ] `README.md`：项目说明（待创建）

---

## Phase 5 — 部署

### 5.1 Docker（待创建）

- [ ] Dockerfile：python:3.13-slim + requirements
- [ ] docker-compose.yml：backend + volumes

### 5.2 本地开发

- [x] .venv/ 虚拟环境
- [x] requirements.txt
- [x] .env.example

---

## Phase 6 — 安全审查

- [ ] API 无认证（MVP 可接受，生产需加鉴权）
- [ ] 文件上传无大小限制（MVP 可接受）
- [x] .env 在 .gitignore 中
- [x] 测试文件不入库

---

## Phase 7 — 下一步（可扩展方向）

1. **Docker 化部署** — 一键启动
2. **API 鉴权** — JWT / API Key
3. **Alembic 数据库迁移** — Schema 版本管理
4. **参考图质量持续优化** — 面填充 + Prompt 模板
5. **Epic-5 知识飞轮** — 工程师审核经验沉淀
6. **多模型支持** — 支持其他 STEP 解析器 / 图片模型
7. **WebSocket 实时进度** — 替代 SSE 流式响应
