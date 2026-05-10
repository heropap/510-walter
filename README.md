# 510 Walter

ModelScope-ready Gradio starter for a 5-hour solo AI hackathon.

## Local Run

Use Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://localhost:7860`.

## Model Config

The app runs even without a model key, using a local demo fallback so the page is always presentable.

For DashScope / Qwen compatible mode:

```bash
DASHSCOPE_API_KEY=your_key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-plus
```

For any OpenAI-compatible provider:

```bash
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://your-provider.example/v1
MODEL_NAME=your-model
```

## ModelScope Deploy

The deployment entry is `app.py`, and the container listens on port `7860`.

```bash
git lfs install
git add app.py Dockerfile requirements.txt README.md TASK_BRIEF.md .env.example .gitignore docs/
git commit -m "Prepare ModelScope hackathon starter"
git push
```

Use the ModelScope Studio Git URL from the ModelScope console when pushing to the deployment space.

## Competition Day Flow

1. Paste the directed challenge into `TASK_BRIEF.md`.
2. Put the same challenge into the app's "命题" field.
3. Build one complete demo path before adding optional features.
4. Keep all outputs, screenshots, and demo scripts under `outputs/` locally.
5. Freeze features in the final 30 minutes and focus on deployment plus demo.
