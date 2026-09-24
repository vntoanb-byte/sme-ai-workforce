"""
Mẫu quy trình — Đọc hoá đơn và lập báo cáo định kỳ

Quét thư mục → đọc hoá đơn → QC → hoá đơn ĐẠT được tổng hợp thành báo cáo
Excel + PDF theo kỳ; hoá đơn KHÔNG ĐẠT chuyển sang chờ xác nhận.
"""

from app.domain.templates.base import TemplateEdge, TemplateStep, WorkflowTemplate

TEMPLATE = WorkflowTemplate(
    code="invoice_report",
    name="Đọc hoá đơn và lập báo cáo định kỳ",
    description="Đọc hoá đơn mới, kiểm tra rồi lập báo cáo tổng hợp Excel và PDF theo kỳ.",
    examples=(
        "Cuối mỗi ngày lúc 17h30 tổng hợp hoá đơn đã xử lý trong ngày thành báo cáo Excel và PDF",
        "Mỗi tháng lập báo cáo tổng hợp hoá đơn theo nhà cung cấp",
        "Đọc hoá đơn trong thư mục rồi làm báo cáo chi phí theo tháng",
        "Lập báo cáo thuế giá trị gia tăng theo thuế suất vào cuối tuần",
    ),
    default_trigger={"type": "cron", "cron_expr": "30 17 * * *", "timezone": "Asia/Ho_Chi_Minh"},
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
            "build_report", "report.build_xlsx", "Lập báo cáo tổng hợp Excel",
            {"period": "today", "group_by": "seller"},
        ),
        TemplateStep(
            "export_pdf", "report.build_pdf", "Xuất báo cáo PDF",
            {"period": "today", "group_by": "seller"},
        ),
        TemplateStep(
            "to_review", "qc.escalate", "Chuyển sang chờ người xác nhận", {"assign_to": ""},
        ),
    ),
    edges=(
        TemplateEdge("scan_folder", "read_invoice"),
        TemplateEdge("read_invoice", "check_data"),
        TemplateEdge("check_data", "build_report", "pass"),
        TemplateEdge("build_report", "export_pdf"),
        TemplateEdge("check_data", "to_review", "fail"),
    ),
    params={
        "scan_folder.path": "Thư mục chứa hoá đơn cần đọc trên máy chủ",
        "build_report.period": "Kỳ báo cáo: today | this_week | this_month | last_month",
        "build_report.group_by": "Nhóm theo: seller | month | vat_rate",
        "export_pdf.period": "Giống build_report.period",
        "export_pdf.group_by": "Giống build_report.group_by",
    },
)
