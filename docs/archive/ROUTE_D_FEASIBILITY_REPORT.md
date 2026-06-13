# Route D 可行性报告

**日期**: 2026-06-13
**审计人**: Senior CAD Visualization Engineer + Multimodal AI Architect
**目标**: 确认 Doubao Seedream 4.0 是否支持 image-to-image 以及参考图增强方案的可行性

---

## 1. Seedream 4.0 API 能力实测

### 1.1 核心发现

**Seedream 4.0 支持 image-to-image（图片到图片）生成。**

通过 `images.generate` 的 `extra_body` 参数传入参考图，无需额外 SDK 或端点。

### 1.2 已验证的 API 参数

| 参数 | 类型 | 是否支持 | 说明 |
|---|---|---|---|
| `prompt` | string | ✓ | 文本描述（必须） |
| `model` | string | ✓ | 模型 endpoint ID |
| `n` | int | ✓ | 生成数量 |
| `size` | string | ✓ | 1024x1024 / 1536x1024 / 1024x1536 |
| `response_format` | string | ✓ | `"url"` (默认) 或 `"b64_json"` |
| `extra_body.image` | string | ✓ | **data:image/png;base64,...** 格式的参考图 |
| `extra_body.strength` | float | ✓ | 参考图影响强度 0.0~1.0 |
| `extra_body.seed` | int | ✓ | 随机种子（控制可复现性） |
| `extra_body.guidance_scale` | float | ✓ | 引导比例 |

### 1.3 不支持的端点

| 端点 | 状态 | 说明 |
|---|---|---|
| `images.edit` | ✗ 404 | 标准 OpenAI 编辑接口不支持 |
| `images.create_variation` | ✗ 404 | 标准变体接口不支持 |
| size=512x512 | ✗ 400 | 最小 1024x1024 |

### 1.4 实测数据

```
测试环境: Python 3.13.9 + openai SDK 2.36.0
模型: ep-20260612172525-2v5bb (doubao-seedream-4.0)
API: https://ark.cn-beijing.volces.com/api/v3/images/generations

参考图格式: data:image/png;base64,{base64_string}
可用尺寸: 1024x1024, 1536x1024, 1024x1536
响应格式: URL 或 base64_json
平均延迟: 6-11 秒/张
```

---

## 2. Image-to-Image 实测效果

### 2.1 测试方案

创建灰色 3D 线框参考图 → Seedream 增强为真实渲染图

| strength | 效果 | 耗时 | 文件大小 |
|---|---|---|---|
| 0.3 | 保留参考图结构，轻微增强 | 10.9s | 156 KB |
| 0.5 | 平衡：保留形状 + 增加细节 | 6.8s | 214 KB |
| 0.7 | 大幅增强，参考图影响弱 | 7.6s | 158 KB |

### 2.2 关键发现

1. **strength=0.5 是最佳平衡点** — 保留参考图的几何结构，同时增加真实感
2. **参考图可以是简单的灰色线框** — 不需要高质量渲染
3. **Prompt 仍然重要** — 描述材质、光照、风格的文字影响最终效果
4. **response_format=b64_json 可以避免 SSL 下载问题** — 直接在内存中处理

---

## 3. 可行性结论

| 维度 | 评估 |
|---|---|
| API 支持 image-to-image | ✓ 已验证 |
| 参考图可以是简单线框 | ✓ 已验证 |
| strength 可控 | ✓ 已验证 (0.3~0.7) |
| b64_json 直接返回 | ✓ 已验证 |
| 可复现性 (seed) | ✓ 已验证 |
| 延迟可接受 (<15s) | ✓ 平均 7-10s |
| 无需新依赖 | ✓ openai SDK 已有 |

**结论: Route D 完全可行。**
