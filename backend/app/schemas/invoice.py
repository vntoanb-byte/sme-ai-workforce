"""
Lược đồ dữ liệu hoá đơn

Cấu trúc dữ liệu hoá đơn giá trị gia tăng Việt Nam, có đánh số phiên bản.

Cần hiện thực:
  1. SCHEMA_VERSION = 'invoice_v1' — tăng khi thay đổi cấu trúc, KHÔNG sửa tại
     chỗ
  2. class Party: name, tax_code (pattern 10 hoặc 13 số), address
  3. class LineItem: line_no, description, unit, quantity, unit_price, amount
  4. class Totals: subtotal, vat_rate (Literal 0|5|8|10), vat_amount, total
  5. class InvoiceExtraction: invoice_no, invoice_form, issue_date, currency,
     seller, buyer, line_items, totals
  6. Dùng Decimal cho mọi trường tiền tệ, KHÔNG dùng float
"""
