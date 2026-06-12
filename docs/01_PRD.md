# 01_PRD — Laser Sensor Mount Assembly Agent 产品需求文档

版本：v1.0
状态：Accepted

## 1. 项目概述
Laser Sensor Mount Assembly Agent 是一个 MVP 系统，将 STEP CAD 文件转换为工程师审核的装配流程，并最终生成工人可执行的 PDF 装配指导书。

## 2. 问题描述
光电企业存在大量 STEP CAD 图纸，工人无法理解。工程师需花费大量时间手动生成装配说明书。

## 3. 产品目标
- 上传 STEP 文件
- 生成 ProductGraph
- 生成 DraftProcessGraph
- 工程师审核与批准
- 输出 PDF 装配指导书

## 4. 用户角色
### 主用户：CAD 工程师
- 上传 STEP 文件
- 审核草稿工艺流程
- 批准或修改 DraftProcessGraph

### 次用户：装配工人
- 按照 PDF 指导书完成装配

## 5. MVP 范围
### 包含
- STEP 文件上传与解析
- ProductGraph 生成
- DraftProcessGraph 生成
- 工程师审核
- ApprovedProcessGraph 生成
- 指导书渲染与 PDF 导出

### 不包含
- 知识飞轮/规则自学习
- AR/VR 指导
- 自适应学习
- 高级优化算法

## 6. 成功标准
- 完整流程可运行 Demo STEP 文件
- JSON ProductGraph 和 DraftProcessGraph 正确生成
- 工程师可以审核与批准
- PDF 装配指导书生成可打印

## 7. 当前项目阶段
- Phase 1：文档冻结 — 已完成
- Phase 2：数据库设计 — 已完成
- Phase 3：Epic-1 开发 — 已完成
- Phase 4：Epic-2 开发 — 待启动