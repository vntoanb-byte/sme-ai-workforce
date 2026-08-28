#!/usr/bin/env bash
# Đóng gói toàn bộ hệ thống để cài đặt trong mạng KHÔNG có Internet.
# Chạy trên máy CÓ Internet, kết quả chép sang máy chủ đích bằng ổ cứng di động.
set -euo pipefail

OUT=./bundle
mkdir -p "$OUT"

echo "[1/4] Tải ảnh container..."
docker pull vllm/vllm-openai:v0.11.0
docker build -t sme-ai-workforce:1.0.0 -f ../backend/Dockerfile ..

echo "[2/4] Xuất ảnh ra tệp (khoảng 8-10 GB)..."
docker save vllm/vllm-openai:v0.11.0 sme-ai-workforce:1.0.0 | gzip > "$OUT/images.tar.gz"

echo "[3/4] Chép trọng số mô hình (khoảng 6 GB)..."
cp -r ../models "$OUT/"

echo "[4/4] Chép cấu hình..."
cp docker-compose.yml nginx.conf "$OUT/"
cp ../backend/.env.example "$OUT/.env"

echo "Xong. Tổng dung lượng:"; du -sh "$OUT"
echo "Trên máy đích chạy: gunzip -c images.tar.gz | docker load && docker compose up -d"
