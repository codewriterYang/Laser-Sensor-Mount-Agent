# IMAGE_GENERATION_REALITY_AUDIT.md

**审计日期**: 2026-06-12
**审计人**: Senior CAD Visualization Engineer
**审计范围**: STEP 文件 → 图片生成 完整链路
**审计目标**: 找到最适合当前项目的真实步骤图方案

---

## Phase 1: 当前链路完整审查

### 1.1 数据流图（现状）

```
┌─────────────┐
│  .step 文件  │  ILD1x20-100.step (87,510 实体, 44 种类型)
│  SolidWorks  │  10 个 MANIFOLD_SOLID_BREP
│  2022 导出    │  41,456 个顶点 / 877 个 B 样条曲面
└──────┬──────┘
       │ 读取全文为字符串
       ▼
┌─────────────────────────────────────────────┐
│  step_parser.py (正则解析, 395 行)            │
│                                             │
│  提取:                                      │
│    ✓ PRODUCT 名称                           │
│    ✓ FILE_SCHEMA 类型                       │
│    ✓ 是否装配体 (NEXT_ASSEMBLY_USAGE_*)      │
│    ✓ 整体包围盒 (采样 5000 个 CARTESIAN_POINT)│
│    ✓ 每零件面数 (CLOSED_SHELL → ADVANCED_FACE)│
│    ✓ 曲面类型标签 (平面/圆柱/球面/环面/锥面/B样条)│
│    ✓ 零件颜色 (8 步链追溯 COLOUR_RGB)        │
│    ✓ 零件分类名 (规则推断)                    │
│    ✓ 每零件尺寸 (面数比例 × 整体尺寸, 估算)   │
│                                             │
│  未提取:                                     │
│    ✗ 41,456 个 CARTESIAN_POINT 坐标归属      │
│    ✗ 3,578 个 VERTEX_POINT                   │
│    ✗ 5,479 个 EDGE_CURVE 边界                │
│    ✗ 877 个 B_SPLINE_SURFACE 控制点/节点向量   │
│    ✗ 331 个 CIRCLE 半径/圆心                  │
│    ✗ 面的拓扑关系 (EDGE_LOOP → ORIENTED_EDGE) │
│    ✗ 零件在装配体中的空间位置                  │
└──────┬──────────────────────────────────────┘
       │ ParsedProduct (name, parts[], dimensions, colors)
       ▼
┌─────────────────────────────────────────────┐
│  step_analysis_service.py                    │
│                                             │
│  • 合并同名零件 (name + surface_types 去重)   │
│  • 构建 ProductGraph (nodes + edges)         │
│  • 节点 metadata:                            │
│    { name, faceCount, surfaceTypes,          │
│      length, width, height, color }          │
│                                             │
│  未传递:                                     │
│    ✗ 任何几何顶点数据                         │
│    ✗ 任何曲线/曲面参数                        │
│    ✗ 任何拓扑关系                             │
└──────┬──────────────────────────────────────┘
       │ ProductGraph JSON
       ▼
┌─────────────────────────────────────────────┐
│  process_generation_service.py (LLM 生成步骤) │
│  instruction_service.py (组装 per_step_info)  │
│                                             │
│  为每个步骤匹配零件节点，传递:                 │
│  { name, faceCount, surfaceTypes,            │
│    length, width, height, color }            │
│                                             │
│  仍然没有任何几何数据                         │
└──────┬──────────────────────────────────────┘
       │ per_step_info dict
       ▼
┌─────────────────────────────────────────────┐
│  image_service.py (Pillow 程序化绘制, 480 行) │
│                                             │
│  输入: name, faceCount, surfaceTypes,        │
│        length/width/height, color            │
│                                             │
│  处理:                                       │
│  1. 固定虚拟尺寸 v=80,60,40 / scale=5.0      │
│  2. 根据 surfaceTypes 选形状模板:            │
│     圆柱面 → _draw_cylinder()                │
│     球面+环面 → _draw_sphere()               │
│     环面+锥面 → _draw_threaded()             │
│     面数≤6 → _draw_plate()                   │
│     其他 → _draw_3d_box()                    │
│  3. 用 STEP 颜色填充 (或默认调色板)           │
│  4. 不同步骤用不同预设视角 (10 个循环)        │
│  5. 右侧信息面板 + 尺寸标注                  │
│                                             │
│  输出: 1200×800 PNG                          │
│                                             │
│  未使用:                                     │
│    ✗ 任何网络请求                             │
│    ✗ 任何 AI 模型                             │
│    ✗ 任何 3D 渲染引擎                         │
│    ✗ 任何几何顶点数据                         │
└─────────────────────────────────────────────┘
       │
       ▼
   exports/images/step_N_xxxxxxxx.png
```

