"""
Định nghĩa tác tử CrewAI

CrewAI được dùng ở CHẾ ĐỘ TUẦN TỰ với vai trò hạn chế: điều phối việc gọi công
cụ theo thứ tự ĐÃ ĐƯỢC KIỂM CHỨNG TRƯỚC, không tự suy luận lại kế hoạch.

Cần hiện thực:
  1. Ba tác tử: Tác tử Tài liệu (doc.*, vision.*), Tác tử Dữ liệu (xlsx.*,
     report.*), Tác tử Kiểm soát (qc.*)
  2. Giới hạn phạm vi công cụ theo từng tác tử — lớp phòng vệ chống cấu hình
     sai
  3. build_crew(spec) -> Crew với Process.sequential
  4. Nếu CrewAI gây khó khăn: có thể thay bằng vòng lặp for đơn giản qua các
     bước. Kiến trúc không phụ thuộc vào CrewAI.
"""
