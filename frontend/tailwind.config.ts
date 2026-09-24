import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        // Chữ nội dung/số liệu — giữ Inter, hỗ trợ dấu tiếng Việt tốt.
        sans: ['Inter', 'Segoe UI', 'Noto Sans', 'system-ui', 'sans-serif'],
        // Chữ "nhãn thiết bị" — nhãn cột, tiêu đề khối, mã chứng từ: dùng mono
        // thật (không phải Consolas hệ thống) để đồng nhất cảm giác "đọc số
        // trên mặt đồng hồ đo" xuyên suốt toàn app, thay vì chỉ ở Dashboard.
        mono: ['"JetBrains Mono"', 'Consolas', 'DejaVu Sans Mono', 'monospace'],
      },
      colors: {
        ink:  { DEFAULT: '#16233C', soft: '#54637C', mute: '#7E8CA3', faint: '#9AA6B8' },
        line: { DEFAULT: '#E2E8F1', soft: '#F1F5FA' },
        // Bảng điều khiển (sidebar + khối "đồng hồ" Dashboard) — ngả sang
        // graphite/than chì thay vì xanh navy công sở, đúng chất "vỏ máy".
        nav:  { DEFAULT: '#17212B', hover: '#212F3B', text: '#AEC0C4', line: '#28363F' },
        // "brand" = tông đồng thau (brass) của kim/vành đồng hồ đo — thay cho
        // xanh dương chung chung. #96691F đã kiểm tỉ lệ tương phản với chữ
        // trắng đạt AA (~4.8:1) cho nút bấm chính.
        brand:{ DEFAULT: '#96691F', dark: '#7A5518', light: '#FBF1DE' },
      },
    },
  },
  plugins: [],
} satisfies Config
