# 项目优化计划

版本：v1.0
状态：Accepted
创建日期：2026.6.17
来源：MVP 项目审查

---

## 概述

本文档记录了 MVP 完成后对项目进行全面审查后识别的优化项，按优先级排列。每项包含具体方案和预估改动范围，后续可按需逐项执行。

---

## 🔴 高优先级

### 1. 前端单文件拆分 ✅ 已完成 (2026.6.17)

**现状**：`src/app/static/index.html` 原 852 行，HTML + CSS + JS 全部混在一个文件中。

**执行结果**：已拆分为 3 个文件：

```
src/app/static/
├── index.html      # 纯 HTML 结构（158 行）
├── style.css       # 所有 CSS 样式（75 行）
└── app.js          # 所有 JS 逻辑（610 行）
```

**附带修复**：删除了 `app.js` 中重复的 `zoom-overlay` wheel 事件监听器（原第 765 行和第 775 行重复注册）。

**验证**：161 个测试全部通过。

---

### 2. FastAPI 路由拆分 ✅ 已完成 (2026.6.17)

**现状**：`src/app/main.py` 原 432 行，14 个端点 + 异常处理 + 日志过滤 + 静态文件挂载全部混在一起。

**执行结果**：已拆分为 5 个文件：

```
src/app/
├── main.py                        # 应用入口（58 行）
├── utils/
│   ├── __init__.py
│   └── response.py                # _ok(), _error(), _now()
├── routers/
│   ├── __init__.py
│   ├── step.py                    # STEP 分析 + 产品结构审核（3 个端点）
│   ├── process.py                 # 工艺生成 + 流程审核（4 个端点）
│   ├── instruction.py             # 指导书 + PDF（7 个端点）
│   └── bom.py                     # BOM 管理（4 个端点）
```

**验证**：161 个测试全部通过。

---

### 3. InstructionService 重复代码消除 ✅ 已完成 (2026.6.17)

**执行结果**：抽取了两个私有方法：
- `_prepare_render_context()` — 封装查询 ApprovedProcess、解析 JSON、获取零件数据、获取 STEP 文本
- `_build_and_save_instruction()` — 封装构建 sections、创建 Schema、持久化 ORM

`render()` 从 45 行缩减到 14 行，`render_stream()` 从 85 行缩减到 70 行，消除 ~40 行重复代码。

**验证**：161 个测试全部通过。

---

## 🟡 中优先级

### 4. 端点错误处理装饰器 ✅ 已完成 (2026.6.17)

**执行结果**：创建 `src/app/utils/error_handler.py`，提供 `@handle_service_errors({...})` 装饰器。已应用到 4 个端点：
- `step.py`: `analyze_step`
- `process.py`: `generate_process`, `submit_review`
- `instruction.py`: `render_instruction`, `export_pdf`

消除 ~60 行重复的 try/except/rollback 样板代码。`get_product_graph`、`get_draft_process`、`get_approved_process`、`get_instruction`、`review_instruction`、`download_pdf` 等端点逻辑简单（无 try/except 或仅需一个 if 判断），保持原样更清晰。

**验证**：161 个测试全部通过。

---

### 5. Pillow `getdata()` 弃用迁移 ✅ 已完成 (2026.6.17)

**执行结果**：3 个测试文件中 10 处 `img.getdata()` 全部替换为 `img.get_flattened_data()`。16 个 DeprecationWarning 全部消除（剩余 3 个 warning 来自 FastAPI `on_event`，见优化项 6）。

**验证**：161 个测试全部通过。

---

## 🟢 低优先级（已知技术债）

### 6. 数据库迁移与索引 ✅ 部分完成 (2026.6.17)

已在 `PROJECT_STATUS.md` 中标记为已知技术债：

| # | 项 | 严重度 | 状态 |
|---|---|---|---|
| 1 | FastAPI `on_event` 已弃用 | Low | ✅ 已迁移到 `lifespan` |
| 2 | 无 Alembic 迁移 | Low | ⏸️ 延后（MVP 阶段可接受） |
| 3 | 无显式数据库索引 | Low | ⏸️ 延后（MVP 阶段可接受） |

**已完成**：`on_event("startup")` → `lifespan` 上下文管理器，消除 3 个 DeprecationWarning。当前仅剩 1 个 warning（starlette multipart，第三方库问题）。

**验证**：161 个测试全部通过。

---

## 执行建议

| 顺序 | 优化项 | 预估工时 | 风险 | 收益 |
|------|--------|---------|------|------|
| 1 | 前端单文件拆分 | 30 分钟 | 低 | 高 — 后续前端改动效率翻倍 |
| 2 | 路由拆分 | 45 分钟 | 低 | 高 — 代码组织清晰，可独立测试 |
| 3 | render/render_stream 去重 | 20 分钟 | 低 | 中 — 减少维护负担 |
| 4 | 错误处理装饰器 | 40 分钟 | 中 | 中 — 消除 ~100 行样板 |
| 5 | Pillow getdata 迁移 | 10 分钟 | 极低 | 低 — 消除所有警告 |
| 6 | 技术债清理 | 1-2 小时 | 低 | 中 — 生产就绪 |

**建议执行策略**：按顺序逐项执行，每完成一项运行 `pytest` 确认 161 个测试全部通过后再进入下一项。
