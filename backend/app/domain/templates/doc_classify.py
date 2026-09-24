"""
Mẫu quy trình — Phân loại và sắp xếp tài liệu

Quét thư mục → mô hình phân loại từng tài liệu vào tập nhãn cho trước → xuất
bảng phân loại (Excel) để sắp xếp.
"""

from app.domain.templates.base import TemplateEdge, TemplateStep, WorkflowTemplate

TEMPLATE = WorkflowTemplate(
    code="doc_classify",
    name="Phân loại và sắp xếp tài liệu",
    description="Phân loại tài liệu quét được vào các nhóm cho trước và lập bảng phân loại.",
    examples=(
        "Phân loại các tài liệu scan thành hoá đơn, hợp đồng, phiếu thu, phiếu chi",
        "Sắp xếp chứng từ trong thư mục theo loại tài liệu",
        "Nhận diện loại giấy tờ trong thư mục Scan và lập danh sách",
    ),
    default_trigger={"type": "manual"},
    steps=(
        TemplateStep(
            "scan_folder", "fs.list_new_files", "Lấy tài liệu mới trong thư mục",
            {"path": "", "extensions": "jpg,jpeg,png,pdf"},
        ),
        TemplateStep(
            "classify", "vision.classify_document", "AI phân loại tài liệu",
            {"labels": "hoa_don,hop_dong,phieu_thu,phieu_chi,khac"},
            on_error="retry", retry_max=2,
        ),
    ),
    edges=(TemplateEdge("scan_folder", "classify"),),
    params={
        "scan_folder.path": "Thư mục chứa tài liệu cần phân loại",
        "classify.labels": "Danh sách nhãn phân loại, cách nhau dấu phẩy, dạng không dấu",
    },
)
