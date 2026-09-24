"""
Mẫu quy trình — Đối chiếu hai tập dữ liệu

So khớp hai tệp Excel theo một cột khoá, xuất tệp kết quả gồm các dòng chỉ có
ở một bên và các dòng lệch giá trị.
"""

from app.domain.templates.base import TemplateStep, WorkflowTemplate

TEMPLATE = WorkflowTemplate(
    code="excel_reconcile",
    name="Đối chiếu hai tập dữ liệu",
    description="Đối chiếu hai tệp Excel theo cột khoá và liệt kê các dòng lệch.",
    examples=(
        "Mỗi thứ Hai lúc 9 giờ đối chiếu SoHoaDon.xlsx với CongNo.xlsx theo số hoá đơn",
        "So sánh sổ kế toán với sao kê ngân hàng theo mã giao dịch và báo dòng lệch",
        "Đối chiếu công nợ nhà cung cấp giữa hai file Excel",
    ),
    default_trigger={"type": "cron", "cron_expr": "0 9 * * 1", "timezone": "Asia/Ho_Chi_Minh"},
    steps=(
        TemplateStep(
            "reconcile", "xlsx.reconcile", "Đối chiếu hai tệp theo cột khoá",
            {"left_file": "", "right_file": "", "key_column": "", "compare_columns": ""},
        ),
    ),
    params={
        "reconcile.left_file": "Đường dẫn tệp Excel thứ nhất",
        "reconcile.right_file": "Đường dẫn tệp Excel thứ hai",
        "reconcile.key_column": "Tên cột khoá dùng để ghép dòng (vd. Số hoá đơn)",
        "reconcile.compare_columns": "Các cột cần so giá trị, cách nhau dấu phẩy "
        "(rỗng = mọi cột chung)",
    },
)
