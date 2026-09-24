"""
Gộp router phiên bản v1

Tạo APIRouter tổng và include các router con theo đúng tiền tố.
"""

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    documents,
    employees,
    reports,
    reviews,
    runs,
    tools,
    workflows,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
