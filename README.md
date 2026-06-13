# Laser-Sensor-Mount-Agent

激光传感器支架装配指导书自动生成系统

---

## 项目简介

输入 STEP CAD 文件，自动生成图文装配指导书 PDF。

```
STEP 文件 → 产品结构解析 → 装配流程生成 → 工程师审核 → 图片生成 → PDF 导出
```

## 技术栈

- **后端**：Python 3.13 / FastAPI / SQLite / SQLAlchemy / Pydantic
- **AI**：DeepSeek V4-flash（文本生成）+ Doubao Seedream 4.5（图片生成）
- **前端**：Vanilla HTML/JS SPA
- **测试**：pytest（Contract + Unit + Integration + E2E）

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key

# 4. 启动服务
python -m uvicorn src.app.main:app --reload

# 5. 访问前端
# 打开 http://127.0.0.1:8000
```

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `LLM_API_KEY` | DeepSeek API Key（火山引擎） | 否（无则用模板） |
| `LLM_MODEL` | 文本模型 ID | 否 |
| `IMAGE_API_KEY` | Seedream API Key（火山引擎） | 否（无则仅生成参考图） |
| `IMAGE_MODEL` | 图片模型 ID | 否 |

## 工作流程

1. **上传 STEP** → 解析产品结构 → 自动生成 BOM 库
2. **审核产品结构** → 确认零件和关系
3. **生成装配流程** → 规则引擎 + LLM 生成步骤
4. **审核装配流程** → 接受/修改/删除步骤
5. **渲染指导书** → 生成图片 + PDF
6. **导出 PDF** → 下载装配指导书

## 图片生成模式

| 模式 | 说明 |
|------|------|
| 对比图 | 参考图 + AI 生成图并排（规则 Prompt） |
| 仅参考图 | 线框参考图（无 AI） |
| 文本加生图 | DeepSeek 生成 Prompt → AI 生图 |

## 运行测试

```bash
# 全部测试
python -m pytest src/tests/ -v

# 仅 E2E
python -m pytest src/tests/e2e/ -v
```

## 项目结构

```
src/
├── app/
│   ├── main.py              # FastAPI 应用
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库连接
│   ├── services/            # 业务逻辑
│   │   ├── step_parser.py           # STEP 文件解析
│   │   ├── step_analysis_service.py # STEP 分析服务
│   │   ├── process_generation_service.py  # 流程生成
│   │   ├── review_service.py        # 审核服务
│   │   ├── instruction_service.py   # 指导书渲染
│   │   ├── image_service.py         # 图片生成
│   │   ├── reference_renderer.py    # 参考图渲染
│   │   ├── prompt_builder.py        # Prompt 构建
│   │   ├── llm_service.py           # LLM 文本生成
│   │   ├── doubao_image_client.py   # Seedream API 客户端
│   │   ├── bom_library.py           # BOM 零件库
│   │   └── bom_matcher.py           # BOM 匹配器
│   ├── models/              # ORM + Schema
│   ├── repositories/        # 数据访问层
│   └── static/              # 前端 SPA
├── tests/                   # 测试
│   ├── contract/            # Contract Test
│   ├── unit/                # Unit Test
│   ├── integration/         # Integration Test
│   └── e2e/                 # E2E Test
docs/                        # 项目文档
data/bom/                    # BOM 数据（运行时生成）
```

## 已知限制

- Seedream API 需要火山引擎 API Key
- 参考图质量持续迭代中
- API 无认证（MVP 阶段）
- 无 Docker 部署

## 可扩展方向

- Docker 化部署
- API 鉴权（JWT / API Key）
- Alembic 数据库迁移
- 参考图质量优化（面填充 + Prompt 模板）
- Epic-5 装配知识飞轮
- 多模型支持
- WebSocket 实时进度

## License

Internal use only.
