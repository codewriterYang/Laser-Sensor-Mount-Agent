# 02_ADR — Architecture Decision Records

版本：v1.0

状态：Accepted

------

# ADR-001

## 标题

MVP 优先于技术完美性

------

## 背景

项目目标是验证：

STEP CAD
↓

ProductGraph
↓

DraftProcessGraph
↓

Engineer Review
↓

ApprovedProcessGraph
↓

PDF Instruction

整条链路是否能够跑通。

当前阶段不是构建工业级 MES 系统。

不是构建知识飞轮系统。

不是构建自动工艺优化平台。

------

## 决策

优先实现：

能够跑通完整业务闭环。

即使：

- 架构不够优雅
- 性能不够极致
- 扩展性一般

也允许接受。

------

## 替代方案

方案A：

先构建可扩展架构。

优点：

后期维护方便。

缺点：

开发周期长。

风险高。

------

方案B：

先构建完整闭环。

优点：

快速验证价值。

缺点：

后期可能重构。

------

## 最终选择

方案B

------

## 影响

允许：

- SQLite
- 单体服务
- JSON 存储

暂不要求：

- 微服务
- 分布式架构
- 高并发设计

------

# ADR-002

## 标题

ProductGraph 与 ProcessGraph 分离

------

## 背景

CAD 装配结构

与

装配工艺流程

是两种不同的信息。

例如：

CAD：

Base
├── Bracket
├── Sensor
└── Screw

这是结构关系。

------

工艺：

Step1 安装 Bracket

Step2 安装 Sensor

Step3 锁紧 Screw

这是流程关系。

------

## 决策

建立两个独立模型。

ProductGraph

描述：

产品结构。

------

ProcessGraph

描述：

装配流程。

------

## 原因

符合 DDD 领域模型原则。

避免：

结构模型污染流程模型。

------

## 后果

必须维护：

ProductGraph

↓

DraftProcessGraph

之间的转换逻辑。

------

# ADR-003

## 标题

Human-In-The-Loop 强制存在

------

## 背景

LLM 生成的流程存在风险。

包括：

- 步骤遗漏
- 顺序错误
- 工具错误
- 安全风险

------

## 决策

禁止：

LLM 直接输出 PDF。

必须经过：

Engineer Review

阶段。

------

## 状态流转

Draft

↓

Reviewing

↓

Approved

或

Rejected

------

## 原因

工程场景属于高风险领域。

不能完全信任模型输出。

------

# ADR-004

## 标题

ApprovedProcessGraph 是唯一可信源

------

## 决策

PDF 只能来自：

ApprovedProcessGraph

不能来自：

DraftProcessGraph

------

## 原因

保证：

工程师审核结果

与

最终指导书

完全一致。

------

# ADR-005

## 标题

Contract First

------

## 决策

先写：

API Contract

再写：

代码实现

------

## 原因

Claude Code 在 Contract 明确时表现最好。

避免：

边写边改接口。

------

## 开发顺序

Contract

↓

Contract Test

↓

Implementation

↓

Integration Test

------

# ADR-006

## 标题

STEP 解析是项目最大技术风险

------

## 原因

如果：

STEP

↓

ProductGraph

失败

则后续全部失败。

------

## 决策

Epic-1 优先开发：

STEP Analysis Service

------

## 风险等级

Critical

------

# ADR-007

## 标题

Living Documentation

------

## 背景

Freeze 不等于 Immutable。

------

## 决策

允许修改：

- Architecture
- Contract
- Database
- Domain Model

但是必须：

同步修改：

文档

↓

代码

↓

测试

------

## 禁止

文档与实现不一致。

------

# ADR-008

## 标题

Task 是最小开发单元

------

## 错误方式

Epic

↓

Claude Code 一次完成

------

Feature

↓

Claude Code 一次完成

------

都会导致上下文失控。

------

## 正确方式

Epic

↓

Feature

↓

Story

↓

Task

↓

RED

↓

GREEN

↓

REFACTOR

↓

REVIEW

↓

COMMIT

------

## 约束

一个 Task：

预计工作量 ≤ 1天

Claude Code 每次只允许实现一个 Task。