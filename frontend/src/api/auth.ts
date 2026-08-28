import { api, setAccessToken } from './client'
import type { TokenPair, User } from './types'

export async function login(username: string, password: string): Promise<User> {
  const res = await api.post<TokenPair>('/auth/login', { username, password })
  setAccessToken(res.access_token)
  return res.user
}

export function logout(): void {
  setAccessToken(null)
}
