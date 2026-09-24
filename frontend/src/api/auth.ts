import { USE_MOCK, api, setAccessToken } from './client'
import type { TokenPair, User } from './types'

export async function login(username: string, password: string): Promise<User> {
  const res = await api.post<TokenPair>('/auth/login', { username, password })
  setAccessToken(res.access_token)
  return res.user
}

/** Thu hồi phiên ở máy chủ (refresh token + cookie), rồi xoá mã trong bộ nhớ. */
export async function logout(): Promise<void> {
  try {
    if (!USE_MOCK) await api.post<void>('/auth/logout')
  } finally {
    setAccessToken(null)
  }
}
