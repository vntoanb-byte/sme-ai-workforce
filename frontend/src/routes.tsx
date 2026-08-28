/**
 * Bảng định tuyến — 10 tuyến đường.
 *
 * Đây là NƠI DUY NHẤT khai báo tuyến đường. Nguyên tắc chống phình: cửa sổ
 * tạo nhân viên AI (M-01) và ngăn nạp chứng từ (M-02) KHÔNG có tuyến đường
 * riêng — chúng là trạng thái tạm thời trên trang đang mở.
 *
 * Xem bảng index màn hình ở mục 2.3 của tài liệu Kế hoạch triển khai.
 */
import { lazy, Suspense } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { RequireAuth } from '@/hooks/useAuth'
import { Skeleton } from '@/components/ui/primitives'

import { LoginPage } from '@/features/auth/LoginPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { DocumentListPage } from '@/features/documents/DocumentListPage'
import { DocumentReviewPage } from '@/features/documents/DocumentReviewPage'
import { RunListPage } from '@/features/runs/RunListPage'
import { RunDetailPage } from '@/features/runs/RunDetailPage'
import { EmployeeListPage } from '@/features/employees/EmployeeListPage'
import { EmployeeDetailPage } from '@/features/employees/EmployeeDetailPage'

// Hai màn hình ít dùng nhất — nạp muộn để giảm kích thước gói ban đầu
const ReportPage = lazy(() => import('@/features/reports/ReportPage').then((m) => ({ default: m.ReportPage })))
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage').then((m) => ({ default: m.SettingsPage })))

const lazyWrap = (el: React.ReactNode) => (
  <Suspense fallback={<Skeleton className="h-96 w-full rounded-xl" />}>{el}</Suspense>
)

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <RequireAuth><AppShell /></RequireAuth>,
    children: [
      { index: true,               element: <DashboardPage /> },        // P-02
      { path: 'documents',         element: <DocumentListPage /> },     // P-05 (+ M-02)
      { path: 'documents/:id',     element: <DocumentReviewPage /> },   // P-06
      { path: 'runs',              element: <RunListPage /> },          // P-07
      { path: 'runs/:id',          element: <RunDetailPage /> },        // P-08
      { path: 'employees',         element: <EmployeeListPage /> },     // P-03 (+ M-01)
      { path: 'employees/:id',     element: <EmployeeDetailPage /> },   // P-04
      { path: 'reports',           element: lazyWrap(<ReportPage />) }, // P-09
      { path: 'settings',          element: lazyWrap(<SettingsPage />) },// P-10
    ],
  },
])
