"""
Thu hồi công việc treo

Đưa các job đã quá hạn giữ về trạng thái chờ để worker khác nhận lại.

Cần hiện thực:
  1. reap() gọi queue.reap_expired(), ghi log số lượng đã thu hồi
  2. Nếu attempts >= max_attempts thì chuyển thẳng sang failed kèm lý do 'hết
     hạn giữ việc'
"""
