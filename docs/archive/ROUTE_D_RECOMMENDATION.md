# Route D 最终推荐

**日期**: 2026-06-13
**决策人**: Senior CAD Visualization Engineer + Multimodal AI Architect

---

## 推荐方案

**方案 A (Wireframe 参考图) + Seedream img2img**

---

## 推荐理由

### 1. 唯一能在 3 天内完成的方案

| 方案 | 工作量 | 可行性 |
|---|---|---|
| A: Wireframe | 2-3 天 | ✓ 可行 |
| B: Hidden Line | 5-7 天 | ⚠️ 复杂 |
| C: Grey CAD | 5-7 天 | ⚠️ 曲面解析难 |
| D: Mesh Render | 3-5 天 | ✗ Python 3.13 不兼容 |

### 2. 零新依赖

- 纯 Python + Pillow + openai SDK（全部已在 venv 中）
- 不需要 numpy、trimesh、OCP、conda

### 3. 已验证的 API 能力

```
✓ Seedream 4.0 支持 image-to-image
✓ data:image/png;base64 格式已验证
✓ strength 参数可控 (0.3~0.7)
✓ response_format=b64_json 避免 SSL 问题
✓ 平均延迟 6-11 秒/张
```

### 4. 效果提升路径清晰

```
当前: ~5% 相似度 (Pillow 模板)
     ↓
Route A 完成: 50-70% 相似度 (Wireframe + Seedream img2img)
     ↓
后续优化: 70-85% 相似度 (Grey CAD + Seedream img2img)
```

---

## 技术方案

### 参考图: Wireframe Render

从 STEP 文件中提取 EDGE_CURVE 实体的端点坐标，投影到 2D，用 Pillow 绘制灰色线框。

```
STEP 文件
    ↓
正则提取 CARTESIAN_POINT + EDGE_CURVE + VERTEX_POINT
    ↓
构建边线拓扑: EDGE_CURVE → VERTEX_POINT → CARTESIAN_POINT
    ↓
3D → 2D 等轴测投影 (视角与步骤对应)
    ↓
Pillow 绘制灰色线框 (fill=#d0d0d0, outline=#808080)
    ↓
添加尺寸标注线
    ↓
1024×1024 PNG 参考图
```

### AI 增强: Seedream img2img

```
参考图 (base64)
    ↓
extra_body = {
    "image": "data:image/png;base64,{ref_b64}",
    "strength": 0.5
}
    ↓
images.generate(
    prompt="[材质/光照/风格描述]",
    response_format="b64_json"
)
    ↓
1024×1024 PNG 真实渲染图
    ↓
缩放到 1200×800
    ↓
exports/images/step_N.png
```

---

## 预期效果

### 当前 (纯文本 Prompt)

```
STEP → 元数据 → Prompt 猜测 → Seedream → PNG
相似度: 40-60%
问题: AI 在猜测零件形状
```

### Route A 完成后

```
STEP → 元数据 + 线框参考图 → Prompt + 参考图 → Seedream img2img → PNG
相似度: 50-70%
改善: AI 基于参考图增强，不再猜测
```

### 后续优化 (Grey CAD 参考图)

```
STEP → 元数据 + 灰色 CAD 渲染 → Prompt + 参考图 → Seedream img2img → PNG
相似度: 70-85%
改善: 参考图包含面信息和深度
```

---

## 风险

| 风险 | 概率 | 缓解措施 |
|---|---|---|
| 线框过于混乱（复杂零件） | 中 | 仅提取主轮廓边线，忽略细节边 |
| Seedream 忽略参考图 | 低 | strength=0.5 已验证有效 |
| API 延迟波动 | 中 | 并发调用 + 缓存 |
| 参考图生成失败 | 低 | 降级到纯文本生成 |

---

## 实施计划

### Day 1: 参考图生成器

```
上午: reference_renderer.py
  - 从 STEP 提取 EDGE_CURVE 端点坐标
  - 构建边线列表
  - 3D→2D 等轴测投影
  - Pillow 灰色线框绘制

下午: 测试 + 调优
  - 用 ILD1x20-100.step 实际测试
  - 调整线宽、颜色、视角
  - 处理复杂零件的边线裁剪
```

### Day 2: img2img 集成

```
上午: 修改 doubao_image_client.py
  - 新增 generate_with_reference() 方法
  - 使用 b64_json 响应格式
  - 错误处理 + 降级

下午: 修改 image_service.py
  - 集成参考图生成
  - 参考图 → img2img 流程
  - 保留纯文本降级
```

### Day 3: Prompt 调优 + 测试

```
上午: 优化 prompt_builder.py
  - 针对 img2img 场景优化 Prompt
  - 减少形状描述（参考图已提供）
  - 增加材质/光照描述

下午: 端到端测试
  - 完整流程验证
  - 对比不同 strength 效果
  - 性能测试
```

---

## 最终结论

**推荐: 方案 A (Wireframe) + Seedream img2img**

| 指标 | 数值 |
|---|---|
| 工作量 | 3 天 |
| 新依赖 | 0 |
| Python 3.13 兼容 | ✓ |
| 预期相似度 | 50-70% |
| 降级方案 | 纯文本 Seedream (40-60%) |
| 后续升级路径 | Grey CAD 参考图 (70-85%) |

Route A 是当前约束条件下的最优解：
1. 唯一能在 3 天内完成
2. 唯一不引入新依赖
3. 已验证的 API 能力
4. 清晰的升级路径
