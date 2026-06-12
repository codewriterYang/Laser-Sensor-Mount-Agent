# 07_EPICS

版本：v2.0
状态：Accepted

---

# Epic-Driven Development 工作流

```
Epic
↓
Analysis（分析阶段）
↓
Implementation Plan（实现计划）
↓
Features
↓
Stories
↓
Tasks
↓
Tests（RED → GREEN → REFACTOR）
↓
Documentation Update（文档同步更新）
↓
Commit（Story 级别提交）
```

---

# Epic 状态定义

| 状态 | 含义 |
|---|---|
| `Planning` | Epic 已定义，尚未开始 Analysis |
| `Analysis` | 正在进行 Architecture / Contract / Domain 分析 |
| `Implementation` | 正在按 Story / Task 开发 |
| `Completed` | 所有 Story 完成，E2E 通过，文档已更新 |

---

# Epic-1：STEP 文件解析与 ProductGraph 生成

- **状态**：Completed
- **完成日期**：2026.6.11
- **Phase**：全部 Story 完成，E2E 通过，文档已更新

## 目标
- 完整实现从 STEP 文件上传到 ProductGraph 生成的闭环
- 验证 MVP 核心流程是否可落地

---

## Feature-1：STEP 文件上传

### Story-1：上传接口实现
- **Task-1：接口测试**
  - Goal: 确认上传接口返回正确 HTTP 状态码
  - Inputs: STEP 文件
  - Outputs: HTTP 200 或错误码
  - Acceptance Criteria:
    - 上传成功返回 200
    - 错误时返回规范化错误
  - Tests Required:
    - Contract 测试
    - Unit Test

- **Task-2：实现上传接口**
  - Goal: 提供 REST API 上传 STEP 文件
  - Inputs: STEP 文件
  - Outputs: stepFileId
  - Acceptance Criteria: 同 Task-1
  - Tests Required: 同 Task-1

- **Task-3：文件持久化**
  - Goal: 保存 STEP 文件到 SQLite / 本地存储
  - Acceptance Criteria:
    - 文件保存成功
    - 数据库记录创建
  - Tests Required:
    - Repository 测试

- **Task-4：状态管理**
  - Goal: STEP 文件状态从 uploaded → parsing → parsed / failed
  - Acceptance Criteria:
    - 状态转换正确
    - 异常时可回滚
  - Tests Required:
    - Unit Test
    - Integration Test

---

## Feature-2：STEP 文件解析

### Story-1：生成 ProductGraph
- **Task-1：解析节点与边**
  - Goal: 从 STEP 文件解析节点与边
  - Inputs: STEP 文件
  - Outputs: ProductGraph JSON
  - Acceptance Criteria:
    - 节点、边正确生成
    - 满足 ProductGraph Invariants
  - Tests Required:
    - Unit Test

- **Task-2：存储 ProductGraph**
  - Goal: 将 ProductGraph 持久化到 SQLite
  - Inputs: ProductGraph JSON
  - Outputs: 数据库记录
  - Acceptance Criteria:
    - JSON 保存正确
    - 索引正确建立
  - Tests Required:
    - Repository 测试

- **Task-3：状态管理**
  - Goal: ProductGraph 状态从 draft → generated
  - Acceptance Criteria:
    - 状态更新正确
  - Tests Required:
    - Unit Test

- **Task-4：异常处理**
  - Goal: STEP 解析失败时状态更新为 failed
  - Acceptance Criteria:
    - 异常捕获
    - 返回规范化错误码
  - Tests Required:
    - Unit Test
    - Integration Test

---

# Epic-2：DraftProcessGraph 生成与审核

- **状态**：Completed
- **完成日期**：2026.6.12
- **Phase**：全部 Story 完成，E2E 通过，文档已更新

## 目标

- 根据 ProductGraph 自动生成 DraftProcessGraph
- 支持工程师审核并生成 ApprovedProcessGraph
- 验证 MVP 核心流程可落地

---

## Feature-1：Process Generation Service

### Story-1：规则 + LLM 生成 DraftProcessGraph