### 1.2 Parser 提取了什么 vs Image Service 使用了什么

| Parser 提取字段 | Image Service 使用方式 | 保真度 |
|---|---|---|
| 产品名称 | 未使用 | — |
| 零件分类名 | 右侧面板显示 | ★★★★★ |
| 面数 | 影响形状模板选择 | ★★☆☆☆ |
| 曲面类型 | 决定画圆柱/球/板/长方体 | ★★☆☆☆ |
| 颜色 (R,G,B) | 转 hex 填充形状 | ★★★★☆ |
| 尺寸 (估算) | 仅用于底部标注文字 | ★☆☆☆☆ |
| 整体包围盒 | 未使用 | — |

**结论**: Image Service 使用的几乎全部是**元数据标签**，而非几何数据。

### 1.3 豆包模型当前是否参与

**否。完全未参与。**

证据链：
1. `image_service.py` 无任何 `import requests / httpx / openai`
2. 无任何 HTTP 请求代码
3. 无任何 `IMAGE_MODEL / IMAGE_API_KEY / IMAGE_BASE_URL` 引用
4. `.env` 中配置了 `IMAGE_MODEL=ep-20260612172525-2v5bb`（Seedream 4.0），但无调用代码
5. `config.py` 定义了 `IMAGE_MODEL / IMAGE_BASE_URL / IMAGE_API_KEY`，但无消费方

**豆包 Seedream 已配置、已授权、未实现。**

### 1.4 图片与真实模型差异来源

| 排名 | 差异来源 | 影响度 | 当前状态 |
|---|---|---|---|
| 1 | 无几何顶点数据 | ★★★★★ | Parser 不提取 |
| 2 | 形状使用模板而非真实几何 | ★★★★★ | 5 种固定模板 |
| 3 | 不使用 AI 图片生成 | ★★★★☆ | 代码未实现 |
| 4 | 无 B 样条曲面数据 | ★★★★☆ | Parser 不解析 |
| 5 | 零件尺寸为估算值 | ★★★☆☆ | 面数比例公式 |
| 6 | 无零件空间位置 | ★★★☆☆ | 非装配文件，无变换矩阵 |
| 7 | 曲面类型仅作标签 | ★★☆☆☆ | 不含半径/高度参数 |
| 8 | 颜色仅取主色 | ★★☆☆☆ | 一个零件一种颜色 |
| 9 | 视角固定循环 | ★☆☆☆☆ | 10 个预设视角 |
| 10 | 2D 投影非真 3D | ★☆☆☆☆ | Pillow 绘制 |

---

## Phase 2: 三条技术路线分析

### 2.1 当前环境状态

| 项目 | 状态 |
|---|---|
| Python | 3.13.9 (venv) |
| Pillow | 12.2.0 ✓ |
| openai SDK | 2.36.0 ✓ |
| httpx | 0.27.0 ✓ |
| numpy | 2.3.4 ✓ |
| FreeCAD | ✗ 未安装 |
| OpenCASCADE (OCP/pythonocc) | ✗ 未安装 |
| trimesh | ✗ 未安装 |
| scipy / vtk / pyvista | ✗ 未安装 |
| Docker | 29.5.2 ✓ (无 Dockerfile) |
| 豆包 Seedream API | 已配置 ✓ 未调用 |

---

### Route A: 当前 Parser + Prompt 增强 + 豆包生图

**原理**: 利用已有的元数据（名称、面数、曲面类型、颜色、尺寸），构造精确 Prompt，调用豆包 Seedream 生成图片。

**实现方式**:

```
STEP 文件
    ↓
step_parser.py（现有，不改）
    ↓
ParsedProduct（现有元数据）
    ↓
Prompt 构造器（新增）
    ↓
"Generate a technical CAD rendering of a [零件名],
 with [N] faces, surfaces: [圆柱面,平面],
 color: #b11919, dimensions: 55.6×12.4×114.7mm,
 isometric view, white background, engineering style"
    ↓
豆包 Seedream 4.0 API（已配置，新增调用代码）
    ↓
PNG
```

**需要修改的模块**:

