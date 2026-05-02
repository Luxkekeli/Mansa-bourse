/**
 * Typed wrappers around the MANSA backend.
 *
 * All requests use `credentials: 'include'` so the Flask session cookie is
 * sent. Errors are normalized into a single `ApiError` shape so callers can
 * pattern-match without inspecting status codes everywhere.
 */

export interface Ticker {
  symbol: string;
  name: string;
  sector: string;
  type: 'equity' | 'index';
  country: string;
  last_close: number | null;
  last_volume: number | null;
  last_date: string | null;
  prev_close: number | null;
  variation_pct: number;
}

export interface PricePoint {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  volume: number;
}

export interface User {
  id: number;
  email: string;
  prenom: string;
  nom: string;
  pays: string;
  profil: string;
  plan: string;
  email_verified: 0 | 1;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let body: any = {};
    try { body = await res.json(); } catch {}
    throw new ApiError(res.status, body.code ?? String(res.status), body.error ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  config: () => request<{ turnstile: { enabled: boolean; site_key: string }; payments_enabled: boolean }>('/api/config'),
  tickers: (filters: { sector?: string; country?: string; type?: string } = {}) => {
    const qs = new URLSearchParams(filters as any).toString();
    return request<{ count: number; tickers: Ticker[] }>(`/api/tickers${qs ? '?' + qs : ''}`);
  },
  ticker: (symbol: string) => request<{ ticker: Ticker; prices: PricePoint[] }>(`/api/ticker/${encodeURIComponent(symbol)}`),
  prices: (symbol: string, params: { from?: string; to?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<{ symbol: string; count: number; prices: PricePoint[] }>(
      `/api/prices/${encodeURIComponent(symbol)}${qs ? '?' + qs : ''}`,
    );
  },
  indices: () => request<{ indices: any[] }>('/api/indices'),
  marketSnapshot: () => request<{ date: string; gainers: any[]; losers: any[] }>('/api/market/snapshot'),
  search: (q: string) => request<{ results: any[] }>(`/api/search?q=${encodeURIComponent(q)}`),

  // Auth
  me: () => request<{ user: User }>('/api/auth/me'),
  login: (email: string, password: string, captcha_token = '') =>
    request<{ user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, captcha_token }),
    }),
  register: (data: Partial<User> & { password: string; captcha_token?: string }) =>
    request<{ user: User }>('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  logout: () => request<{ status: string }>('/api/auth/logout', { method: 'POST' }),

  // Community
  postMessage: (room: string, content: string, captcha_token = '') =>
    request<{ id: number; sanitized_content: string }>('/api/community/post', {
      method: 'POST',
      body: JSON.stringify({ room, content, captcha_token }),
    }),
  pollMessages: (room: string, since = '1970-01-01T00:00:00') =>
    request<{ messages: any[] }>(`/api/community/poll?room=${encodeURIComponent(room)}&since=${encodeURIComponent(since)}`),
};