- **Task-1：实现规则引擎**
  - Goal: 构建装配顺序规则库
  - Inputs: ProductGraph JSON
  - Outputs: 初步流程步骤
  - Acceptance Criteria:
    - 步骤顺序满足 Parent Before Child
    - Base First
    - Fastener Last
    - Washer Follow Fastener
    - Sensor After Mount
  - Tests Required:
    - Unit Test

- **Task-2：调用 LLM 生成步骤文本**
  - Goal: 根据 ProductGraph 生成自然语言步骤描述
  - Inputs: ProductGraph 节点与边
  - Outputs: DraftProcessGraph 文本内容
  - Acceptance Criteria:
    - 步骤文本可读
    - 每步包含标题与描述
  - Tests Required:
    - Unit Test

- **Task-3：组合生成 DraftProcessGraph JSON**
  - Goal: 合并规则与 LLM 输出形成完整 DraftProcessGraph
  - Inputs: 规则引擎输出 + LLM 输出
  - Outputs: DraftProcessGraph JSON
  - Acceptance Criteria:
    - JSON 满足 DraftProcessGraph Invariants
  - Tests Required:
    - Unit Test

- **Task-4：存储 DraftProcessGraph**
  - Goal: 保存 DraftProcessGraph 到 SQLite
  - Inputs: DraftProcessGraph JSON
  - Outputs: 数据库记录
  - Acceptance Criteria:
    - JSON 保存成功
    - 索引正确建立
  - Tests Required:
    - Repository 测试

- **Task-5：状态管理 (draft → reviewing)**
  - Goal: 更新 DraftProcessGraph 状态为 reviewing
  - Inputs: DraftProcessGraph ID
  - Outputs: 状态字段更新
  - Acceptance Criteria:
    - 状态正确
  - Tests Required:
    - Unit Test

---

## Feature-2：Review Service

### Story-1：工程师审批流程

- **Task-1：实现 ReviewDecision 接口**
  - Goal: 提供 REST API 接收工程师审核
  - Inputs: DraftProcessGraph ID + ReviewDecision JSON
  - Outputs: 更新后的 DraftProcessGraph / ApprovedProcessGraph
  - Acceptance Criteria:
    - ReviewDecision 记录在数据库
    - 状态流转正确
  - Tests Required:
    - API 测试
    - Unit Test

- **Task-2：更新 DraftProcessGraph 状态**
  - Goal: 根据 ReviewDecision 修改 DraftProcessGraph 状态
  - Inputs: DraftProcessGraph + ReviewDecision
  - Outputs: DraftProcessGraph 更新
  - Acceptance Criteria:
    - draft → reviewing → approved / rejected
  - Tests Required:
    - Unit Test
    - Integration Test

- **Task-3：生成 ApprovedProcessGraph**
  - Goal: 将审核通过的 DraftProcessGraph 转化为 ApprovedProcessGraph
  - Inputs: DraftProcessGraph
  - Outputs: ApprovedProcessGraph
  - Acceptance Criteria:
    - ApprovedProcessGraph JSON 正确生成
    - 状态为 approved
  - Tests Required:
    - Unit Test
    - Repository Test

- **Task-4：审核异常处理**
  - Goal: 处理审核输入异常、非法操作
  - Inputs: 异常 ReviewDecision
  - Outputs: 返回错误信息 / 状态回滚
  - Acceptance Criteria:
    - 异常捕获
    - 返回标准化错误码
  - Tests Required:
    - Integration Test

---

# Epic-3：ApprovedProcessGraph 与 AssemblyInstruction

- **状态**：Completed
- **完成日期**：2026.6.12
- **Phase**：全部 Story 完成，E2E 通过，文档已更新

## 目标

- 将 DraftProcessGraph 审核通过后生成正式 ApprovedProcessGraph
- 将 ApprovedProcessGraph 渲染为 PDF 装配指导书
- 验证 PDF 可打印且流程无误

---

## Feature-1：ApprovedProcessGraph 生成

### Story-1：生成正式流程

