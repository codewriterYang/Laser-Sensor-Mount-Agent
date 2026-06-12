# Gap Analysis — 文档设计 vs 实际实现偏差分析

版本：v1.0  
分析日期：2026-06-12  

---

## 1. 偏差总览

| Epic | 设计状态 | 实际判定 | 偏差级别 |
|---|---|---|---|
| Epic-1 | Completed | **PARTIAL** | 🔴 Critical |
| Epic-2 | Completed | **COMPLETE** | 🟢 无偏差 |
| Epic-3 | Completed | **PARTIAL** | 🟡 High |
| Epic-4 | Completed | **PARTIAL** | 🟡 High |
| Epic-5 | Deferred | **DEFERRED** | 🟢 一致 |

---

## 2. Epic-1 偏差分析: STEP 文件解析与 ProductGraph 生成

### 2.1 核心偏差

| 设计 (03_ARCHITECTURE.md §1.2) | 实际实现 | 偏差 |
|---|---|---|
| STEP Parser 解析 STEP 文件 | `DEMO_PRODUCT_GRAPH` 硬编码常量 | **Mock 替代了真实解析** |
| 从 STEP 提取零件、材料、结构关系 | 返回固定的 6 节点 8 边 ProductGraph | **不读取任何 STEP 内容** |

### 2.2 偏差影响

- **ADR-006**: "STEP 解析是项目最大技术风险" — 此风险未解决
- 真实文件 ILD1x20-100.step (113K 行) 被上传但内容不会被解析
- 后续 Epic 依赖的 ProductGraph 来源虚假，整条链路验证无意义

### 2.3 缺失功能

| 07_EPICS.md 声明的 Task | 实际状态 |
|---|---|
| Feature-2 / Story-1 / Task-1: 解析节点与边 | ❌ 使用 Mock |
| Feature-2 / Story-1 / Task-4: 异常处理 (failed) | ⚠️ 有代码但只处理上传失败，非解析失败 |

### 2.4 判定

**PARTIAL** — 假设 ProductGraph 已可用，但实际 STEP→ProductGraph 的转换未实现。这是整个 MVP 的根基问题。

---

## 3. Epic-2 偏差分析: DraftProcessGraph 生成与审核

### 3.1 核心偏差

无重大偏差。所有 Feature/Story/Task 均已实现。

### 3.2 实现验证

| 07_EPICS.md 声明的 Task | 实际状态 |
|---|---|
| Feature-1 / Story-1 / Task-1: 规则引擎 | ✅ NODE_TYPE_PRIORITY + _order_by_rules() |
| Feature-1 / Story-1 / Task-2: LLM 生成步骤文本 | ✅ LLMService._llm_step() |
| Feature-1 / Story-1 / Task-3: 组合生成 DraftProcessGraph JSON | ✅ _generate_steps() |
| Feature-1 / Story-1 / Task-4: 存储 DraftProcessGraph | ✅ DraftProcessRepository |
| Feature-1 / Story-1 / Task-5: 状态管理 | ✅ draft → reviewing |
| Feature-2 / Story-1 / Task-1-4: 审核全部功能 | ✅ accept/modify/delete/insert |
| Tests: 22 tests | ✅ 全部通过 |

### 3.3 判定

**COMPLETE** — 与设计文档完全一致。

---

## 4. Epic-3 偏差分析: ApprovedProcessGraph 与 AssemblyInstruction

### 4.1 核心偏差

| 设计 (07_EPICS.md + 03_ARCHITECTURE.md) | 实际实现 | 偏差 |
|---|---|---|
| Feature-2 / Story-1 / Task-2: 生成图文 Section | 无图片生成代码 | **图片生成未集成** |
| config.py: IMAGE_MODEL 已配置 | 无调用 IMAGE_API 的代码 | **配置存在但未使用** |

### 4.2 实现验证

| 07_EPICS.md 声明的 Task | 实际状态 |
|---|---|
| Feature-1 / Story-1: 全部 5 个 Task | ✅ ApprovedProcessGraph 生成完整 |
| Feature-2 / Story-1 / Task-1: 渲染步骤文本 | ✅ _build_sections() |
| Feature-2 / Story-1 / Task-2: 生成图文 Section | ❌ 无图片 |
| Feature-2 / Story-1 / Task-3: 生成 PDF | ✅ FPDF2 文字 PDF |
| Feature-2 / Story-1 / Task-4: 存储 PDF 路径 | ✅ InstructionRepository |
| Feature-2 / Story-1 / Task-5: 返回下载链接 | ⚠️ 返回路径但无下载端点 |
| Feature-2 / Story-2: 异常处理 3 个 Task | ⚠️ 有基础错误处理，无重试逻辑 |

### 4.3 判定

**PARTIAL** — 文字 PDF 可生成，但缺少图片。

---

## 5. Epic-4 偏差分析: MVP 边界与 Demo

### 5.1 核心偏差

| 设计 | 实际 | 偏差 |
|---|---|---|
| 03_ARCHITECTURE.md §1.1: Review UI | 无前端代码 | **前端未开发** |
| 端到端流程用 Demo STEP | 测试用 Mock 数据通过 | **非真实 STEP 验证** |

### 5.2 缺失功能

| 缺失项 | 影响 |
|---|---|
| Review UI (展示层) | 工程师无法通过浏览器审核流程 |
| 真实 STEP 端到端验证 | 完整链路未在真实数据上验证 |
| PDF 人工验证 | PDF 质量未评估 |

### 5.3 判定

**PARTIAL** — E2E 测试通过但使用 Mock 数据，前端缺失。

---

## 6. 文档偏差汇总

### 6.1 需要更新的文档

| 文档 | 问题 | 修复 |
|---|---|---|
| PROJECT_STATUS.md | 声称 Epic-4 "等待启动" | 更新为 "PARTIAL"，标注真实状态 |
| 07_EPICS.md | 声称全部 Completed | 更新 Epic 状态判定 |
| CLAUDE.md | Commit 格式使用旧版 | 改为 `<type>(<scope>): <description>` |
| .env.example | 第 14 行 `LLM_API_KEY` 应为 `IMAGE_API_KEY` | 修正 key 名称 |

---

## 7. 风险矩阵

| 风险 | 可能性 | 影响 | 级别 |
|---|---|---|---|
| STEP 解析无法实现 | Medium | Critical — 整个 MVP 无真实输入 | 🔴 |
| 图片生成 API 不可用 | Low | High — PDF 质量降低 | 🟡 |
| 前端开发超预期 | Medium | Medium — 可仅用 API 演示 | 🟡 |
| 真实 STEP 与 Mock 结构不兼容 | High | High — 下游逻辑需大改 | 🟡 |

---

## 8. 下一步行动

| 优先级 | 行动 | 预估工时 |
|---|---|---|
| **P0** | 实现真实 STEP 文件解析器 (PE 级) | 2-3 天 |
| **P1** | 集成图片生成到 InstructionService | 1 天 |
| **P2** | 开发前端 UI (后 4 个页面) | 2-3 天 |
| **P3** | 修复文档和技术债 | 0.5 天 |
