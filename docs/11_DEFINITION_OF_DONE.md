# 11_DEFINITION_OF_DONE

版本：v2.0

状态：Accepted

---

# 目标

- 定义 Epic / Story / Task 三个层级的完成标准
- 与 Epic-Driven Development 流程对应
- 让 Claude Code 可判断各级别是否 Done
- 保证 MVP 流程可执行且可验证

---

# 完成标准核心原则

1. 所有 Acceptance Criteria 已验证通过
2. 所有 Tests Required 已执行且通过
3. 所有 Repository / 数据库变更经过 Review
4. 所有相关文档已更新（Architecture / Contract / Domain / Database / EPICS）
5. 所有代码提交符合 Commit Template
6. CI/CD Pipeline 所有测试通过
7. 无未解决异常
8. RED → GREEN → REFACTOR 流程完整执行
9. Documentation Update 完成

---

# Level 1：Task Done Checklist

## 1. Acceptance Criteria 完成

- 每条 Acceptance Criteria 已验证通过
- 所有可量化指标满足
- 所有边界条件覆盖

## 2. Unit Tests

- 每个函数/类单元测试执行成功
- 覆盖率 ≥ 90%
- 无未处理异常

## 3. Integration Tests

- 所有组件协作测试执行成功
- 数据库事务边界正确
- 异常处理覆盖

## 4. Contract Tests

- API 请求/响应完全符合 05_CONTRACT.md
- 所有 Schema 验证通过
- 错误码与标准一致

## 5. E2E Tests

- Story 级 E2E 流程成功执行
- 相关聚合根状态转换正确

## 6. RED → GREEN → REFACTOR 流程完成

- RED: 已写失败测试
- GREEN: 已实现功能，测试通过
- REFACTOR: 已重构，测试仍通过

---

# Level 2：Story Done Checklist

Story 内所有 Task 完成后，额外验证：

## 1. 跨 Task 一致性

- Story 内所有 Task 的输出可衔接
- 无重复实现
- 无遗漏功能

## 2. Story E2E 验证

- Story 级别端到端流程可运行
- 上下游接口对齐

## 3. Repository 层完整

- 涉及的所有 Repository 方法有测试
- 事务边界正确

## 4. Code Review

- 已提交 Pull Request
- Review 评论已处理
- Reviewer 已确认

## 5. Commit

- 每个 Task 已完成 Commit
- Commit Message 格式：`<Epic-ID>/<Story-ID> <Task-ID> <描述> [Type]`

---

# Level 3：Epic Done Checklist

Epic 内所有 Story 完成后，额外验证：

## 1. Epic E2E 验证

- Epic 级完整业务流程可运行
- 最终输出符合 PRD 定义

示例（Epic-1）：

```
STEP 上传 → ProductGraph JSON → 数据库持久化
```

全部环节可独立验证。

## 2. Architecture 一致性

- 模块归属与 03_ARCHITECTURE.md 一致
- 数据流与 Architecture 定义一致
- 状态机行为正确

## 3. Domain Model 一致性

- 聚合根不变量全部满足
- 值对象正确使用
- 领域规则正确实现

## 4. Contract 一致性

- 所有 Epic 涉及的 API 端点 100% Contract Test 通过
- Request / Response Schema 与 05_CONTRACT.md 一致
- 错误码标准化

## 5. Database 一致性

- 所有涉及的表已创建
- 索引正确建立
- 外键约束正确

## 6. Documentation Update 完成

Epic 完成后必须同步更新：

- 07_EPICS.md：Epic 状态更新为 Completed
- 03_ARCHITECTURE.md：如有变更必须更新
- 05_CONTRACT.md：如有 API 变更必须更新
- 04_DOMAIN_MODEL.md：如有模型变更必须更新
- 06_DATABASE.md：如有 Schema 变更必须更新

## 7. CI/CD

- 所有 Unit / Integration / Contract / E2E 测试通过
- 覆盖率指标达标
- Pipeline 状态为绿色

---

# Claude Code Done 判定

## Task 级别判定

Claude Code 检查：

1. 以上 Level 1 全部满足 → Task DONE
2. 任意一条未满足 → Task NOT DONE

## Story 级别判定

Claude Code 检查：

1. Level 1 全部满足（所有 Task）
2. Level 2 全部满足
3. 全部满足 → Story DONE

## Epic 级别判定

Claude Code 检查：

1. Level 1 + Level 2 全部满足（所有 Story）
2. Level 3 全部满足（Documentation Update 完成）
3. 全部满足 → Epic DONE

---

# 总结

```
Task DONE
  = Acceptance Criteria
  + Tests（RED → GREEN → REFACTOR）
  + Contract Pass

Story DONE
  = All Tasks DONE
  + Code Review
  + Commit

Epic DONE
  = All Stories DONE
  + E2E Pass
  + Architecture 一致性
  + Domain Model 一致性
  + Contract 一致性
  + Database 一致性
  + Documentation Update
```