- **Task-1：复制草稿步骤**
  - Goal: 将 DraftProcessGraph 步骤复制到 ApprovedProcessGraph
  - Inputs: DraftProcessGraph JSON
  - Outputs: ApprovedProcessGraph JSON
  - Acceptance Criteria:
    - 步骤顺序一致
    - 节点和边完整
  - Tests Required:
    - Unit Test

- **Task-2：记录审核人信息**
  - Goal: 保存工程师 ID / Name
  - Inputs: ReviewDecision
  - Outputs: ApprovedProcessGraph.approvedBy
  - Acceptance Criteria:
    - 审核人信息完整
  - Tests Required:
    - Unit Test

- **Task-3：记录批准时间**
  - Goal: 保存批准时间戳
  - Inputs: 系统当前时间
  - Outputs: ApprovedProcessGraph.approvedAt
  - Acceptance Criteria:
    - 时间格式正确
  - Tests Required:
    - Unit Test

- **Task-4：状态更新**
  - Goal: 更新状态为 approved
  - Acceptance Criteria:
    - Draft → ApprovedProcessGraph.approved
  - Tests Required:
    - Unit Test

- **Task-5：存储数据库**
  - Goal: 保存 ApprovedProcessGraph 到 SQLite
  - Acceptance Criteria:
    - 数据库记录创建成功
  - Tests Required:
    - Repository 测试

---

## Feature-2：Instruction Service

### Story-1：渲染 PDF 指导书

- **Task-1：渲染步骤文本**
  - Goal: 将 ApprovedProcessGraph 转为图文步骤文本
  - Inputs: ApprovedProcessGraph JSON
  - Outputs: AssemblyInstruction JSON
  - Acceptance Criteria:
    - 每步有标题、描述、所需零件和工具
  - Tests Required:
    - Unit Test

- **Task-2：生成图文 Section**
  - Goal: 为每步生成对应示意图或 CAD 渲染图
  - Inputs: AssemblyInstruction JSON
  - Outputs: 含图 Section
  - Acceptance Criteria:
    - 图文对应正确
  - Tests Required:
    - Unit Test

- **Task-3：生成 PDF**
  - Goal: 输出可打印 PDF
  - Inputs: AssemblyInstruction JSON
  - Outputs: PDF 文件
  - Acceptance Criteria:
    - PDF 可打开
    - 页码与步骤对应
  - Tests Required:
    - Integration Test

- **Task-4：存储 PDF 路径**
  - Goal: 保存 PDF 文件路径到数据库
  - Acceptance Criteria:
    - 路径可在数据库查询
  - Tests Required:
    - Repository Test

- **Task-5：返回下载链接**
  - Goal: 提供 PDF 下载 URL
  - Acceptance Criteria:
    - URL 可访问
  - Tests Required:
    - Integration Test

### Story-2：Instruction 异常处理

- **Task-1：渲染失败重试**
- **Task-2：PDF 文件损坏修复**
- **Task-3：通知工程师**

---

# Epic-4：MVP 边界与 Demo

- **状态**：Completed
- **完成日期**：2026.6.12
- **Phase**：全部 Story 完成，95 tests，0 skipped

## 目标

- 验证端到端流程可执行
- 确认 MVP 功能边界清晰

---

# Epic-5：Assembly Knowledge Flywheel（装配知识飞轮）

- **状态**：Deferred（非 MVP）
- **Phase**：MVP 完成后进入 Analysis

## 目标

- 验证端到端流程可执行
- 确认 MVP 功能边界清晰
- 提供可演示 Demo 文件

---

## Feature-1：End-to-End Workflow 验证

### Story-1：完整业务链路验证

- **Task-1：上传 Demo STEP 文件**
  - Goal: 验证 STEP 文件上传接口可正常工作
  - Inputs: Demo STEP 文件
  - Outputs: stepFileId
  - Acceptance Criteria:
    - 上传成功返回 HTTP 200
    - 数据库记录成功创建
  - Tests Required:
    - Unit Test
    - Contract 测试

- **Task-2：解析 ProductGraph**
  - Goal: STEP Parser 正确生成 ProductGraph
  - Inputs: stepFileId
  - Outputs: ProductGraph JSON
  - Acceptance Criteria:
    - 节点和边正确生成
    - 满足 ProductGraph Invariants
  - Tests Required:
    - Unit Test
    - Integration Test

