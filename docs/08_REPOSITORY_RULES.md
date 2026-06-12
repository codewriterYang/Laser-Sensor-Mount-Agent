# 08_REPOSITORY_RULES

版本：v2.0

状态：Accepted

---

## 1. 目录结构规范

```
project-root/
│
├─ .claude.md
├─ docs/
│ ├─ 01_PRD.md
│ ├─ 02_ADR.md
│ ├─ 03_ARCHITECTURE.md
│ ├─ 04_DOMAIN_MODEL.md
│ ├─ 05_CONTRACT.md
│ ├─ 06_DATABASE.md
│ ├─ 07_EPICS.md
│ ├─ 08_REPOSITORY_RULES.md
│ ├─ 09_TESTING_STRATEGY.md
│ ├─ 10_TASK_TEMPLATE.md
│ └─ 11_DEFINITION_OF_DONE.md
│
├─ src/
│ ├─ app/
│ │ ├─ services/
│ │ ├─ repositories/
│ │ └─ models/
│ └─ tests/
│   ├─ contract/
│   ├─ unit/
│   ├─ integration/
│   └─ e2e/
└─ migrations/
```

- `services/`：Application/Domain Service
- `repositories/`：Repository 层，实现对数据库的访问
- `models/`：ORM / Pydantic Schema
- `tests/contract/`：Contract 测试
- `tests/unit/`：单元测试
- `tests/integration/`：集成测试
- `tests/e2e/`：E2E 测试
- `migrations/`：Alembic 数据库迁移

---

## 2. 分支策略

- `main`：生产分支，随时可部署
- `develop`：集成分支，用于功能合并
- `feature/<epic-id>-<story-id>`：功能分支，每个 Story 对应一个 feature 分支
- `hotfix/<issue-id>`：紧急修复分支

规则：

1. 每个 Story 必须在单独 feature 分支上完成。
2. Story 内所有 Task 在同一分支上实现。
3. Story 完成后提交 Pull Request 到 develop。
4. 合并前必须通过 CI 自动测试（所有测试类型）。
5. develop 通过后合并到 main，生成可部署版本。

---

## 3. 提交规范

- Commit message 模板：
  ```
  <Epic-ID>/<Story-ID> <Task-ID> <短描述> [Type]
  ```

Type 可选值：

- `feat`: 新增功能
- `fix`: 修复 bug
- `refactor`: 重构
- `test`: 测试相关
- `docs`: 文档修改

示例：
```
E1/S1 TASK-001 上传接口实现 feat
E1/S1 TASK-002 文件持久化 feat
E1/S1 TASK-003 状态管理测试 test
```

规则：
- 每次 Commit 对应一个 Task
- Story 内所有 Task 完成后提交最终 Review 到 develop
- 不允许跨 Story 的混合 Commit

---

## 4. Repository 层规则

- 每个 Aggregate Root 对应一个 Repository
- Repository 提供统一接口：
  - `save()`
  - `get_by_id()`
  - `get_all()`
  - `delete()`
- Application Service 禁止直接操作数据库
- 读操作优先使用 Repository 方法，不允许直接 ORM 查询
- Repository 方法必须保证事务边界：
  - 一个事务只操作单个 Aggregate Root
  - ApprovedProcessGraph 保存可包含 ReviewDecision 一起事务提交
- 异常处理：
  - 所有数据库异常必须捕获并返回标准化错误码
- JSON 字段存储必须通过 Repository 包装，不允许外部直接写入

---

## 5. 数据操作边界

- Aggregate Root 仅在 Repository 内持久化
- 业务逻辑不允许跨 Aggregate Root 更新
- 状态字段更新必须通过 Service + Repository 完成
- 数据库版本升级必须通过 Alembic 迁移脚本

---

## 6. 测试要求

- 每个 Repository 方法必须有 Unit Test
- CRUD 操作覆盖率必须达到 100%
- 集成测试覆盖事务边界和异常场景
- E2E 测试覆盖完整 Epic 流程：
  - STEP 上传 → ProductGraph → DraftProcessGraph → Review → ApprovedProcessGraph → AssemblyInstruction → PDF

---

## 7. Claude Code 配置

- `.claude.md` 文件中必须指定：
  - Repository 路径：`src/app/repositories/`
  - 分支策略：`feature/<epic-id>-<story-id>`
  - Epic-Driven 开发流程：
    ```
    Epic → Analysis → Implementation Plan → Features → Stories → Tasks
    → Tests（RED → GREEN → REFACTOR）→ Documentation Update → Commit
    ```
