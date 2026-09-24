/**
 * Dấu hiệu nhận diện — mặt đồng hồ đo với kim chỉ, thay cho khối gradient
 * xanh-tím chung chung trước đây. Gợi "kim đo" trên bảng điều khiển: hệ
 * thống đang quan sát và báo cáo, không phải một sản phẩm SaaS bất kỳ.
 * Dùng chung ở Sidebar (AppShell) và LoginPage để nhất quán.
 */
export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden
      className="shrink-0"
    >
      <circle cx="16" cy="16" r="14.5" fill="#0F1820" stroke="#96691F" strokeWidth="1.5" />
      {/* Vạch chia độ quanh mặt đồng hồ */}
      {Array.from({ length: 12 }).map((_, i) => {
        const angle = (i * 30 * Math.PI) / 180
        const inner = 10.5
        const outer = i % 3 === 0 ? 8.7 : 9.6
        return (
          <line
            key={i}
            x1={16 + inner * Math.sin(angle)}
            y1={16 - inner * Math.cos(angle)}
            x2={16 + outer * Math.sin(angle)}
            y2={16 - outer * Math.cos(angle)}
            stroke="#6B4F22"
            strokeWidth={i % 3 === 0 ? 1.1 : 0.7}
            strokeLinecap="round"
          />
        )
      })}
      {/* Kim chỉ — cố định ở vị trí ~10 giờ, dừng trong vùng an toàn (ẩn dụ hệ
          thống đang ở trạng thái ổn định) */}
      <line x1="16" y1="16" x2="10.5" y2="9.5" stroke="#E4B25A" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="16" cy="16" r="1.6" fill="#E4B25A" />
    </svg>
  )
}
