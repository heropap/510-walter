import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import gradio as gr

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in deployed containers
    load_dotenv = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - lets the app run before dependencies install
    OpenAI = None


if load_dotenv:
    load_dotenv()


APP_TITLE = "510 Walter AI Hackathon Starter"
DEFAULT_MODEL = os.getenv("MODEL_NAME") or os.getenv("OPENAI_MODEL") or "qwen-plus"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MAX_FILE_CHARS = 12000
OUTPUT_DIR = Path("outputs")


SYSTEM_PROMPT = """你是一个面向 AI 黑客松的产品与工程搭档。
你的回答要直接服务于 5 小时单人开发：先给可演示的核心方案，再给最小可行实现路径。
优先输出结构化内容，包括用户价值、核心流程、数据/模型假设、MVP 功能、演示脚本和风险。
不要泛泛而谈，所有建议都要能落到当前命题和输入材料上。"""


def _first_non_empty(values: Iterable[Optional[str]]) -> Optional[str]:
    for value in values:
        if value:
            value = value.strip()
            if value:
                return value
    return None


def provider_config() -> dict:
    api_key = _first_non_empty(
        [
            os.getenv("OPENAI_API_KEY"),
            os.getenv("DASHSCOPE_API_KEY"),
            os.getenv("MODELSCOPE_API_KEY"),
        ]
    )
    base_url = _first_non_empty(
        [
            os.getenv("OPENAI_BASE_URL"),
            DEFAULT_BASE_URL if os.getenv("DASHSCOPE_API_KEY") else None,
        ]
    )
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": DEFAULT_MODEL,
        "ready": bool(api_key and OpenAI),
    }


def provider_status() -> str:
    config = provider_config()
    if config["ready"]:
        endpoint = config["base_url"] or "OpenAI default endpoint"
        return f"模型已配置\n\n- model: `{config['model']}`\n- endpoint: `{endpoint}`"
    if not OpenAI:
        return "演示模式\n\n`openai` 依赖未安装，安装依赖后可启用真实模型调用。"
    return "演示模式\n\n未检测到 API Key。配置 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY` 后会自动调用真实模型。"


def read_uploaded_files(files: Optional[List[object]]) -> str:
    if not files:
        return ""

    chunks = []
    remaining = MAX_FILE_CHARS
    for item in files:
        if remaining <= 0:
            break
        file_path = Path(getattr(item, "name", str(item)))
        if not file_path.exists():
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            chunks.append(f"\n\n[文件读取失败: {file_path.name}: {exc}]")
            continue
        text = text[:remaining]
        remaining -= len(text)
        chunks.append(f"\n\n## 文件: {file_path.name}\n{text}")
    return "".join(chunks)


def build_messages(problem: str, context: str, uploaded_text: str, task: str) -> list:
    user_content = f"""# 黑客松命题
{problem.strip() or "待补充"}

# 业务/用户/数据上下文
{context.strip() or "暂无"}

# 上传材料摘录
{uploaded_text.strip() or "暂无"}

# 当前要完成的任务
{task.strip() or "请生成可演示的 MVP 方案和实现路径。"}
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def demo_fallback(problem: str, context: str, task: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    problem_text = problem.strip() or "比赛命题待填"
    task_text = task.strip() or "生成 MVP 方案和实现路径"
    context_text = context.strip() or "暂无补充材料"

    return f"""# 本地演示模式输出

生成时间：{now}

## 当前命题
{problem_text}

## 当前任务
{task_text}

## 可直接展开的 MVP 框架
1. 用户输入：把命题相关资料、用户场景或数据文件放到左侧输入区。
2. AI 分析：抽取问题、目标用户、约束条件和可自动化的关键步骤。
3. 交付结果：输出方案、流程、风险、演示话术和下一步工程任务。
4. 演示闭环：用一组样例输入跑通从“输入问题”到“生成可执行结果”的全流程。

## 5 小时实现建议
1. 第 0.5 小时：锁定目标用户、输入输出和演示样例。
2. 第 1.5 小时：实现最小主流程，只保留一条可讲清楚的路径。
3. 第 2.5 小时：补齐结果展示、错误处理、样例数据和部署。
4. 第 3.5 小时：打磨演示脚本、首页文案和关键截图。
5. 第 4.5 小时：冻结功能，专注验证、录屏和提交材料。

## 已收到的上下文摘录
{context_text[:1200]}

配置 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY` 后，此区域会切换为真实模型输出。"""


def save_result(problem: str, task: str, output: str) -> str:
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"run_{stamp}.md"
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "problem": problem,
        "task": task,
        "output": output,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"\n\n---\n已保存到 `{path}`"


def run_assistant(
    problem: str,
    context: str,
    task: str,
    files: Optional[List[object]],
    model_name: str,
    temperature: float,
    should_save: bool,
) -> str:
    uploaded_text = read_uploaded_files(files)
    messages = build_messages(problem, context, uploaded_text, task)
    config = provider_config()
    model = model_name.strip() or config["model"]

    if config["ready"]:
        try:
            client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            output = response.choices[0].message.content or ""
        except Exception as exc:
            output = (
                f"# 模型调用失败\n\n`{exc}`\n\n"
                "已回退到本地演示模式，先保证比赛现场页面可用。\n\n"
                + demo_fallback(problem, context, task)
            )
    else:
        output = demo_fallback(problem, context, task)

    if should_save:
        output += save_result(problem, task, output)
    return output


def build_app() -> gr.Blocks:
    with gr.Blocks(title=APP_TITLE, theme=gr.themes.Soft()) as demo:
        gr.Markdown(f"# {APP_TITLE}")
        with gr.Row():
            with gr.Column(scale=2):
                problem = gr.Textbox(
                    label="命题",
                    placeholder="比赛开始后粘贴定向命题",
                    lines=4,
                )
                context = gr.Textbox(
                    label="上下文 / 数据摘录",
                    placeholder="粘贴用户画像、业务背景、样例数据、评审标准等",
                    lines=10,
                )
                files = gr.File(
                    label="资料文件",
                    file_count="multiple",
                    file_types=[".txt", ".md", ".csv", ".json", ".log"],
                )
                task = gr.Textbox(
                    label="当前任务",
                    value="请基于命题生成可演示的 MVP 方案、核心流程、实现步骤和 2 分钟演示脚本。",
                    lines=3,
                )
            with gr.Column(scale=1):
                status = gr.Markdown(provider_status())
                model = gr.Textbox(label="模型", value=DEFAULT_MODEL)
                temperature = gr.Slider(
                    label="温度",
                    minimum=0,
                    maximum=1,
                    step=0.05,
                    value=0.35,
                )
                should_save = gr.Checkbox(label="保存输出", value=True)
                run = gr.Button("生成", variant="primary")
                clear = gr.Button("清空", variant="secondary")

        output = gr.Markdown(label="输出")

        with gr.Accordion("比赛日检查清单", open=False):
            gr.Markdown(
                """1. 命题粘贴到输入区，并压缩成一句话目标。
2. 先跑通一条完整演示路径，再扩展功能。
3. 每完成一个可演示节点就提交一次 Git。
4. 部署前确认端口为 `7860`，入口为 `app.py`。
5. 演示材料保留：问题、方案、截图、录屏、仓库链接、部署链接。"""
            )

        run.click(
            fn=run_assistant,
            inputs=[problem, context, task, files, model, temperature, should_save],
            outputs=output,
        )
        clear.click(
            fn=lambda: ("", "", None, ""),
            outputs=[problem, context, files, output],
        )
    return demo


demo = build_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=port,
        prevent_thread_lock=True,
    )
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
