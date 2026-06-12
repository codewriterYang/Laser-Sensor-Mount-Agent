# 09_TESTING_STRATEGY

版本：v2.0

状态：Accepted

---

# 目标

建立统一测试体系。

确保：

```
STEP
↓
ProductGraph
↓
DraftProcessGraph
↓
Engineer Review
↓
ApprovedProcessGraph
↓
AssemblyInstruction
↓
PDF
```

整个链路持续可验证。

所有代码开发必须遵循 Epic-Driven Development 流程：

```
Epic
↓
Analysis
↓
Implementation Plan
↓
Features
↓
Stories
↓
Tasks
↓
Tests（RED → GREEN → REFACTOR）
↓
Documentation Update
↓
Commit
```

---

# Testing Pyramid

项目采用 Testing Pyramid。

```
                E2E
                 ▲
                 │
          Integration
                 ▲
                 │
             Unit
```

测试数量：

- Unit Tests ≈ 70%
- Integration Tests ≈ 20%
- E2E Tests ≈ 10%

---

# Test Types

## Unit Test

目标：

验证单个函数、单个类、单个 Domain Service。

特点：

- 不访问数据库
- 不访问网络
- 不访问文件系统
- 执行速度快

示例：

- 验证 ProductGraphValidator
- 输入：ProductGraph
- 输出：ValidationResult

---

## Integration Test

目标：

验证多个组件协作。

特点：

- 可访问 SQLite
- 可访问 Repository
- 可访问 Service

示例：

```
ProcessGenerationService
↓
DraftProcessRepository
↓
SQLite
```

---

## Contract Test

目标：

验证 API Contract。

Contract 来源：

05_CONTRACT.md

验证：

- Request Schema
- Response Schema
- Error Schema
- 是否一致

**Contract Test 是最先编写的测试**（Contract First 原则）。

---

## E2E Test

目标：

验证完整业务流程。

范围：

```
STEP Upload → STEP Parse → ProductGraph → DraftProcessGraph
→ Review → ApprovedProcessGraph → AssemblyInstruction → PDF
```

---

# Epic-Driven Testing Phases

## Phase 1：Analysis（分析阶段）

Epic 启动前的测试规划：

1. 确定该 Epic 涉及的 Contract 端点
2. 确定该 Epic 涉及的 Aggregate Root
3. 确定该 Epic 涉及的 Repository
4. 输出测试范围文档（哪些 Contract / Unit / Integration / E2E 需要新增或修改）

## Phase 2：Story 测试开发（TDD）

每个 Story 内的 Task 遵循 RED → GREEN → REFACTOR：

```
Task
↓
Acceptance Criteria
↓
Test Cases
↓
RED（编写失败测试）
↓
GREEN（最小实现通过测试）
↓
REFACTOR（优化代码，测试仍通过）
```

### 测试开发顺序

1. **Contract Test** 最先编写（验证 API Schema）
2. **Unit Test** 其次编写（验证 Domain Logic）
3. **Integration Test** 再次编写（验证 Repository + Service 协作）
4. **E2E Test** 最后编写（验证完整链路）

## Phase 3：Documentation Update

Story 完成后：

- 更新 EPICS 状态
- 更新 Contract（如有 API 变更）
- 更新 Domain Model（如有模型变更）
- 更新 Database（如有 Schema 变更）

---

# RED Phase

目标：创建失败测试。

要求：至少存在一个失败测试。

例如：`test_upload_step_file()`

预期：FAIL

如果测试直接通过：说明测试无效。

---

# GREEN Phase

目标：通过测试。

要求：实现最少代码。

原则：Make It Work

禁止：提前优化、提前重构。

目标：全部测试通过。

---

# REFACTOR Phase

目标：提升代码质量。

原则：Make It Right

允许：

- 提取函数
- 提取类
- 消除重复代码
- 优化命名

要求：重构后测试必须全部通过。

---

# Unit Test Strategy

## ProductGraph

必须测试：

### Graph Validation

验证：

- Root Assembly 存在
- Node ID 唯一
- Edge ID 唯一
- 无孤立节点

### Node Creation

验证：Node 创建正确。

### Edge Creation

验证：Edge 创建正确。

---

## DraftProcessGraph

必须测试：

### Step Ordering

验证：Parent Before Child

### Fastener Rule

验证：Fastener Last

### Sensor Rule

验证：Sensor After Mount

---

## Review Service

必须测试：

- Accept
- Modify
- Delete
- Insert

四种行为。

---

# Integration Test Strategy

## Repository Tests

必须覆盖：

- ProductGraphRepository
- DraftProcessRepository
- ApprovedProcessRepository
- InstructionRepository

测试内容：

- save()
- get_by_id()
- get_all()
- delete()

---

## Database Transaction Tests

验证：

- 事务提交
- 事务回滚
- 异常处理

---

## Service Integration Tests

验证完整流程：

```
STEP Analysis Service
↓
ProductGraph Repository
↓
SQLite
```

---

# Contract Test Strategy

Contract 来源：05_CONTRACT.md

验证所有 API 端点：

- POST /step/analyze
- POST /process/generate
- POST /process/review
- POST /instruction/render
- 所有 GET API

测试内容：

- Request Schema
- Response Schema
- Status Code
- Error Response

---

# E2E Test Strategy

## MVP Main Flow

测试流程：

```
上传 STEP 文件 → 生成 ProductGraph → 生成 DraftProcessGraph
→ 审核 → 生成 ApprovedProcessGraph → 生成 Instruction → 生成 PDF
```

验证：最终 PDF 成功生成。

---

# Coverage Rules

最低覆盖率：

| 测试类型 | 覆盖率要求 |
|---|---|
| Unit Test | ≥ 90% |
| Integration Test | ≥ 80% |
| Contract Test | 100% |
| Critical Domain | 100% |

Critical Domain：

- ProductGraph
- DraftProcessGraph
- Review Service
- ApprovedProcessGraph

---

# Test Naming Convention

格式：

```
test_<behavior>_<expected_result>()
```

示例：

- `test_upload_step_file_returns_200()`
- `test_generate_product_graph_success()`
- `test_review_process_approved()`

---

# Test File Structure

```
tests/
├── contract/     # Contract 测试（最先编写）
├── unit/         # 单元测试
├── integration/  # 集成测试
└── e2e/          # 端到端测试
```

---

# CI Requirements

Pull Request 合并前必须：

✓ Unit Test Pass
✓ Integration Test Pass
✓ Contract Test Pass
✓ E2E Test Pass
✓ Coverage 达标
✓ Documentation Update 完成

否则：禁止 Merge。

---

# Claude Code Rules

Claude Code 执行时必须：

1. 先完成 Epic Analysis
2. 先写测试、后写实现
3. 禁止跳过 RED
4. 禁止跳过 GREEN
5. 禁止跳过 REFACTOR
6. 禁止跳过 Documentation Update

必须遵循 Epic-Driven Development 流程：

```
Epic
↓
Analysis
↓
Implementation Plan
↓
Features
↓
Stories
↓
Tasks（RED → GREEN → REFACTOR）
↓
Documentation Update
↓
Commit
```
