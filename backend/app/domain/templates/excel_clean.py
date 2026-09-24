"""
Mẫu quy trình — Làm sạch và chuẩn hoá bảng tính

Quét thư mục lấy tệp Excel → gộp thành một bảng → chuẩn hoá (khoảng trắng,
ngày tháng, số tiền) → bỏ dòng trùng. Kết quả là tệp MỚI, không sửa tệp gốc.
"""

from app.domain.templates.base import TemplateEdge, TemplateStep, WorkflowTemplate

TEMPLATE = WorkflowTemplate(
    code="excel_clean",
    name="Làm sạch và chuẩn hoá bảng tính",
    description="Gộp các tệp Excel, chuẩn hoá dữ liệu và loại bỏ dòng trùng lặp.",
    examples=(
        "Gộp các tệp Excel bán hàng của chi nhánh thành một tệp và bỏ dòng trùng",
        "Làm sạch bảng tính khách hàng: bỏ khoảng trắng thừa, chuẩn hoá ngày tháng",
        "Chuẩn hoá số tiền trong các file Excel rồi xoá các dòng bị lặp theo mã khách hàng",
    ),
    default_trigger={"type": "manual"},
    steps=(
        TemplateStep(
            "scan_folder", "fs.list_new_files", "Lấy tệp Excel trong thư mục",
            {"path": "", "extensions": "xlsx", "only_new": False},
        ),
        TemplateStep("merge", "xlsx.merge_files", "Gộp các tệp thành một bảng", {}),
        TemplateStep("normalize", "xlsx.normalize", "Chuẩn hoá khoảng trắng, ngày, số tiền", {}),
        TemplateStep("dedupe", "xlsx.dedupe", "Loại bỏ dòng trùng", {"key_columns": ""}),
    ),
    edges=(
        TemplateEdge("scan_folder", "merge"),
        TemplateEdge("merge", "normalize"),
        TemplateEdge("normalize", "dedupe"),
    ),
    params={
        "scan_folder.path": "Thư mục chứa các tệp Excel",
        "dedupe.key_columns": "Tên các cột dùng xác định dòng trùng, cách nhau dấu phẩy "
        "(rỗng = so cả dòng)",
    },
)
