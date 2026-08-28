"""
Bộ chuyển đổi hàng đợi trên SQLite

TỆP QUAN TRỌNG NHẤT CỦA BACKEND. Hiện thực giao thức giành việc trên SQLite.
Lưu ý: SQLite KHÔNG có SELECT ... FOR UPDATE SKIP LOCKED như PostgreSQL, nên
phải dùng cách khác — xem phần Cần hiện thực.

Cần hiện thực:
  1. claim(): mở transaction bằng BEGIN IMMEDIATE để giành khoá ghi NGAY LẬP
     TỨC
  2. SELECT id FROM job_queue WHERE status='pending' AND available_at<=now
     ORDER BY priority DESC, id ASC LIMIT 1
  3. UPDATE job_queue SET status='claimed', claimed_by=?, lease_until=?,
     attempts=attempts+1 WHERE id=? AND status='pending' — rồi KIỂM TRA
     rowcount
  4. Nếu rowcount == 0 nghĩa là worker khác đã giành mất: COMMIT và trả về None
  5. fail(): tính thời gian lùi backoff = min(30 * 2**attempt, 900) + nhiễu
     ngẫu nhiên, đặt available_at = now + backoff, trả trạng thái về pending
  6. Nếu attempts >= max_attempts: chuyển status='failed', KHÔNG thử lại nữa
  7. reap_expired(): UPDATE ... SET status='pending' WHERE status='claimed' AND
     lease_until < now
  8. enqueue() PHẢI dùng chung Session với việc tạo bản ghi runs — cùng một
     commit, để không bao giờ có run mà thiếu job hoặc ngược lại
"""