| 文件 | 改动 |
|---|---|
| `image_service.py` | 重写，替换 Pillow 绘制为 API 调用 |
| 新增 prompt_builder.py | 根据元数据构造图片生成 Prompt |
| `requirements.txt` | 无需新增（openai/httpx 已有） |

**工作量评估**:

| 任务 | 时间 |
|---|---|
| 编写 Prompt 构造逻辑 | 0.5 天 |
| 接入豆包 Seedream API | 0.5 天 |
| 多步骤图片差异化（不同视角/装配状态） | 0.5 天 |
| 错误处理/重试/降级 | 0.5 天 |
| 测试调优 | 1 天 |
| **总计** | **3 天** |

**风险**:

| 风险 | 概率 | 影响 |
|---|---|---|
| Seedream 不理解 CAD 术语 | 中 | 图片质量差 |
| API 延迟 (每张图 3-10 秒) | 高 | 7 步骤 = 30-70 秒等待 |
| 每张图消耗 token/费用 | 确定 | 持续成本 |
| 图片风格不稳定 | 中 | 同一 Prompt 不同结果 |
| 无法精确还原模型细节 | 确定 | AI 生图本质是"想象" |

**最终相似度**: **40-60%**

理由：
- 豆包 Seedream 是**文本生成图片**模型，不是**CAD 渲染**引擎
- 它能理解"红色圆柱体"，但无法理解"ILD1x20-100 的精确几何"
- 即使 Prompt 精确到毫米，生成的仍然是"AI 想象的零件"，不是"STEP 模型的渲染"
- 对于简单零件（螺栓、垫片），相似度可能达到 60-70%
- 对于复杂零件（B 样条曲面主体），相似度可能低于 30%

**结论**: 投入低，但天花板明确——AI 生图 ≠ CAD 渲染。

---

### Route B: FreeCAD 真实截图

**原理**: 用 FreeCAD 命令行打开 STEP 文件，设置视角，导出 PNG 截图。

**实现方式**:

```
STEP 文件
    ↓
FreeCAD CLI（headless 模式）
    ↓
  import Part
  shape = Part.read("model.step")
  # 设置视角、光源、背景
  # 导出 PNG
    ↓
真实渲染 PNG
```

**需要安装的依赖**:

| 依赖 | 大小 | Python 3.13 兼容性 |
|---|---|---|
| FreeCAD | ~1.2 GB | ✗ FreeCAD 0.21 支持 Python 3.10/3.11 |
| FreeCAD Python 包 | — | ✗ 无 pip 包，需独立安装 |

**关键障碍**:

1. **FreeCAD 不支持 Python 3.13**
   - FreeCAD 0.21.x 绑定 Python 3.10/3.11
   - FreeCAD 1.0 (2024.11) 绑定 Python 3.12
   - 当前 venv 是 Python 3.13.9，**无法直接使用**
   - 需要：降级 Python 或安装独立 FreeCAD 环境

2. **FreeCAD 不是 pip 包**
   - 无法 `pip install freecad`
   - 需要从官网下载安装包或 conda 安装
   - Windows 上安装路径：`C:\Program Files\FreeCAD 0.21\`
   - Python 绑定需要手动配置 `sys.path`

3. **无头渲染依赖 OpenGL**
   - FreeCAD 的 3D 渲染需要 OpenGL 上下文
   - 服务器/CI 环境无 GPU 时需要 Mesa 软渲染
   - Windows 无头模式需额外配置

4. **与 venv 集成困难**
   - FreeCAD 自带 Python，与项目 venv 隔离
   - 需要通过 subprocess 调用 FreeCAD CLI
   - 数据传递通过文件系统，非内存

**工作量评估**:

| 任务 | 时间 |
|---|---|
| FreeCAD 安装 + 环境配置 | 1-2 天 |
| Python 3.13 兼容性处理 | 1-2 天 |
| CLI 脚本编写（打开 STEP、设视角、导出 PNG） | 1 天 |
| 与 FastAPI 集成（subprocess 调用） | 1 天 |
| 多步骤装配状态渲染 | 2-3 天 |
| 跨平台兼容性测试 | 1-2 天 |
| **总计** | **7-12 天** |

**风险**:

| 风险 | 概率 | 影响 |
|---|---|---|
| Python 3.13 不兼容 | **高** | 需降级或隔离环境 |
| 安装体积过大 (~1.2GB) | 确定 | 部署复杂 |
| 无头模式渲染失败 | 中 | 需要 Mesa/GPU |
| FreeCAD API 不稳定 | 低 | 版本间 API 变化 |
| 部署到生产环境困难 | 高 | 依赖系统级安装 |

**最终相似度**: **85-95%**

理由：
- FreeCAD 是真正的 CAD 内核，基于 OpenCASCADE
- STEP 文件中的所有几何（B 样条、圆弧、自由曲面）都能精确解析
- 渲染质量取决于 FreeCAD 的 3D 视图引擎
- 能导出真实视角的高清截图

**结论**: 效果最好，但环境代价最大。Python 3.13 不兼容是致命障碍。

---

### Route C: OpenCASCADE (OCP) + 自定义渲染

**原理**: 用 OpenCASCADE 的 Python 绑定 (OCP) 解析 STEP 为 B-Rep 几何，三角化为 mesh，用 pyglet/pyvista/Pillow 渲染。

**实现方式**:

```
STEP 文件
    ↓
