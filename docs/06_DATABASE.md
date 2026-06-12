# 06_DATABASE — Database Design

版本：v1.0

状态：Accepted

数据库：

SQLite

ORM：

SQLAlchemy

迁移工具：

Alembic

主键策略：

UUID v4

------

# 1. Database Design Principles

------

## Principle 1

MVP 优先

允许：

- JSON 存储
- 简化关系

禁止：

过度规范化

------

## Principle 2

Aggregate First

数据库服务于 Domain。

不是反过来。

------

错误方式：

```text
Database
↓
Domain
```

------

正确方式：

```text
Domain
↓
Database
```

------

## Principle 3

Repository Only

Application Service 禁止直接操作数据库。

必须通过：

Repository

访问。

------

# 2. Data Lifecycle

完整生命周期：

```text
STEP File
↓
ProductGraph
↓
DraftProcessGraph
↓
ApprovedProcessGraph
↓
AssemblyInstruction
↓
PDF
```

------

# 3. Entity Relationship

```text
STEP_FILE
    │
    ▼
PRODUCT_GRAPH
    │
    ▼
DRAFT_PROCESS_GRAPH
    │
    ▼
APPROVED_PROCESS_GRAPH
    │
    ▼
ASSEMBLY_INSTRUCTION
```

------

# 4. Table: step_files

保存上传的 STEP 文件记录。

------

## Columns

| Column     | Type     | Nullable | Description |
| ---------- | -------- | -------- | ----------- |
| id         | UUID     | No       | 主键        |
| file_name  | TEXT     | No       | 文件名称    |
| file_path  | TEXT     | No       | 存储路径    |
| file_size  | INTEGER  | No       | 文件大小    |
| status     | TEXT     | No       | 上传状态    |
| created_at | DATETIME | No       | 创建时间    |
| updated_at | DATETIME | No       | 更新时间    |

------

## Status

允许：

```text
uploaded

parsing

parsed

failed
```

------

# 5. Table: product_graphs

保存 ProductGraph。

------

## Columns

| Column       | Type       |
| ------------ | ---------- |
| id           | UUID       |
| step_file_id | UUID       |
| graph_json   | JSON(TEXT) |
| status       | TEXT       |
| created_at   | DATETIME   |
| updated_at   | DATETIME   |

------

## Foreign Key

```text
step_file_id
↓
step_files.id
```

------

## Status

```text
draft

generated

approved
```

------

## graph_json Example

```json
{
  "graphId": "uuid",
  "nodes": [],
  "edges": []
}
```

------

# 6. Table: draft_process_graphs

保存 AI 生成流程。

------

## Columns

| Column           | Type       |
| ---------------- | ---------- |
| id               | UUID       |
| product_graph_id | UUID       |
| graph_json       | JSON(TEXT) |
| status           | TEXT       |
| generated_by     | TEXT       |
| created_at       | DATETIME   |
| updated_at       | DATETIME   |

------

## Foreign Key

```text
product_graph_id
↓
product_graphs.id
```

------

## Status

```text
draft

reviewing

approved

rejected
```

------

# 7. Table: review_decisions

保存审核历史。

------

## Purpose

审计追踪。

未来支持：

- 回溯
- 审核记录
- 责任归属

------

## Columns

| Column     | Type     |
| ---------- | -------- |
| id         | UUID     |
| process_id | UUID     |
| step_id    | UUID     |
| action     | TEXT     |
| reason     | TEXT     |
| reviewer   | TEXT     |
| created_at | DATETIME |

------

## Action

```text
accept

modify

delete

insert
```

------

# 8. Table: approved_process_graphs

正式流程。

------

## Columns

| Column           | Type       |
| ---------------- | ---------- |
| id               | UUID       |
| draft_process_id | UUID       |
| graph_json       | JSON(TEXT) |
| approved_by      | TEXT       |
| approved_at      | DATETIME   |
| created_at       | DATETIME   |

------

## Rule

Approved 后禁止修改。

------

如需修改：

```text
Create Draft
↓
Review Again
↓
Approve Again
```

------

# 9. Table: assembly_instructions

保存指导书。

------

## Columns

| Column              | Type       |
| ------------------- | ---------- |
| id                  | UUID       |
| approved_process_id | UUID       |
| instruction_json    | JSON(TEXT) |
| pdf_path            | TEXT       |
| created_at          | DATETIME   |

------

# 10. Why JSON Storage

MVP 阶段：

选择：

```text
graph_json
```

而不是：

```text
nodes table

edges table
```

------

原因：

结构变化频繁。

Graph 查询简单。

开发速度快。

Claude Code 实现简单。

------

# 11. Index Strategy

------

## product_graphs

```sql
CREATE INDEX idx_product_graph_file
ON product_graphs(step_file_id);
```

------

## draft_process_graphs

```sql
CREATE INDEX idx_draft_product_graph
ON draft_process_graphs(product_graph_id);
```

------

## approved_process_graphs

```sql
CREATE INDEX idx_approved_draft
ON approved_process_graphs(draft_process_id);
```

------

## assembly_instructions

```sql
CREATE INDEX idx_instruction_approved
ON assembly_instructions(approved_process_id);
```

------

# 12. Repository Design

每个 Aggregate Root 一个 Repository。

------

## ProductGraphRepository

职责：

```text
save()

get_by_id()

get_by_step_file()
```

------

## DraftProcessRepository

职责：

```text
save()

get_by_id()

get_by_product_graph()
```

------

## ApprovedProcessRepository

职责：

```text
save()

get_by_id()
```

------

## InstructionRepository

职责：

```text
save()

get_by_id()
```

------

# 13. Transaction Boundary

事务边界：

Aggregate Root。

------

允许：

```text
ProductGraph Save
```

一个事务。

------

允许：

```text
ApprovedProcessGraph Save
+
ReviewDecision Save
```

一个事务。

------

禁止：

跨多个业务流程的大事务。

------

# 14. Migration Strategy

工具：

Alembic

------

规则：

任何 Schema 修改：

必须：

```text
Update Database Doc
↓
Generate Migration
↓
Update Repository
↓
Update Tests
```

------

禁止：

手工修改生产数据库。

------

# 15. Test Database Strategy

单元测试：

```text
SQLite In Memory
```

------

集成测试：

```text
Temporary SQLite File
```

------

E2E：

独立测试库。

------

# 16. Future Evolution

未来可能拆分：

```text
product_nodes

product_edges
```

独立表。

------

当前阶段：

禁止。

------

保持：

```text
graph_json
```

方案。

------

# 17. Source Of Truth

数据库只是持久化层。

真正事实来源：

```text
Domain Model
```

即：

ProductGraph

DraftProcessGraph

ApprovedProcessGraph

AssemblyInstruction

数据库必须服务于领域模型。