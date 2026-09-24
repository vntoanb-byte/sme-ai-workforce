"""
Mẫu quy trình — Đọc hoá đơn và nhập vào bảng tính

Quét thư mục → mô hình đọc hoá đơn → 8 quy tắc QC → hoá đơn ĐẠT ghi vào tệp
Excel (bản mới có dấu thời gian, không ghi đè tệp gốc); hoá đơn KHÔNG ĐẠT
chuyển sang chờ người xác nhận.
"""

from app.domain.templates.base import TemplateEdge, TemplateStep, WorkflowTemplate

TEMPLATE = WorkflowTemplate(
    code="invoice_to_excel",
    name="Đọc hoá đơn và nhập vào bảng tính",
    description="Đọc hoá đơn mới trong thư mục, kiểm tra số liệu rồi ghi vào tệp Excel.",
    examples=(
        "Mỗi sáng 8 giờ đọc hoá đơn mới trong thư mục Scan rồi nhập vào tệp SoHoaDon.xlsx",
        "Đọc các hoá đơn mua vào, kiểm tra tổng tiền rồi ghi vào Excel",
        "Nhập dữ liệu hoá đơn giá trị gia tăng từ ảnh chụp vào sổ theo dõi hoá đơn",
        "Khi có hoá đơn mới trong thư mục thì đọc và thêm vào bảng tính kế toán",
    ),
    default_trigger={"type": "cron", "cron_expr": "0 8 * * *", "timezone": "Asia/Ho_Chi_Minh"},
    steps=(
        TemplateStep(
            "scan_folder", "fs.list_new_files", "Lấy hoá đơn mới trong thư mục",
            {"path": "", "extensions": "jpg,jpeg,png,pdf"},
        ),
        TemplateStep(
            "read_invoice", "vision.extract_invoice", "AI đọc hoá đơn → dữ liệu có cấu trúc",
            {"schema_version": "invoice_v1"}, on_error="retry", retry_max=2,
        ),
        TemplateStep(
            "check_data", "qc.validate_invoice", "Đối chiếu tổng tiền, thuế, mã số thuế",
            {"rules": "QC-01..QC-08"},
        ),
        TemplateStep(
            "write_excel", "xlsx.append_rows", "Ghi hoá đơn đạt vào bảng tính",
            {"file": "SoHoaDon.xlsx", "sheet": "HoaDon"},
        ),
        TemplateStep(
            "to_review", "qc.escalate", "Chuyển sang chờ người xác nhận", {"assign_to": ""},
        ),
    ),
    edges=(
        TemplateEdge("scan_folder", "read_invoice"),
        TemplateEdge("read_invoice", "check_data"),
        TemplateEdge("check_data", "write_excel", "pass"),
        TemplateEdge("check_data", "to_review", "fail"),
    ),
    params={
        "scan_folder.path": "Thư mục chứa hoá đơn cần đọc trên máy chủ",
        "write_excel.file": "Tên hoặc đường dẫn tệp Excel đích (vd. SoHoaDon2026.xlsx)",
        "write_excel.sheet": "Tên trang tính (mặc định HoaDon)",
        "to_review.assign_to": "Tên đăng nhập người xác nhận (nếu mô tả có nêu)",
    },
)
