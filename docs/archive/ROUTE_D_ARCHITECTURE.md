# Route D 架构设计

**日期**: 2026-06-13
**目标**: STEP → 参考图 → Seedream Image-to-Image → 步骤图

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        输入层                                    │
│  STEP 文件 (.step)                                               │
│  • ILD1x20-100.step (87,510 实体)                                │
│  • SolidWorks 2022 导出                                          │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    解析层 (现有)                                  │
│  step_parser.py                                                  │
│  • 产品名称 / 零件数 / 面数                                       │
│  • 曲面类型标签 (圆柱面/平面/球面/...)                             │
│  • 颜色 (8步链追溯 COLOUR_RGB)                                   │
│  • 整体包围盒 / 零件估算尺寸                                      │
└──────┬──────────────────────────────────────────────────────────┘
       │ ParsedProduct (元数据)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   参考图生成层 (新增)                              │
│                                                                  │
│  参考图生成器 (ReferenceRenderer)                                 │
│                                                                  │
│  方案 A: 灰色 3D 线框 (Pillow 增强版)                             │
│  方案 B: 隐藏线渲染 (拓扑计算)                                    │
│  方案 C: 灰色 CAD 渲染 (面片光栅化)                               │
│  方案 D: 简单 Mesh 渲染 (trimesh + 光栅化)                       │
│                                                                  │
│  输出: 1024×1024 PNG (灰色/线框参考图)                            │
└──────┬──────────────────────────────────────────────────────────┘
       │ reference_image (base64 PNG)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Prompt 构造层 (现有)                              │
│  prompt_builder.py                                               │
│  • 形状描述 (自然语言)                                            │
│  • 颜色描述                                                      │
│  • 尺寸比例                                                      │
│  • 视角 + 装配进度                                               │
│  • 风格参数 (engineering illustration)                           │
└──────┬──────────────────────────────────────────────────────────┘
       │ prompt (string)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│               Seedream Image-to-Image 层 (修改)                   │
│                                                                  │
│  doubao_image_client.py (修改)                                    │
│                                                                  │
│  API 调用:                                                       │
│    images.generate(                                              │
│      model=IMAGE_MODEL,                                          │
│      prompt=prompt,                                              │
│      size="1024x1024",                                           │
│      response_format="b64_json",                                 │
│      extra_body={                                                │
│        "image": f"data:image/png;base64,{ref_b64}",             │
│        "strength": 0.5,                                          │
│        "seed": 42,                                               │
│      }                                                           │
│    )                                                             │
│                                                                  │
│  输出: 1024×1024 PNG (AI 增强的真实渲染图)                        │
└──────┬──────────────────────────────────────────────────────────┘
       │ enhanced_image (bytes)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  后处理层 (修改)                                   │
│  image_service.py                                                │
│  • 缩放到 1200×800 (目标尺寸)                                     │
│  • 保存到 exports/images/                                         │
│  • 缓存 (相同 prompt+ref 不重复调用)                              │
└──────┬──────────────────────────────────────────────────────────┘
       │ final_image_path (string)
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    输出层 (现有)                                   │
│  instruction_service.py                                          │
│  • 嵌入 PDF                                                      │
│  • 浏览器下载                                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 模块变更清单

### 2.1 新增模块

| 文件 | 用途 |
|---|---|
| `src/app/services/reference_renderer.py` | 参考图生成器（核心新增） |

### 2.2 修改模块

| 文件 | 改动 |
|---|---|
| `src/app/services/doubao_image_client.py` | 新增 `generate_with_reference()` 方法 |
| `src/app/services/image_service.py` | 集成参考图生成 + img2img 调用 |
| `src/app/services/prompt_builder.py` | 优化 Prompt（适配 img2img 场景） |

### 2.3 删除模块

无。

---

## 3. 参考图生成器设计

### 3.1 输入

```python
class ReferenceInput:
    part_name: str           # "带孔支架"
    face_count: int          # 19
    surface_types: list[str] # ["圆柱面", "平面"]
    color: str | None        # "#b11919"
    length: float            # 6.1
    width: float             # 1.0
    height: float            # 7.2
    view_label: str          # "俯视"
```

### 3.2 输出

- 1024×1024 PNG
- 灰色调（浅灰填充 + 深灰线框）
- 白色背景
- 包含尺寸标注线
- 保留参考图中的几何结构

### 3.3 参考图风格

```
┌─────────────────────────────────────┐
│                                     │
│        ┌───────────┐               │
│       /           /│               │
│      /           / │               │
│     ┌───────────┐  │               │
│     │           │  │               │
│     │   ○ 孔    │  /               │
│     │           │ /                │
│     └───────────┘/                 │
│                                     │
│     ←── L=6.1mm ──→                │
│                                     │
│  灰色面片 + 深灰边线                 │
│  白色背景                           │
│  尺寸标注                           │
└─────────────────────────────────────┘
```

---

## 4. API 调用流程

```python
# 1. 生成参考图
ref_renderer = ReferenceRenderer()
ref_image = ref_renderer.render(part_info, view_label)
ref_b64 = base64.b64encode(ref_image).decode()

# 2. 构造 Prompt
prompt = build_step_image_prompt(part_info, step_title, view_label)

# 3. 调用 Seedream img2img
response = client.images.generate(
    model=IMAGE_MODEL,
    prompt=prompt,
    size="1024x1024",
    response_format="b64_json",
    extra_body={
        "image": f"data:image/png;base64,{ref_b64}",
        "strength": 0.5,
    },
)

# 4. 解码 + 缩放 + 保存
image_bytes = base64.b64decode(response.data[0].b64_json)
save_and_resize(image_bytes, "exports/images/step_N.png")
```

---

## 5. 降级策略

```
参考图生成成功 + Seedream img2img 成功 → 使用 AI 增强图
参考图生成成功 + Seedream img2img 失败 → 使用参考图本身（灰色渲染）
参考图生成失败 + Seedream text2img 成功 → 使用纯文本生成图
参考图生成失败 + Seedream text2img 失败 → 使用 Pillow 模板绘制
```

---

## 6. 性能预估

| 阶段 | 耗时 |
|---|---|
| STEP 解析 | ~2.5s (现有) |
| 参考图生成 | <0.5s (Pillow 绘制) |
| Prompt 构造 | <0.01s |
| Seedream img2img | 6-11s |
| 后处理 (缩放) | <0.5s |
| **单步总计** | **~10-15s** |
| **7 步总计** | **~70-105s** |

---

## 7. 关键设计决策

### 7.1 为什么用 b64_json 而非 URL？

- 避免 SSL 下载问题（实测 URL 下载有 SSL 错误）
- 避免公网 URL 依赖（服务器可能无公网 IP）
- 内存处理更快

### 7.2 为什么 strength=0.5？

- 0.3: 参考图影响太强，AI 增强不足
- 0.5: 平衡点——保留几何结构 + 增加真实感
- 0.7: 参考图影响太弱，AI 可能忽略几何

### 7.3 为什么 1024×1024 而非 1536×1024？

- 1024×1024 是 Seedream 最稳定的尺寸
- 后处理时再缩放到 1200×800
- 减少 API 延迟
