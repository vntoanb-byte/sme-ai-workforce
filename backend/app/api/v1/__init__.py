"""
Gộp router phiên bản v1

Tạo APIRouter tổng và include các router con theo đúng tiền tố.
"""

from fastapi import APIRouter

from app.api.v1 import documents

api_router = APIRouter()
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
# 7 router còn lại (auth, employees, workflows, runs, reviews, reports, tools,
# admin) CHƯA include — file vẫn là docstring stub, hiện thực dần theo từng
# task trong IMPLEMENTATION_PLAN.md. Chỉ mount router documents theo quyết định
# cắt phạm vi TASK-006.

