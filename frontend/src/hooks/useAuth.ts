/**
 * Điểm vào của tầng xác thực.
 *
 * Phần hiện thực nằm ở authProvider.tsx (có JSX nên phải đuôi .tsx).
 * Tệp này chỉ tái xuất, để mọi nơi khác import gọn: `@/hooks/useAuth`.
 */
export { AuthProvider, RequireAuth, useAuth } from './authProvider'