- **Task-3：生成 DraftProcessGraph**
  - Goal: Process Generation Service 生成草稿流程
  - Inputs: ProductGraph JSON
  - Outputs: DraftProcessGraph JSON
  - Acceptance Criteria:
    - 至少生成一个步骤
    - 每步包含 sequence、title、description
  - Tests Required:
    - Unit Test
    - Integration Test

- **Task-4：工程师审核流程**
  - Goal: Review Service 正确处理 DraftProcessGraph
  - Inputs: DraftProcessGraph JSON + ReviewDecision
  - Outputs: ApprovedProcessGraph JSON
  - Acceptance Criteria:
    - 审核通过生成 ApprovedProcessGraph
    - 状态更新为 approved
  - Tests Required:
    - API 测试
    - Integration Test

- **Task-5：渲染 PDF 指导书**
  - Goal: Instruction Service 渲染可打印 PDF
  - Inputs: ApprovedProcessGraph JSON
  - Outputs: PDF 文件
  - Acceptance Criteria:
    - PDF 可打开
    - 页码与步骤对应
    - 图文结合正确
  - Tests Required:
    - Integration Test
    - Unit Test

- **Task-6：完整链路验收**
  - Goal: 验证整个端到端流程可运行
  - Inputs: Demo STEP 文件
  - Outputs: 最终 PDF
  - Acceptance Criteria:
    - 无人工干预
    - PDF 成功生成
  - Tests Required:
    - E2E 测试

---

## Feature-2：MVP Scope 验证

### Story-1：功能边界验证

- **Task-1：确认知识飞轮未调用**
  - Goal: 验证 MVP 未包含 Learning Loop
  - Inputs: 系统日志
  - Outputs: 验证报告
  - Acceptance Criteria:
    - 日志中未调用 Learning Service
  - Tests Required:
    - Integration Test

- **Task-2：确认 AR 模块未加载**
  - Goal: 确保 AR/VR 模块未启用
  - Inputs: 系统模块列表
  - Outputs: 验证报告
  - Acceptance Criteria:
    - 模块未加载
  - Tests Required:
    - Integration Test

- **Task-3：确认自学习未启用**
  - Goal: 系统行为确定性
  - Inputs: 运行日志
  - Outputs: 验证报告
  - Acceptance Criteria:
    - 无自动训练操作
  - Tests Required:
    - Integration Test

---

# Epic-5：Assembly Knowledge Flywheel（装配知识飞轮）

- **状态**：Planning
- **Phase**：非 MVP 范围，等待 MVP 完成后进入 Analysis

## 目标

- 沉淀工程师审核经验
- 构建企业装配知识库
- 提高 DraftProcessGraph 生成质量
- 降低工程师审核成本
- 为未来 Agent 自主优化提供数据基础

---

## Feature-1：Review Data Collection

### Story-1：收集工程师审核行为

- **Task-1：记录 Accept 操作**
  - Goal: 保存工程师接受步骤的行为
  - Inputs: ReviewDecision
  - Outputs: Review Event
  - Acceptance Criteria:
    - Accept 操作被完整记录
    - 可追溯审核人
    - 可追溯时间
  - Tests Required:
    - Unit Test
    - Repository Test

- **Task-2：记录 Modify 操作**
  - Goal: 保存工程师修改步骤行为
  - Inputs: 原始 Step + 修改后 Step
  - Outputs: Modify Event
  - Acceptance Criteria:
    - 修改前后内容均保存
    - 支持差异对比
  - Tests Required:
    - Unit Test
    - Repository Test

- **Task-3：记录 Delete 操作**
  - Goal: 保存工程师删除步骤行为
  - Inputs: ReviewDecision
  - Outputs: Delete Event
  - Acceptance Criteria:
    - 删除步骤被完整记录
    - 删除原因被保存
  - Tests Required:
    - Unit Test
    - Repository Test

