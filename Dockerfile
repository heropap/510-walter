FROM node:22-bookworm AS frontend-build

ARG APP_BASE_PATH=
ENV APP_BASE_PATH=${APP_BASE_PATH}
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/python:3.10

ARG APP_BASE_PATH=
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_BASE_PATH=${APP_BASE_PATH}

WORKDIR /home/user/app

COPY requirements.txt /home/user/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ /home/user/app
COPY --from=frontend-build /app/frontend/dist /home/user/app/frontend/dist

EXPOSE 7860
ENTRYPOINT ["python", "-u", "app.py"]
