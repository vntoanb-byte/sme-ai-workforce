# Build với context = GỐC REPO (deploy/docker-compose*.yml và Makefile đều
# dùng `context: ..` / `-f backend/Dockerfile .`), nên mọi COPY đều có tiền tố
# backend/ hoặc frontend/.
#
# Stage 1: build giao diện (kết quả /app/dist)
FROM node:22-alpine AS frontend-build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: backend
FROM python:3.11-slim

# Thư viện hệ thống cho opencv và pypdfium2; fonts-dejavu-core: phông có dấu tiếng
# Việt cho báo cáo PDF (ReportLab) — thiếu phông thì PDF mất dấu.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
# Mạng chậm: nới timeout tải gói (mặc định 15s từng làm build gãy giữa chừng)
ENV PIP_DEFAULT_TIMEOUT=300
RUN pip install --no-cache-dir --retries 10 -r requirements.txt

COPY backend/ .
# Giao diện đã build được chép vào đây từ stage 1
COPY --from=frontend-build /app/dist ./static

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
    CMD curl -f http://localhost:8080/health || exit 1

# Tiến trình API (tự chạy migration + seed khi khởi động). Tiến trình xử lý nền dùng
# CÙNG ảnh này với lệnh `python -m app.workers.worker` (xem deploy/docker-compose.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
