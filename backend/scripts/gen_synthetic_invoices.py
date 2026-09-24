"""
Sinh hoá đơn tổng hợp

Phương án dự phòng khi không xin được hoá đơn thật từ doanh nghiệp:
  1. Sinh dữ liệu hoá đơn GTGT hợp lệ (tên doanh nghiệp/địa chỉ Việt Nam từ bộ từ
     vựng soạn sẵn — Faker vi_VN sinh tên kém tự nhiên; mã số thuế đúng chữ số
     kiểm tra; tổng tiền khớp 8 quy tắc QC) rồi dựng thành ảnh A4 150 dpi.
  2. Thêm nhiễu theo nhóm chất lượng: clean (sạch), noisy (xoay nhẹ, mờ, đổi độ
     sáng, nền giấy ngả màu).
  3. Xuất kèm ground truth JSON (đúng cấu trúc InvoiceExtraction + "quality") —
     được nhãn miễn phí cho bộ đánh giá (scripts/eval_run.py, eval/score.py).

Dùng:
    python scripts/gen_synthetic_invoices.py --count 50 --noisy-ratio 0.4
    → eval/dataset/syn_0001.png ... + eval/ground_truth/syn_0001.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.qc_rules import TAX_CODE_WEIGHTS  # noqa: E402
from app.utils.money import format_money  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial.ttf",
)
_PREFIX = ("Công ty TNHH", "Công ty Cổ phần", "Công ty TNHH MTV", "Doanh nghiệp tư nhân")
_TRADE = ("Thương mại", "Thiết bị Công nghiệp", "Vật tư Kỹ thuật", "Dịch vụ", "Cơ khí", "Điện")
_BRAND = ("Minh Long", "Đông Á", "Hoàng Gia", "Tân Tiến", "Phú Thịnh", "An Phát", "Việt Hưng",
          "Thành Công", "Bảo Minh", "Sao Việt", "Hưng Thịnh", "Nam Sơn")
_STREET = ("Lê Trọng Tấn", "Nguyễn Văn Linh", "Cộng Hoà", "Trường Chinh", "Lê Lợi",
           "Phạm Văn Đồng", "Nguyễn Trãi", "Hoàng Quốc Việt", "Điện Biên Phủ")
_AREA = ("P. Tây Thạnh, Q. Tân Phú, TP.HCM", "Q. Cầu Giấy, Hà Nội", "Q. Hải Châu, Đà Nẵng",
         "P. 13, Q. Tân Bình, TP.HCM", "Q. Thanh Xuân, Hà Nội", "TP. Biên Hoà, Đồng Nai")
_UNITS = ("Cái", "Bộ", "Hộp", "Kg", "Mét", "Gói", "Chiếc", "Lít")
_GOODS = (
    "Vòng bi SKF 6205-2RS",
    "Dây curoa A-1250",
    "Mỡ bôi trơn Shell Gadus",
    "Giấy in A4 Double A",
    "Mực in HP 12A",
    "Bulong inox M10",
    "Ống nhựa PVC D60",
    "Dịch vụ bảo trì máy lạnh",
    "Cáp điện Cadivi 2x2.5",
    "Thùng carton 5 lớp",
    "Găng tay bảo hộ",
    "Sơn Dulux nội thất",
)


def tax_code(rng: random.Random) -> str:
    """Mã số thuế 10 số có chữ số kiểm tra đúng thuật toán của domain/qc_rules.py."""
    while True:
        digits = [rng.randint(0, 9) for _ in range(9)]
        weighted = sum(d * w for d, w in zip(digits, TAX_CODE_WEIGHTS, strict=True))
        check = (10 - weighted % 11) % 11
        if check != 10:
            return "".join(map(str, digits)) + str(check)


def company(rng: random.Random) -> str:
    return f"{rng.choice(_PREFIX)} {rng.choice(_TRADE)} {rng.choice(_BRAND)}"


def address(rng: random.Random) -> str:
    return f"{rng.randint(1, 350)} {rng.choice(_STREET)}, {rng.choice(_AREA)}"


def make_invoice(rng: random.Random, index: int) -> dict[str, Any]:
    items = []
    for n in range(1, rng.randint(1, 5) + 1):
        qty = Decimal(rng.randint(1, 50))
        price = Decimal(rng.randint(10, 900) * 1000)
        items.append(
            {
                "line_no": n,
                "description": rng.choice(_GOODS),
                "unit": rng.choice(_UNITS),
                "quantity": str(qty),
                "unit_price": str(price),
                "amount": str(qty * price),
            }
        )
    subtotal = sum(Decimal(i["amount"]) for i in items)
    rate = Decimal(rng.choice((0, 5, 8, 10, 10, 8)))
    vat = (subtotal * rate / 100).quantize(Decimal("1"))
    return {
        "invoice_no": f"{rng.randint(1, 9_999_999):07d}",
        "invoice_form": f"1C{date.today():%y}T{rng.choice('ABCDEFGHK')}{rng.choice('ABCDEFGHK')}",
        "issue_date": (date.today() - timedelta(days=rng.randint(1, 60))).isoformat(),
        "currency": "VND",
        "seller": {"name": company(rng), "tax_code": tax_code(rng), "address": address(rng)},
        "buyer": {"name": company(rng), "tax_code": tax_code(rng), "address": None},
        "line_items": items,
        "totals": {
            "subtotal": str(subtotal),
            "vat_rate": str(rate),
            "vat_amount": str(vat),
            "total": str(subtotal + vat),
        },
    }


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for path in _FONTS:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render(data: dict[str, Any]) -> Image.Image:
    """Dựng ảnh hoá đơn A4 (1240×1754 ≈ 150 dpi)."""
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    big, mid, small = _font(40), _font(26), _font(22)
    d.text((620, 90), "HOÁ ĐƠN GIÁ TRỊ GIA TĂNG", font=big, fill="#8B1A1A", anchor="mm")
    issued = date.fromisoformat(data["issue_date"])
    d.text(
        (620, 150),
        f"Ngày {issued:%d} tháng {issued:%m} năm {issued:%Y}",
        font=small,
        fill="black",
        anchor="mm",
    )
    d.text((900, 200), f"Ký hiệu: {data['invoice_form']}", font=small, fill="black")
    d.text((900, 235), f"Số: {data['invoice_no']}", font=mid, fill="#8B1A1A")

    y = 300
    seller, buyer = data["seller"], data["buyer"]
    for label, value in (
        ("Đơn vị bán hàng", seller["name"]),
        ("Mã số thuế", seller["tax_code"]),
        ("Địa chỉ", seller["address"] or ""),
        ("Người mua (đơn vị)", buyer["name"]),
        ("Mã số thuế người mua", buyer["tax_code"]),
    ):
        d.text((80, y), f"{label}: {value}", font=small, fill="black")
        y += 42

    y += 20
    cols = (80, 150, 640, 760, 880, 1040, 1160)
    headers = ("STT", "Tên hàng hoá, dịch vụ", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền")
    d.rectangle((70, y - 8, 1170, y + 36), outline="black")
    for x, h in zip(cols, headers, strict=False):
        d.text((x, y), h, font=small, fill="black")
    y += 50
    for item in data["line_items"]:
        row = (
            str(item["line_no"]),
            item["description"],
            item["unit"],
            item["quantity"],
            format_money(Decimal(item["unit_price"])),
            format_money(Decimal(item["amount"])),
        )
        for x, v in zip(cols, row, strict=False):
            d.text((x, y), v, font=small, fill="black")
        y += 42
    d.line((70, y, 1170, y), fill="black")

    totals = data["totals"]
    y += 30
    for label, value in (
        ("Cộng tiền hàng", totals["subtotal"]),
        (
            f"Thuế suất GTGT: {Decimal(totals['vat_rate']).normalize():f}%   Tiền thuế GTGT",
            totals["vat_amount"],
        ),
        ("Tổng cộng tiền thanh toán", totals["total"]),
    ):
        d.text((500, y), f"{label}:", font=small, fill="black")
        d.text((1160, y), format_money(Decimal(value)), font=mid, fill="black", anchor="ra")
        y += 46
    return img


def add_noise(img: Image.Image, rng: random.Random) -> Image.Image:
    tint = Image.new("RGB", img.size, (rng.randint(235, 250), rng.randint(228, 242), 210))
    img = Image.blend(img, tint, 0.25)
    img = img.rotate(rng.uniform(-2.5, 2.5), expand=True, fillcolor=(240, 236, 220))
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.6, 1.4)))
    return ImageEnhance.Brightness(img).enhance(rng.uniform(0.85, 1.1))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--noisy-ratio", type=float, default=0.4)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--out", type=Path, default=ROOT / "eval")
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    (args.out / "dataset").mkdir(parents=True, exist_ok=True)
    (args.out / "ground_truth").mkdir(parents=True, exist_ok=True)
    for index in range(1, args.count + 1):
        data = make_invoice(rng, index)
        quality = "noisy" if rng.random() < args.noisy_ratio else "clean"
        img = render(data)
        if quality == "noisy":
            img = add_noise(img, rng)
        stem = f"syn_{index:04d}"
        img.save(args.out / "dataset" / f"{stem}.png")
        truth = {**data, "quality": quality}
        (args.out / "ground_truth" / f"{stem}.json").write_text(
            json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"Đã sinh {args.count} hoá đơn vào {args.out}")


if __name__ == "__main__":
    main()
