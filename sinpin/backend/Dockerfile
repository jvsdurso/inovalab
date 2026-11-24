# Backend SINPIN (FastAPI + psycopg). NÃO foi construído no ambiente de desenvolvimento (sem daemon Docker): valide com `docker compose build`.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sinpin sinpin
ENV SINPIN_STORAGE_DIR=/data/arquivos SINPIN_HOST=0.0.0.0 SINPIN_PORT=8000
EXPOSE 8000
CMD ["python", "-m", "sinpin"]
