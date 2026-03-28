FROM python:3.11-slim

# 设置时区
RUN apt-get update && apt-get install -y tzdata && \
    cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone && \
    apt-get clean

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖（使用国内镜像源）
RUN pip config set global.index-url http://mirrors.cloud.tencent.com/pypi/simple && \
    pip config set global.trusted-host mirrors.cloud.tencent.com && \
    pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 暴露端口
EXPOSE 8080

# 启动命令：生成报告
CMD ["python", "-m", "market_monitor", "--macro"]
