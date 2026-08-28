"""
Bộ biên dịch mô tả công việc thành quy trình

ĐÓNG GÓP CHÍNH CỦA ĐỀ TÀI. Chuyển câu tiếng Việt người dùng gõ thành
WorkflowSpec. Nguyên tắc: KHÔNG dùng vòng lặp tác tử tự chủ. Quy giản bài toán
lập kế hoạch thành hai bài toán dễ hơn nhiều: phân loại ý định và điền tham
số.

Cần hiện thực:
  1. classify_intent(text) -> template_code | None — gọi mô hình với schema là
     Literal của 5 mã mẫu; nếu không khớp mẫu nào thì trả None và báo lỗi thân
     thiện
  2. extract_params(text, template) -> WorkflowSpec — MỘT lời gọi duy nhất, có
     ràng buộc theo json_schema của WorkflowSpec, không vòng lặp
  3. Thử lại tối đa 3 lần, mỗi lần đính kèm thông báo lỗi cụ thể của lần trước
     vào prompt
  4. compile(text) -> tuple[WorkflowSpec | None, list[SpecError]] — hàm public
     duy nhất
  5. Ghi lại prompt_version vào kết quả để về sau so sánh được giữa các phiên
     bản prompt
"""
