/**
 * API Client — 底层 fetch 封装
 *
 * 职责：构建 URL、序列化 query params、统一错误处理。
 * 业务层不直接调用此 client，而是通过 hooks/api/ 中的 TanStack Query hooks。
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

class APIError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`)
    this.name = 'APIError'
  }
}

function buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
  const url = new URL(`${API_BASE}${path}`)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value))
      }
    })
  }
  return url.toString()
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const res = await fetch(buildUrl(path, params))
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new APIError(res.status, text)
  }
  return res.json()
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new APIError(res.status, text)
  }
  return res.json()
}

export { APIError }
