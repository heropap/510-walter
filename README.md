---
# 详细文档见https://modelscope.cn/docs/%E5%88%9B%E7%A9%BA%E9%97%B4%E5%8D%A1%E7%89%87
domain: #领域：cv/nlp/audio/multi-modal/AutoML
# - nlp
tags: #自定义标签
-
datasets: #关联数据集
  evaluation:
  #- iic/ICDAR13_HCTR_Dataset
  test:
  #- iic/MTWI
  train:
  #- iic/SIBR
models: #关联模型
#- iic/ofa_ocr-recognition_general_base_zh

## 启动文件(若SDK为Gradio/Streamlit，默认为app.py, 若为Static HTML, 默认为index.html)
# deployspec:
#   entry_file: app.py
license: Apache License 2.0
---

# 学科知识整合智能体

AI 全栈极速黑客松作品。系统用 FastAPI + React/Vite + D3 将多本教材解析为章节、知识图谱、跨教材整合决策和 RAG 问答知识库，目标是把 7 本教材压缩为不超过原始体量 30% 的精华版本，同时保留原文引用来源。

## 功能概览

- 多格式教材上传：Markdown/TXT、PDF、Word、PowerPoint、Excel、CSV/JSON/XML、HTML、EPUB、ZIP、Outlook MSG、图片和音频；非纯文本文件通过 MarkItDown 转 Markdown。
- 章节结构解析：复用 `scripts/mdsplit_obsidian.py` 识别 Markdown 标题和中文“第 X 章/节”结构。
- 单本知识图谱：生成章节节点、定义句知识点、包含关系、并列关系和定义关系。
- 跨教材整合：按规范化知识点名称合并重复节点，输出 merge/compress 决策和压缩比。
- 图谱交互：D3 力导向图，支持缩放、拖拽、搜索、系统筛选、节点详情。
- RAG 问答：生成 700 字 chunk + 100 字 overlap；Dify 配置完整时走 Dify，未配置时回退本地关键词 + BM25 混合检索。
- 教师反馈：支持追问合并理由，并通过整合面板或对话撤销合并，实时刷新整合图谱。
- 报告输出：`report/整合报告.md`。

## 文档清单

| 文档 | 路径 |
| --- | --- |
| 需求分析 | `docs/需求分析.md` |
| 系统设计 | `docs/系统设计.md` |
| Agent 架构说明 | `docs/Agent 架构说明.md` |
| 接口文档 | `docs/接口文档.md` |
| 完整架构蓝图 | `学科知识整合智能体-架构设计文档.md` |
| 黑客松执行清单 | `docs/hackathon-playbook.md` |
| 整合报告 | `report/整合报告.md` |

## 已知局限

- PDF、Office、HTML、图片/音频等复杂格式解析受源文件版式和可选依赖影响，扫描版需要 OCR 兜底。
- 当前语义整合以章节标题、定义句和来源频次为主，低置信度合并仍需教师复核。
- Dify 未配置时使用本地关键词 + BM25 混合检索降级，可演示引用链路；完整生成链路仍建议配置 Dify。
- NotebookLM 与闯关游戏属于可选创新层，核心 P0 不依赖它们。

## 本地检索自测

在内置 7 本教材上执行 `build_rag_index(sync_dify=False)` 后，用 5 个真实医学问题测试本地回退检索，Top-5 均返回引用，首条命中均为 `keyword+bm25` 混合方法。

| 问题 | Top-5 引用数 | 首条方法 | 首条来源 |
| --- | ---: | --- | --- |
| 肺炎链球菌为什么会导致肺泡炎症？ | 5 | keyword+bm25 | 医学微生物学 |
| 低氧血症和肺泡通气有什么关系？ | 5 | keyword+bm25 | 生理学 |
| 炎症时血管通透性为什么升高？ | 5 | keyword+bm25 | 生理学 |
| 休克时循环系统会发生什么变化？ | 5 | keyword+bm25 | 生理学 |
| 抗菌药物的临床应用原则是什么？ | 5 | keyword+bm25 | 医学微生物学 |

## 本地运行

环境建议：

- Python 3.10+
- Node.js 20+
- npm 10+

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..

cp .env.example .env
python app.py
```

打开 `http://localhost:7860`。开发前端时可另开：

```bash
cd frontend
npm run dev
```

## 使用流程

1. 打开页面后，左侧会显示内置教材列表和整合压缩统计。
2. 点击“整合图谱”查看跨教材合并结果；点击任意节点查看定义、证据和来源教材。
3. 上传 MarkItDown 支持的教材文件后，系统会自动转换、拆分、构建图谱、刷新整合结果和 RAG chunk。
4. 在右侧“整合”Tab 查看合并决策。
5. 点击决策卡片的“撤销”后，系统会恢复对应来源节点并刷新整合图谱。
6. 在“问答”Tab 输入问题，获得回答和引用来源。
7. 在“对话”Tab 追问整合理由，或输入“不要合并/分开”触发撤销合并。

如果部署在子路径，例如 `https://your-domain.com/510-walter`：

```bash
APP_BASE_PATH=/510-walter npm --prefix frontend run build
APP_BASE_PATH=/510-walter python app.py
```

Docker 构建同理：

```bash
docker build --build-arg APP_BASE_PATH=/510-walter -t 510-walter .
docker run -d --name 510-walter --env-file .env -p 7860:7860 510-walter
docker compose up --build
```

## 环境变量

`.env` 不会提交。DeepSeek 真实链路需要：

```bash
OPENAI_API_KEY=your_deepseek_key
OPENAI_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-v4-flash
```

Dify RAG：

```bash
DIFY_BASE_URL=https://your-dify-instance/v1
DIFY_API_KEY=app-xxxxx
DIFY_KNOWLEDGE_API_KEY=dataset-xxxxx
DIFY_DATASET_ID=dataset-id
```

缺少 Dify 时，页面仍可运行，RAG Tab 会显示等待配置并使用本地 chunk 检索提示。缺少 DeepSeek 时，知识图谱使用规则构建，不阻塞核心流程。

上传转换会优先使用 Python `markitdown` 包，覆盖 PDF、Office、CSV/JSON/XML、HTML、EPUB、ZIP、MSG、图片和音频等常见格式；如果包不存在，会调用 `MARKITDOWN_BIN`，默认可指向 `/Users/walter/.local/bin/markitdown`。

## API

- `GET /health`
- `GET /api/config/status`
- `GET /api/textbooks`
- `GET /api/knowledge/graph/merged`
- `POST /api/integrate/start`
- `GET /api/integrate/decisions`
- `PUT /api/integrate/decisions/{decision_id}`
- `POST /api/rag/index`
- `POST /api/rag/query`
- `POST /api/chat/message`
- `GET /api/game/skill-tree`
- `GET /api/report/generate`

## 验证

```bash
pytest
npm --prefix frontend run build
python app.py
```

启动后访问 `/health` 应返回 `ok: true`，主页应显示 7 本内置教材和整合图谱。

## 仓库提交说明

教材 PDF 不应提交到 GitHub。`.gitignore` 已排除 `*.pdf`、`data/`、构建产物和虚拟环境。评审可通过前端上传赛方教材文件重新测试。
