/** 呼叫後端 API 的共用函式。路徑一律以 /api 開頭，開發時由 Vite proxy 轉給後端。 */

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(`API 錯誤 ${status}`)
    this.status = status
    this.detail = detail
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...init, headers })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    // 連不到伺服器（手機在外面時最常見）：說明要檢查什麼，而不是顯示看不懂的錯誤
    throw new ApiError(0, '連不到劃重點：請確認電腦開著、沒有睡眠，手機的 Tailscale 也已連線。')
  }
  const body = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(response.status, body?.detail ?? body)
  }
  return body as T
}

export const api = {
  get: <T>(path: string) => apiRequest<T>(path),
  post: <T>(path: string, data?: unknown) =>
    apiRequest<T>(path, { method: 'POST', body: data === undefined ? undefined : JSON.stringify(data) }),
  put: <T>(path: string, data: unknown) => apiRequest<T>(path, { method: 'PUT', body: JSON.stringify(data) }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: 'DELETE' }),
  postForm: <T>(path: string, form: FormData) => apiRequest<T>(path, { method: 'POST', body: form }),
}
