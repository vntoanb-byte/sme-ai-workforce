"""
Chạy bộ đánh giá

Chạy toàn bộ bộ dữ liệu đánh giá qua hệ thống và tính các chỉ số của Chương 8.

Cần hiện thực:
  1. Duyệt eval/dataset/, gọi đường ống trích xuất, so với eval/ground_truth/
  2. Công thức chính: độ chính xác theo trường = 1 − (số trường sai / tổng số
     trường)
  3. Chuẩn hoá trước khi so sánh: bỏ khoảng trắng thừa, chuẩn hoá ngày, bỏ dấu
     phân cách nghìn
  4. Xuất kết quả ra CSV để đưa thẳng vào báo cáo
  5. Tham số dòng lệnh --model để chạy lại với mô hình khác mà không sửa code
"""
