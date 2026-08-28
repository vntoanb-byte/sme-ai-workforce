"""
Gộp router phiên bản v1

Tạo APIRouter tổng và include tất cả router con theo đúng tiền tố.

Cần hiện thực:
  1. from fastapi import APIRouter; api_router = APIRouter()
  2. api_router.include_router(auth.router, prefix='/auth', tags=['auth'])
  3. Lặp lại cho employees, workflows, documents, runs, reviews, reports,
     tools, admin
"""
