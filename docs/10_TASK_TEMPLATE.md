# 10_TASK_TEMPLATE — Task

版本：v2.0

状态：Accepted

---

# Task 在 Epic-Driven 流程中的位置

```
Epic
↓
Analysis
↓
Implementation Plan
↓
Feature
↓
Story
↓
Task  ← 最小开发单元
↓
Tests（RED → GREEN → REFACTOR）
↓
Documentation Update
```

---

# Task 模板概述

每个 Task 必须包含以下字段：

1. **Epic Context**：所属 Epic / Feature / Story
2. **Goal**：该 Task 要实现的目标
3. **Inputs**：所需的输入数据、文件、参数等
4. **Outputs**：执行完后的输出结果
5. **Acceptance Criteria**：必须满足的可验证条件
6. **Tests Required**：需要的测试类型

Claude Code 执行 Task 时的流程：

1. 确认 Analysis 已完成
2. 按照 RED → GREEN → REFACTOR 写测试
3. 写实现
4. 重构
5. 更新文档
6. Commit

---

# Task 示例模板

## Task-<编号>：<简短描述>

- Epic Context:
  - Epic: <Epic 编号与名称>
  - Feature: <Feature 编号与名称>
  - Story: <Story 编号与名称>
- Goal:
  <说明该 Task 要实现的目标>
- Inputs:
  <该 Task 所需的输入数据、文件、参数等>
- Outputs:
  <执行完该 Task 后的输出结果>
- Acceptance Criteria:
  - <必须满足的条件 1>
  - <必须满足的条件 2>
  - <必须满足的条件 3>
- Tests Required:
  - Contract Test: <测试内容>
  - Unit Test: <测试内容>
  - Integration Test: <测试内容>
  - E2E Test: <测试内容（如适用）>

---

# 示例 Task

## Task-001：上传 STEP 文件接口实现

- Epic Context:
  - Epic: Epic-1 - STEP 文件解析与 ProductGraph 生成
  - Feature: Feature-1 - STEP 文件上传
  - Story: Story-1 - 上传接口实现
- Goal:
  提供 REST API 上传 STEP 文件，并返回 stepFileId
- Inputs:
  - STEP 文件 demo_laser_mount.step
- Outputs:
  - HTTP 200
  - stepFileId
  - 数据库 STEP 文件记录
- Acceptance Criteria:
  - 上传成功返回 HTTP 200
  - 数据库中创建 STEP 文件记录
  - stepFileId 唯一且可用
- Tests Required:
  - Contract Test: POST /step/analyze 请求/响应 Schema 验证
  - Unit Test: upload_step_file_function
  - Integration Test: API 接口连通性 + Repository 持久化
  - E2E Test: 完整上传 → ProductGraph 生成流程

---

# 任务拆解规则

1. 每个 Epic 先完成 Analysis → 输出 Implementation Plan
2. 每个 Feature 拆解为一个或多个 Story
3. 每个 Story 拆解为一个或多个 Task
4. 每个 Task 在 Story 分支内完成
5. 每个 Task 都必须保证独立可执行、独立可测试
6. RED → GREEN → REFACTOR 流程必须严格遵守
7. 每个 Story 完成后必须：
   - 运行全部测试
   - 更新相关文档
   - Commit
8. 所有 Task 文件名与编号必须统一命名：`TASK-<编号>_<简短描述>.md`
9. Task 中所有输入和输出必须明确
10. Acceptance Criteria 必须可验证，可量化
11. Tests Required 必须覆盖 Contract / Unit / Integration / E2E（如适用）

---

# Task 开发最佳实践

- 单个 Task 不超过 1 天工作量（MVP 级别）
- Task 内逻辑清晰，不允许跨 Story / Feature 操作
- 数据库操作必须通过 Repository 层
- 所有 Task 都应生成自动化测试
- Task 执行完成必须保证所有相关测试通过
- 完成一个 Story 的全部 Task 后统一 Commit

---

# Claude Code 执行流程

```
Epic（Analysis 完成）
↓
Story
↓
Task
↓
Acceptance Criteria 确认
↓
Contract Test（RED）
↓
Unit Test（RED）
↓
Integration Test（RED）
↓
Implementation（GREEN）
↓
Refactor（REFACTOR）
↓
All Tests Pass 验证
↓
Documentation Update
↓
Commit（Story 级别）
```

---

# 总结

10_TASK_TEMPLATE.md 是 Claude Code 读取每个 Task 并执行 TDD 流程的核心模板文件。

结合 **09_TESTING_STRATEGY.md** 和 **11_DEFINITION_OF_DONE.md**，保证：

- 每个 Task 在 Epic/Feature/Story 上下文中有明确定位
- 每个 Task 可测、可执行、可持续集成
- 所有 Task 严格符合 MVP / AI Native / Contract First / Epic-Driven
- 每个 Story 完成后文档与代码保持同步
