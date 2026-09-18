FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY script/ script/
COPY web/ web/

RUN mkdir -p /var/log/eloverblick

ENV JOB_LOG_PATH=/var/log/eloverblick/prices.log \
    PRICE_AREA=DK2 \
    JOB_INTERVAL_HOURS=6

EXPOSE 8080

CMD ["python", "-m", "web"]
