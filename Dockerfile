FROM python:3.11-slim

WORKDIR /app

# 시스템 라이브러리 설치 (필요한 경우)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# Azure App Service는 기본적으로 80번 포트를 기대하지만, 
# 설정을 통해 변경 가능합니다. 여기서는 8000번을 사용합니다.
EXPOSE 8000

# uvicorn 실행 (WebSockets를 위해 standard worker 사용)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
