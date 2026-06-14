FROM docker.m.daocloud.io/library/python:3.13-slim

# apt 国内镜像源（USTC）
RUN sed -i 's|deb.debian.org|mirrors.ustc.edu.cn|g' /etc/apt/sources.list.d/debian.sources

# pip 国内镜像源（清华）
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 系统依赖（中文支持 + Pillow）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-wqy-zenhei \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY src/ src/
COPY .env.example .env.example

# 创建运行时目录
RUN mkdir -p uploads exports/images exports/images/.cache data/bom logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/').raise_for_status()" || exit 1

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
