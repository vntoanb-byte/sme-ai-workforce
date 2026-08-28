"""
Chấm điểm bộ đánh giá

Tính các chỉ số của Chương 8 bằng cách so kết quả hệ thống với nhãn chuẩn.

Cần hiện thực:
  1. Chỉ số chính: độ chính xác theo trường = 1 − (số trường sai / tổng số
     trường)
  2. Chuẩn hoá TRƯỚC khi so: bỏ khoảng trắng thừa, ngày về ISO-8601, bỏ dấu
     phân cách nghìn, tên riêng về dạng không phân biệt hoa thường
  3. Trường tiền tệ: so bằng Decimal, sai lệch phải bằng 0 mới tính đúng
  4. Dòng hàng: tính độ chính xác và độ bao phủ trên tập dòng, không so theo
     thứ tự
  5. Xuất bảng kết quả theo từng nhóm chất lượng ảnh để thấy mô hình yếu ở đâu
"""
