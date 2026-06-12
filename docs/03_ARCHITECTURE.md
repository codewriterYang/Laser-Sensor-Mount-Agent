## 03_ARCHITECTURE — MVP 架构文档

版本：v2.0

状态：Accepted

---

## 1. 系统分层

### 1.1 展示层 (Presentation Layer)
- **Review UI**
  - 职责：显示 DraftProcessGraph，支持工程师审批、修改或拒绝。
  - 输入：DraftProcessGraph JSON
  - 输出：ReviewDecision, 修改后的 DraftProcessGraph
  - 状态机：draft → reviewing → approved / rejected

### 1.2 应用层 (Application Layer)
- **STEP Analysis Service**
  - 职责：解析 STEP 文件生成 ProductGraph
  - 输入：STEP 文件
  - 输出：ProductGraph JSON
  - 状态机：uploaded → parsing → parsed / failed

- **Process Generation Service**
  - 职责：基于规则引擎 + LLM 生成 DraftProcessGraph
  - 输入：ProductGraph
  - 输出：DraftProcessGraph
  - 规则：
    - Parent Before Child
    - Base First
    - Fastener Last
    - Washer Follow Fastener
    - Sensor After Mount

- **Review Service**
  - 职责：处理 ReviewDecision，更新 DraftProcessGraph 或生成 ApprovedProcessGraph
  - 输入：DraftProcessGraph + ReviewDecision
  - 输出：ApprovedProcessGraph
  - 状态机：reviewing → approved / rejected

- **Instruction Service**
  - 职责：渲染 PDF 装配指导书
  - 输入：ApprovedProcessGraph
  - 输出：AssemblyInstruction JSON + PDF 文件

### 1.3 域层 (Domain Layer)
- ProductGraph (聚合根)
- DraftProcessGraph (聚合根)
- ApprovedProcessGraph (聚合根)
- AssemblyInstruction (聚合根)
- ReviewDecision (值对象)

### 1.4 基础设施层 (Infrastructure Layer)
- STEP Parser：解析 STEP 文件，生成初步 ProductGraph
- SQLite：存储 ProductGraph, DraftProcessGraph, ApprovedProcessGraph, AssemblyInstruction
- PDF Generator：生成可打印 PDF

---

## 2. 模块职责概览

| 模块                       | 职责                             | 输入                               | 输出                           | 状态                                 |
| -------------------------- | -------------------------------- | ---------------------------------- | ------------------------------ | ------------------------------------ |
| STEP Analysis Service      | STEP → ProductGraph              | STEP 文件                          | ProductGraph JSON              | uploaded → parsing → parsed / failed |
| Process Generation Service | ProductGraph → DraftProcessGraph | ProductGraph                       | DraftProcessGraph              | draft → generated                    |
| Review Service             | 审核流程                         | DraftProcessGraph + ReviewDecision | ApprovedProcessGraph           | reviewing → approved / rejected      |
| Instruction Service        | 渲染指导书                       | ApprovedProcessGraph               | AssemblyInstruction JSON + PDF | rendered                             |
| Review UI                  | 展示并审批                       | DraftProcessGraph                  | ReviewDecision                 | reviewing → approved / rejected      |

---

## 3. 数据流

```text
STEP 上传
↓
STEP Parser
↓
ProductGraph
↓
Process Generation Service (Rule + LLM)
↓
DraftProcessGraph
↓
Review UI + Review Service
↓
ApprovedProcessGraph
↓
Instruction Service
↓
AssemblyInstruction + PDF
```



## 4. 状态机定义

- STEP 文件：
  - uploaded → parsing → parsed / failed
- ProductGraph：
  - draft → generated → approved
- DraftProcessGraph：
  - draft → reviewing → approved / rejected
- ApprovedProcessGraph：
  - approved
- AssemblyInstruction：
  - rendered

------

## 5. Claude Code 开发边界

- Claude Code 遵循 Epic-Driven Development 流程
- 每个 Epic 先做 Analysis 再进入 Implementation
- 不可新增未文档化模块或服务
- Contract/API、Database、Domain Model 必须遵循文档
- 任何变更必须同时更新：
  - 文档
  - 代码
  - 测试

------

## 6. 模块间依赖

```text
STEP 上传 → 
STEP Parser → 
ProductGraph
ProductGraph → 
Process Generation Service → DraftProcessGraph

DraftProcessGraph → 
Review Service / Review UI → ApprovedProcessGraph

ApprovedProcessGraph → 
Instruction Service → 
AssemblyInstruction + PDF
```

------

## 7. DDD 分层原则

- 聚合根作为最小一致性边界
- 值对象不可单独持久化
- Service 层仅调用聚合根 / 值对象
- 数据存储层负责持久化

------

## 8. 数据存储策略

- SQLite 存储 MVP 数据
- JSON 存储 ProductGraph / DraftProcessGraph / ApprovedProcessGraph / AssemblyInstruction
- 主键统一使用 UUID
- 索引：idx_product_graph_id, idx_draft_process_id, idx_approved_process_id

