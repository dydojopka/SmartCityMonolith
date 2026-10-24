FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home monolith \
    && mkdir /data \
    && chown monolith:monolith /data

COPY app ./app
COPY tests ./tests
COPY pytest.ini .
USER monolith

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