OCP (Python OpenCASCADE 绑定)
  from OCP.STEPControl import STEPControl_Reader
  reader = STEPControl_Reader()
  reader.ReadFile("model.step")
  reader.TransferRoots()
  shape = reader.Shape()
    ↓
三角化 (B-Rep → Triangle Mesh)
  from OCP.BRepMesh import BRepMesh_IncrementalMesh
  mesh = BRepMesh_IncrementalMesh(shape, linearDeflection=0.1)
    ↓
提取三角面片顶点 + 法向量
    ↓
软件渲染 (pyglet / numpy + Pillow / pyvista)
    ↓
PNG
```

**需要安装的依赖**:

| 依赖 | 大小 | pip 可装 | Python 3.13 |
|---|---|---|---|
| OCP | ~150 MB | ✓ (conda-forge) | ⚠️ 需验证 |
| cadquery | ~50 MB | ✓ (conda) | ⚠️ 需验证 |
| pyvista | ~30 MB | ✓ | ✓ |
| trimesh | ~5 MB | ✓ | ✓ |
| scipy | ~30 MB | ✓ | ✓ |

**关键问题**: OCP (pythonocc-core 的后继) 主要通过 **conda** 分发，pip 安装不稳定。

**方案 C-a: conda 环境**:

```bash
conda create -n occ python=3.12
conda install -c conda-forge pythonocc-core
```

- 与项目 venv 隔离
- 需要 subprocess 调用
- 类似 Route B 的集成困难

**方案 C-b: trimesh + opencascade 后端**:

```bash
pip install trimesh[opencascade]
```

- trimesh 通过 `opencascade` extras 安装 OCP
- 但 Python 3.13 兼容性未验证
- trimesh 可直接读 STEP 文件并输出 mesh

**工作量评估**:

| 任务 | 时间 |
|---|---|
| OCP 安装 + 环境配置 | 2-3 天 |
| STEP → B-Rep → Mesh 代码 | 2 天 |
| 软件渲染器编写 | 2-3 天 |
| 颜色/材质映射 | 1 天 |
| 多视角/装配状态 | 2 天 |
| 与 FastAPI 集成 | 1 天 |
| **总计** | **10-12 天** |

**风险**:

| 风险 | 概率 | 影响 |
|---|---|---|
| OCP 不支持 Python 3.13 | **高** | 需降级或隔离 |
| conda 与 venv 冲突 | 中 | 需 subprocess 隔离 |
| 安装失败（依赖冲突） | 中 | conda 环境管理复杂 |
| 渲染质量不如 FreeCAD | 中 | 自定义渲染器 |
| 维护成本高 | 高 | OpenCASCADE API 复杂 |

**最终相似度**: **80-90%**

理由：
- OpenCASCADE 是工业级几何内核，能精确解析 STEP
- 三角化后的 mesh 能真实表达零件形状
- 渲染质量取决于自定义渲染器的实现水平
- 比 FreeCAD 路线更灵活，但工作量更大

**结论**: 理论上最灵活，但工程量最大且环境风险最高。

---

## Phase 3: 方案决策

### 3.1 三条路线对比

| 维度 | Route A (豆包生图) | Route B (FreeCAD) | Route C (OpenCASCADE) |
|---|---|---|---|
| **工作量** | 3 天 | 7-12 天 | 10-12 天 |
| **新依赖** | 0 | ~1.2 GB | ~200 MB |
| **Python 3.13 兼容** | ✓ 无需改 | ✗ 不兼容 | ⚠️ 需验证 |
| **venv 兼容** | ✓ 直接用 | ✗ 隔离 | ⚠️ conda 隔离 |
| **部署复杂度** | 低 | 高 | 高 |
| **最终相似度** | 40-60% | 85-95% | 80-90% |
| **持续成本** | 有（API 费用） | 无 | 无 |
| **风格稳定性** | 低（AI 随机性） | 高（确定性） | 高（确定性） |
| **维护难度** | 低 | 中 | 高 |
| **MVP 适合度** | ★★★★★ | ★★★☆☆ | ★★☆☆☆ |

### 3.2 决策矩阵

**约束条件**:
1. 当前 venv: Python 3.13.9
2. 不能破坏现有 FastAPI 服务
3. MVP 阶段，需要快速出成果
4. 目标：步骤图与真实模型尽可能一致

**排除 Route B 的理由**:
- FreeCAD **不支持 Python 3.13**，这是硬性障碍
- 安装 1.2GB 独立软件，与 venv 集成困难
- 7-12 天工作量，对 MVP 过重

**排除 Route C 的理由**:
- OCP 主要通过 conda 分发，与 venv 冲突
- Python 3.13 兼容性未验证
- 10-12 天工作量，且需要编写自定义渲染器
- 维护成本最高

**选择 Route A 的理由**:
1. **零新依赖**: openai SDK、httpx 已在 venv 中
2. **零环境风险**: 不需要安装任何系统级软件
3. **3 天工作量**: 最适合 MVP 节奏
4. **API 已配置**: `.env` 中 KEY 有效，`config.py` 已定义
5. **40-60% 相似度**: 虽然不如 CAD 渲染，但远超当前 Pillow 模板的 ~5%
6. **渐进增强**: Route A 可以与 Route B/C 并存，未来替换不影响架构

### 3.3 最终推荐

**Route A: 当前 Parser + Prompt 增强 + 豆包 Seedream 生图**

**理由**:
1. 唯一能在 3 天内完成的方案
2. 唯一不引入系统级依赖的方案
3. 唯一与 Python 3.13 venv 完全兼容的方案
4. 相似度从 ~5% 提升到 40-60%，是量级级改善
5. 豆包 Seedream 已配置未用，是"低垂的果实"
6. 未来可与 Route B/C 共存（AI 生图作为降级方案）

**风险缓解**:
- Prompt 质量不稳定 → 多轮调优 + Prompt 模板化
- API 延迟 → 异步并发 + 进度条
- 图片风格不一致 → 固定 Prompt 前缀 + 风格参数

---

## Phase 4: 实施计划

### 4.1 模块变更清单

#### 新增模块

| 文件 | 用途 | 依赖 |
|---|---|---|
| `src/app/services/prompt_builder.py` | 根据元数据构造图片生成 Prompt | 无外部依赖 |
| `src/app/services/doubao_image_client.py` | 豆包 Seedream API 客户端 | openai SDK |

#### 修改模块

| 文件 | 改动内容 |
|---|---|
| `src/app/services/image_service.py` | 重写：Pillow 绘制 → 调用 DoubaoImageClient |
| `src/app/config.py` | 新增 `is_image_configured()` 函数 |
| `requirements.txt` | 无新增（openai/httpx 已有） |

#### 删除模块

无。保留 Pillow 作为降级方案（API 不可用时回退到模板绘制）。

### 4.2 技术依赖

| 依赖 | 版本 | 状态 |
|---|---|---|
| openai SDK | ≥1.58.0 | ✓ 已安装 (2.36.0) |
| httpx | ≥0.27.0 | ✓ 已安装 |
| Pillow | ≥10.0 | ✓ 已安装 (12.2.0)，用于降级 |
| 豆包 Seedream API | 4.0 | ✓ 已配置，KEY 有效 |

### 4.3 Prompt 设计策略

**输入元数据**:
```python
{
    "name": "带孔支架",
    "faceCount": 19,
    "surfaceTypes": ["圆柱面", "平面"],
    "length": 6.1,
    "width": 1.0,
    "height": 7.2,
    "color": "#b11919",
    "sequence": 3,
    "totalSteps": 7,
    "stepTitle": "安装激光支架",
    "viewLabel": "俯视"
}
```

**构造 Prompt 的原则**:
1. 不依赖 AI 理解 CAD 术语，而是用自然语言描述形状
2. 颜色直接用 hex 值，不描述
3. 尺寸给出比例关系而非绝对值
4. 明确指定风格：技术插图、白底、等轴测
5. 每步骤 Prompt 差异化：不同视角 + 装配进度

**示例 Prompt**:
```
A technical engineering illustration of a small metal bracket
with a cylindrical hole, red color (#b11919),
isometric view from top-right angle,
white background, clean CAD-style rendering,
dimension labels visible, step 3 of 7 assembly process,
surrounding parts shown as transparent gray outlines.
Style: photorealistic technical drawing, studio lighting.
```

### 4.4 API 调用方式

豆包 Seedream 兼容 OpenAI images.generate API:

```python
from openai import OpenAI

client = OpenAI(
    api_key=IMAGE_API_KEY,
    base_url=IMAGE_BASE_URL,
)

response = client.images.generate(
    model=IMAGE_MODEL,  # "ep-20260612172525-2v5bb"
    prompt=prompt_text,
    n=1,
    size="1024x1024",
)

image_url = response.data[0].url  # 下载图片
```

### 4.5 降级策略

```
API 调用成功 → 使用 AI 生成图片
API 调用失败 → 回退到当前 Pillow 模板绘制
API 未配置   → 直接使用 Pillow 模板绘制
```

### 4.6 实施顺序

```
Day 1 上午: 编写 prompt_builder.py
            - 根据元数据构造 Prompt
            - 多种零件类型的 Prompt 模板
            - 视角/装配进度差异化

Day 1 下午: 编写 doubao_image_client.py
            - OpenAI SDK 调用 Seedream
            - 图片下载 + 缓存
            - 错误处理 + 重试

Day 2 上午: 重写 image_service.py
            - 接入 DoubaoImageClient
            - 保留 Pillow 作为降级
            - 异步并发调用（多步骤并行生图）

Day 2 下午: Prompt 调优
            - 用 ILD1x20-100.step 实际测试
            - 调整 Prompt 参数
            - 对比 AI 图 vs 真实模型截图

Day 3:      集成测试 + 细节打磨
            - 端到端流程验证
            - PDF 中嵌入 AI 图片
            - 性能优化（并发 + 缓存）
```

### 4.7 风险点

| 风险 | 概率 | 缓解措施 |
|---|---|---|
| Seedream 不支持 `images.generate` 接口 | 低 | 查阅火山引擎文档确认 |
| API 返回 base64 而非 URL | 中 | 两种格式都处理 |
| 图片风格与工程图差异大 | 中 | Prompt 中强调 "engineering illustration" |
| 7 步骤串行生图太慢 (30-70 秒) | 高 | 用 asyncio.gather 并发 |
| API 限流 | 中 | 加退避重试 |
| 不同步骤图片风格不一致 | 中 | 固定 Prompt 前缀 |

---

## 附录: 为什么其他方案不适合 MVP

### 为什么不用 trimesh？

```bash
pip install trimesh[opencascade]
```

- trimesh 的 STEP 支持需要 `opencascade` 后端
- OCP (OpenCASCADE Python) 主要通过 conda-forge 分发
- Python 3.13 的 OCP wheel 可能不存在
- 即使安装成功，还需要编写 3D 渲染器（trimesh 只提供 mesh，不提供高质量渲染）

### 为什么不直接用 pythonocc？

- pythonocc-core 是 conda 包，不支持 pip
- 需要 conda 环境，与项目 venv 冲突
- 安装体积 ~500MB
- Python 3.13 兼容性不确定

### 为什么不等 Python 降级再做？

- MVP 时间紧迫
- Route A 不依赖 Python 版本，可以立即开始
- 未来降级 Python 后可以叠加 Route B/C

---

## 总结

| 问题 | 答案 |
|---|---|
| 当前图片是什么？ | Pillow 模板绘制的示意图，~5% 相似度 |
| 豆包参与了吗？ | 没有。已配置未实现。 |
| 差异的根本原因？ | 无几何数据 → 模板绘制 ≠ CAD 渲染 |
| 最佳方案？ | **Route A: 豆包 Seedream 生图** |
| 为什么不是 B/C？ | Python 3.13 不兼容 + 安装代价大 |
| 工作量？ | 3 天 |
| 相似度预期？ | 40-60% (从 ~5% 提升) |
| 未来能升级吗？ | 可以，Route A 与 B/C 可共存 |