- **Task-4：记录 Insert 操作**
  - Goal: 保存工程师新增步骤行为
  - Inputs: ReviewDecision
  - Outputs: Insert Event
  - Acceptance Criteria:
    - 新增步骤被完整保存
    - 插入位置被记录
  - Tests Required:
    - Unit Test
    - Repository Test

### Story-2：构建审核历史

- **Task-1：建立 Review History Repository**
  - Goal: 存储全部审核行为
  - Inputs: Review Event
  - Outputs: Review History
  - Acceptance Criteria:
    - 可根据 Process 查询
    - 可根据 Reviewer 查询
  - Tests Required:
    - Repository Test

- **Task-2：建立审核时间线**
  - Goal: 追踪审核过程
  - Inputs: Review Events
  - Outputs: Timeline
  - Acceptance Criteria:
    - 时间顺序正确
    - 操作顺序正确
  - Tests Required:
    - Integration Test

---

## Feature-2：Knowledge Base Construction

### Story-1：构建装配知识库

- **Task-1：提取审核经验**
  - Goal: 从 Review History 提取经验规则
  - Inputs: Review History
  - Outputs: Knowledge Rules
  - Acceptance Criteria:
    - 可识别高频修改
    - 可识别高频错误
  - Tests Required:
    - Unit Test

- **Task-2：构建 Rule Repository**
  - Goal: 存储装配规则
  - Inputs: Knowledge Rules
  - Outputs: Rule Repository
  - Acceptance Criteria:
    - 支持增删改查
    - 支持版本管理
  - Tests Required:
    - Repository Test

- **Task-3：建立规则版本管理**
  - Goal: 管理知识库版本
  - Inputs: Rule Repository
  - Outputs: Versioned Rules
  - Acceptance Criteria:
    - 可回滚
    - 可比较差异
  - Tests Required:
    - Integration Test

### Story-2：知识检索

- **Task-1：实现规则查询服务**
  - Goal: 提供知识检索能力
  - Inputs: ProductGraph
  - Outputs: Relevant Rules
  - Acceptance Criteria:
    - 返回相关规则
    - 响应时间 < 1s
  - Tests Required:
    - Unit Test
    - Integration Test

- **Task-2：实现相似案例检索**
  - Goal: 查询历史相似产品
  - Inputs: ProductGraph
  - Outputs: Similar Cases
  - Acceptance Criteria:
    - 返回 Top-K 案例
    - 支持排序
  - Tests Required:
    - Integration Test

---

## Feature-3：Knowledge Enhanced Generation

### Story-1：增强 DraftProcessGraph 生成

- **Task-1：加载历史规则**
  - Goal: 在生成前加载知识库
  - Inputs: ProductGraph
  - Outputs: Knowledge Context
  - Acceptance Criteria:
    - 成功获取规则
  - Tests Required:
    - Integration Test

- **Task-2：构建增强 Prompt**
  - Goal: 将知识库注入 Prompt
  - Inputs: ProductGraph + Knowledge Context
  - Outputs: Enhanced Prompt
  - Acceptance Criteria:
    - Prompt 包含规则信息
  - Tests Required:
    - Unit Test

- **Task-3：生成增强版 DraftProcessGraph**
  - Goal: 提高生成质量
  - Inputs: Enhanced Prompt
  - Outputs: DraftProcessGraph
  - Acceptance Criteria:
    - 审核修改率下降
    - 步骤质量提升
  - Tests Required:
    - Integration Test

### Story-2：评估知识飞轮效果

- **Task-1：统计审核通过率**
  - Goal: 衡量生成质量
  - Inputs: Review History
  - Outputs: Pass Rate
  - Acceptance Criteria:
    - 统计准确
  - Tests Required:
    - Unit Test

- **Task-2：统计修改率**
  - Goal: 衡量知识库价值
  - Inputs: Review History
  - Outputs: Modify Rate
  - Acceptance Criteria:
    - 可按时间维度分析
  - Tests Required:
    - Integration Test

- **Task-3：生成飞轮报告**
  - Goal: 展示系统持续优化能力
  - Inputs: Metrics
  - Outputs: Flywheel Report
  - Acceptance Criteria:
    - 可视化展示
    - 支持导出
  - Tests Required:
    - Integration Test
