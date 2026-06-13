FROM python:3.13-slim

WORKDIR /app

# 系统依赖（中文支持 + Pillow）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-wqy-zenhei \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY src/ src/
COPY .env.example .env.example

# 创建运行时目录
RUN mkdir -p uploads exports/images exports/images/.cache data/bom logs

EXPOSE 8000

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
