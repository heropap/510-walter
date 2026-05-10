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

FastAPI + React/Vite + D3 的全栈教材整合应用，用 7 本医学教材生成可交互知识图谱、整合决策、RAG 问答和学习材料样例。

## 本地运行

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

如果部署在子路径，例如 `https://your-domain.com/510-walter`：

```bash
APP_BASE_PATH=/510-walter npm --prefix frontend run build
APP_BASE_PATH=/510-walter python app.py
```

Docker 构建同理：

```bash
docker build --build-arg APP_BASE_PATH=/510-walter -t 510-walter .
docker run -d --name 510-walter --env-file .env -p 7860:7860 510-walter
```

## 环境变量

`.env` 不会提交。DeepSeek 真实链路需要：

```bash
OPENAI_API_KEY=your_deepseek_key
OPENAI_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-v4-flash
```

Dify RAG 稍后补充：

```bash
DIFY_BASE_URL=https://your-dify-instance/v1
DIFY_API_KEY=app-xxxxx
DIFY_KNOWLEDGE_API_KEY=dataset-xxxxx
DIFY_DATASET_ID=dataset-id
```

缺少 Dify 时，页面仍可运行，RAG Tab 会显示等待配置并使用本地 chunk 检索提示。

PDF/DOCX 上传转换会优先使用 Python `markitdown` 包；如果包不存在，会调用 `MARKITDOWN_BIN`，默认可指向 `/Users/walter/.local/bin/markitdown`。

## API

- `GET /health`
- `GET /api/config/status`
- `GET /api/textbooks`
- `GET /api/knowledge/graph/merged`
- `POST /api/integrate/start`
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
