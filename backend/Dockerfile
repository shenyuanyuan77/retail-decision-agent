FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY web /web
COPY data /data
ENV RETAIL_DB=/data_local/retail.db \
    WEB_DIR=/web \
    KB_DIR=/data/kb
EXPOSE 8300
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8300"]
