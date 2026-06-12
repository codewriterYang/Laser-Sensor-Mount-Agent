# 05_CONTRACT — API Contract

版本：v1.0

状态：Accepted

API 风格：

REST API

数据格式：

JSON

字符集：

UTF-8

------

# 1. API Design Principles

------

## Contract First

先定义接口

后实现代码

------

禁止：

```text
先写代码
↓
再补接口
```

------

必须：

```text
Contract
↓
Contract Test
↓
Implementation
```

------

## UUID Everywhere

所有资源主键统一使用：

UUID v4

示例：

```text
550e8400-e29b-41d4-a716-446655440000
```

------

## Resource Oriented

API 按资源组织。

资源包括：

```text
STEP File

ProductGraph

DraftProcessGraph

ApprovedProcessGraph

AssemblyInstruction
```

------

# 2. API Versioning

统一前缀：

```text
/api/v1
```

------

示例：

```text
/api/v1/step/analyze
```

------

未来升级：

```text
/api/v2
```

------

禁止：

Header Versioning

Query Versioning

------

# 3. Standard Response

所有成功响应：

```json
{
  "success": true,
  "data": {},
  "timestamp": "2026-06-11T10:00:00Z"
}
```

------

所有失败响应：

```json
{
  "success": false,
  "error": {
    "code": "STEP_PARSE_FAILED",
    "message": "STEP file parse failed"
  },
  "timestamp": "2026-06-11T10:00:00Z"
}
```

------

# 4. STEP Analysis APIs

------

# 4.1 Analyze STEP

## Endpoint

```http
POST /api/v1/step/analyze
```

------

## Purpose

上传 STEP 文件并生成 ProductGraph。

------

## Request

```multipart/form-data
file=<step file>
```

------

## Response

```json
{
  "success": true,
  "data": {
    "stepFileId": "uuid",
    "productGraphId": "uuid",
    "status": "parsed"
  }
}
```

------

## Error Codes

```text
STEP_FILE_NOT_FOUND

STEP_FILE_INVALID

STEP_PARSE_FAILED

INTERNAL_SERVER_ERROR
```

------

# 4.2 Get ProductGraph

## Endpoint

```http
GET /api/v1/product-graphs/{productGraphId}
```

------

## Response

```json
{
  "success": true,
  "data": {
    "graphId": "uuid",
    "nodes": [],
    "edges": []
  }
}
```

------

## Error

```text
PRODUCT_GRAPH_NOT_FOUND
```

------

# 5. Process Generation APIs

------

# 5.1 Generate DraftProcessGraph

## Endpoint

```http
POST /api/v1/process/generate
```

------

## Purpose

根据 ProductGraph 生成 DraftProcessGraph。

------

## Request

```json
{
  "productGraphId": "uuid"
}
```

------

## Response

```json
{
  "success": true,
  "data": {
    "processId": "uuid",
    "status": "draft",
    "steps": []
  }
}
```

------

## Error

```text
PRODUCT_GRAPH_NOT_FOUND

PROCESS_GENERATION_FAILED
```

------

# 5.2 Get DraftProcessGraph

## Endpoint

```http
GET /api/v1/process/{processId}
```

------

## Response

```json
{
  "success": true,
  "data": {
    "processId": "uuid",
    "status": "reviewing",
    "steps": []
  }
}
```

------

## Error

```text
PROCESS_NOT_FOUND
```

------

# 6. Review APIs

------

# 6.1 Submit Review

## Endpoint

```http
POST /api/v1/process/review
```

------

## Purpose

提交工程师审核结果。

------

## Request

```json
{
  "processId": "uuid",
  "decisions": [
    {
      "stepId": "uuid",
      "action": "modify",
      "reason": "Install bracket first"
    }
  ]
}
```

------

## Response

```json
{
  "success": true,
  "data": {
    "approvedProcessId": "uuid",
    "status": "approved"
  }
}
```

------

## Error

```text
PROCESS_NOT_FOUND

REVIEW_REQUIRED

INVALID_REVIEW_ACTION
```

------

# 6.2 Get ApprovedProcessGraph

## Endpoint

```http
GET /api/v1/approved-process/{approvedProcessId}
```

------

## Response

```json
{
  "success": true,
  "data": {
    "approvedProcessId": "uuid",
    "approvedBy": "Engineer",
    "approvedAt": "2026-06-11T10:00:00Z",
    "steps": []
  }
}
```

------

# 7. Instruction APIs

------

# 7.1 Render Instruction

## Endpoint

```http
POST /api/v1/instruction/render
```

------

## Request

```json
{
  "approvedProcessId": "uuid"
}
```

------

## Response

```json
{
  "success": true,
  "data": {
    "instructionId": "uuid"
  }
}
```

------

## Error

```text
APPROVED_PROCESS_NOT_FOUND

RENDER_FAILED
```

------

# 7.2 Get Instruction

## Endpoint

```http
GET /api/v1/instruction/{instructionId}
```

------

## Response

```json
{
  "success": true,
  "data": {
    "instructionId": "uuid",
    "sections": []
  }
}
```

------

# 8. PDF Export APIs

------

# 8.1 Export PDF

## Endpoint

```http
POST /api/v1/instruction/export-pdf
```

------

## Request

```json
{
  "instructionId": "uuid"
}
```

------

## Response

```json
{
  "success": true,
  "data": {
    "pdfPath": "/exports/assembly_001.pdf"
  }
}
```

------

## Error

```text
INSTRUCTION_NOT_FOUND

PDF_EXPORT_FAILED
```

------

# 9. Schema Definitions

------

## ProductGraph

```json
{
  "graphId": "uuid",
  "nodes": [],
  "edges": []
}
```

------

## DraftProcessGraph

```json
{
  "processId": "uuid",
  "status": "draft",
  "steps": []
}
```

------

## ApprovedProcessGraph

```json
{
  "approvedProcessId": "uuid",
  "approvedBy": "",
  "approvedAt": "",
  "steps": []
}
```

------

## AssemblyInstruction

```json
{
  "instructionId": "uuid",
  "sections": []
}
```

------

# 10. Contract Testing Strategy

Contract 是系统边界。

任何实现都必须通过 Contract Test。

------

开发顺序：

```text
Contract
↓
Contract Test
↓
Implementation
↓
Integration Test
```

------

示例：

```python
def test_generate_process_response_schema():
    response = client.post(...)

    assert response.status_code == 200

    assert "processId" in response.json()["data"]
```

------

# 11. Backward Compatibility

v1 内：

禁止破坏兼容性。

------

允许：

新增字段。

------

禁止：

删除字段。

------

禁止：

修改字段类型。

------

禁止：

修改 Endpoint。

------

如需破坏性修改：

必须创建：

```text
/api/v2
```

------

# 12. Source Of Truth

Contract 是：

API 的唯一事实来源。

------

FastAPI

Pydantic

Frontend

Tests

Documentation

全部以本文件为准。