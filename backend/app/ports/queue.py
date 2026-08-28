"""
Cổng hàng đợi công việc

Giao diện trừu tượng cho hàng đợi. Bản hiện thực trên SQLite nằm ở adapters.

Cần hiện thực:
  1. enqueue(run_id, priority, available_at) -> job_id
  2. claim(worker_id, lease_seconds) -> Job | None
  3. complete(job_id) / fail(job_id, error, retry_after) -> None
  4. reap_expired() -> int — thu hồi job quá hạn giữ, trả về số lượng đã thu
     hồi
"""
