.PHONY: help setup dev-api dev-web worker migrate test lint build eval

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:        ## Cài đặt phụ thuộc lần đầu
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm ci
	cp backend/.env.example backend/.env
	@echo "Nhớ điền LLM_API_KEY và JWT_SECRET vào backend/.env"

dev-api:      ## Chạy backend ở chế độ nạp lại nóng
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8080

dev-web:      ## Chạy giao diện ở chế độ phát triển
	cd frontend && npm run dev

worker:       ## Chạy tiến trình xử lý nền
	cd backend && .venv/bin/python -m app.workers.worker

migrate:      ## Sinh và áp dụng tệp di trú
	cd backend && .venv/bin/alembic revision --autogenerate -m "$(m)"
	cd backend && .venv/bin/alembic upgrade head

test:         ## Chạy toàn bộ kiểm thử
	cd backend && .venv/bin/pytest --cov=app --cov-report=term-missing

lint:         ## Kiểm tra chất lượng mã
	cd backend && .venv/bin/ruff check app tests && .venv/bin/mypy app
	cd frontend && npm run lint && npm run typecheck

build:        ## Build giao diện rồi dựng ảnh container
	cd frontend && npm run build
	docker build -t sme-ai-workforce:1.0.0 -f backend/Dockerfile .

eval:         ## Chạy bộ đánh giá và xuất kết quả ra CSV
	cd backend && .venv/bin/python scripts/eval_run.py --out ../eval/results.csv
