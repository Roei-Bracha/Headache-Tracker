FROM python:3.11-slim

RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Jerusalem

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auth.py bot.py config.py database.py handlers.py weather.py ./

RUN mkdir -p /app/data

CMD ["python", "bot.py"]
