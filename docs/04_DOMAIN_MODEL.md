# 04_DOMAIN_MODEL — Domain Model

版本：v1.0

状态：Accepted

------

# 1. Domain Overview

本系统核心目标：

将

STEP CAD

转换为

可执行装配指导书。

因此领域模型围绕：

"产品结构"

与

"装配流程"

展开。

------

核心领域对象：

```text
STEP File
↓
ProductGraph
↓
DraftProcessGraph
↓
ReviewDecision
↓
ApprovedProcessGraph
↓
AssemblyInstruction
```

------

# 2. Bounded Context

本项目仅包含一个核心上下文：

Assembly Process Generation

------

负责：

- 产品结构解析
- 装配流程生成
- 工程师审核
- 指导书生成

------

不负责：

- ERP
- MES
- BOM管理
- 库存管理
- 工艺优化系统

这些属于未来系统。

------

# 3. Aggregate Design

本系统包含四个 Aggregate Root

```text
ProductGraph

DraftProcessGraph

ApprovedProcessGraph

AssemblyInstruction
```

------

# 4. ProductGraph

## 类型

Aggregate Root

------

## 职责

描述产品结构。

回答：

```text
这个产品由什么组成？
```

------

而不是：

```text
怎么装？
```

------

# 5. ProductGraph Structure

```json
{
  "graphId": "uuid",
  "nodes": [],
  "edges": []
}
```

------

# 6. Node

```json
{
  "nodeId": "uuid",
  "nodeType": "assembly|part",
  "name": "",
  "metadata": {}
}
```

------

## Node Type

### assembly

装配体

例如：

```text
Laser Sensor Mount
```

------

### part

零件

例如：

```text
Base Plate

Bracket

Sensor

Screw M4x12
```

------

# 7. Node Metadata

用于保存解析后的属性。

示例：

```json
{
  "material": "Aluminum",
  "weight": 12.5,
  "partNumber": "LSM-001"
}
```

------

# 8. Edge

```json
{
  "edgeId": "uuid",
  "source": "",
  "target": "",
  "relation": ""
}
```

------

# 9. Edge Relation

## contains

包含关系

```text
Assembly
↓
Part
```

------

## attached_to

连接关系

```text
Sensor
↓
Bracket
```

------

## fastened_by

紧固关系

```text
Bracket
↓
Screw
```

------

# 10. ProductGraph Invariants

必须满足：

------

graphId 唯一

------

nodeId 唯一

------

edgeId 唯一

------

edge.source 必须存在

------

edge.target 必须存在

------

图中不允许孤立节点

------

必须存在根 Assembly

------

# 11. DraftProcessGraph

## 类型

Aggregate Root

------

## 职责

描述：

AI 生成的装配流程。

回答：

```text
应该怎么装？
```

------

但尚未经过审核。

------

# 12. DraftProcessGraph Structure

```json
{
  "processId": "uuid",
  "steps": [],
  "status": "draft"
}
```

------

# 13. Step

```json
{
  "stepId": "uuid",
  "sequence": 1,
  "title": "",
  "description": "",
  "requiredParts": [],
  "requiredTools": []
}
```

------

# 14. Step Example

```json
{
  "stepId": "uuid",
  "sequence": 1,
  "title": "安装支架",
  "description": "将支架固定到底板",
  "requiredParts": [
    "Bracket",
    "Base Plate"
  ],
  "requiredTools": [
    "Hex Wrench"
  ]
}
```

------

# 15. DraftProcessGraph Status

```text
draft

reviewing

approved

rejected
```

------

# 16. DraftProcessGraph Invariants

sequence 必须连续

------

不能重复

------

必须从 1 开始

------

至少存在一个 Step

------

每个 Step 必须拥有标题

------

每个 Step 必须拥有描述

------

# 17. ReviewDecision

## 类型

Value Object

------

## 职责

记录工程师审核行为。

------

# 18. Structure

```json
{
  "stepId": "",
  "action": "",
  "reason": ""
}
```

------

# 19. Action

支持：

```text
accept

modify

delete

insert
```

------

# 20. Example

```json
{
  "stepId": "uuid",
  "action": "modify",
  "reason": "先固定底板再安装传感器"
}
```

------

# 21. ApprovedProcessGraph

## 类型

Aggregate Root

------

## 职责

表示：

经过工程师批准后的正式工艺流程。

------

系统中唯一可信流程源。

------

# 22. Structure

```json
{
  "approvedProcessId": "uuid",
  "steps": [],
  "approvedBy": "",
  "approvedAt": ""
}
```

------

# 23. ApprovedProcessGraph Invariants

必须来源于：

DraftProcessGraph

------

必须记录：

approvedBy

------

必须记录：

approvedAt

------

批准后禁止修改

------

如需修改：

必须重新生成 Draft

重新审核

------

# 24. AssemblyInstruction

## 类型

Aggregate Root

------

## 职责

面向工人的指导书。

------

回答：

```text
工人应该如何执行？
```

------

# 25. Structure

```json
{
  "instructionId": "uuid",
  "title": "",
  "sections": []
}
```

------

# 26. Section

```json
{
  "sectionType": "",
  "content": ""
}
```

------

# 27. Section Type

支持：

```text
cover

overview

step

safety

ending
```

------

# 28. PDF Layout

```text
Cover Page

↓

Assembly Overview

↓

Assembly Steps

↓

Safety Notes

↓

End Page
```

------

# 29. Domain Service

本项目包含以下 Domain Service

------

## ProcessGenerationService

职责：

ProductGraph

↓

DraftProcessGraph

------

## ReviewService

职责：

DraftProcessGraph

↓

ApprovedProcessGraph

------

## InstructionService

职责：

ApprovedProcessGraph

↓

AssemblyInstruction

------

# 30. Domain Events

MVP 阶段暂不实现 Event Bus

但保留领域事件概念。

------

未来事件：

```text
ProductGraphGenerated

DraftProcessGenerated

ProcessApproved

InstructionRendered
```

------

# 31. Domain Rules

装配规则：

------

Parent Before Child

父级先于子级

------

Base First

底座优先

------

Fastener Last

紧固件最后

------

Washer Follow Fastener

垫片跟随紧固件

------

Sensor After Mount

先安装支架再安装传感器

------

# 32. Source Of Truth

唯一可信源：

```text
ApprovedProcessGraph
```

任何 PDF

任何指导书

任何导出

都必须从：

ApprovedProcessGraph

生成。