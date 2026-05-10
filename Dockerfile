FROM modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/python:3.10

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV GRADIO_ANALYTICS_ENABLED=False

WORKDIR /home/user/app

COPY requirements.txt /home/user/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ /home/user/app

EXPOSE 7860
ENTRYPOINT ["python", "-u", "app.py"]
