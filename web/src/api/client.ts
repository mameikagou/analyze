/**
 * API Client 骨架
 *
 * 后续对接后端 REST API 或 tRPC。
 * 目前仅作为目录占位，实际请求走 TanStack Query 的 queryFn。
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}
