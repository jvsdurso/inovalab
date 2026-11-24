# NÃO testado no ambiente de desenvolvimento (sem acesso à rede/daemon). Revise antes de usar.
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY frontend frontend
ENV SINPIN_DB_PATH=/data/sinpin.db SINPIN_STORAGE_DIR=/data/arquivos SINPIN_FRONTEND_DIR=/app/frontend
WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "-m", "sinpin", "--host", "0.0.0.0", "--port", "8000"]
