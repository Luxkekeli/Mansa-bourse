import { api, type User, ApiError } from './api';

let currentUser: User | null = null;

export function getUser(): User | null { return currentUser; }
export function isLoggedIn(): boolean { return currentUser !== null; }

export async function initAuth(): Promise<void> {
  try {
    const { user } = await api.me();
    currentUser = user;
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 401) console.warn('auth init', e);
    currentUser = null;
  }
}

export async function login(email: string, password: string, captchaToken = ''): Promise<User> {
  const { user } = await api.login(email, password, captchaToken);
  currentUser = user;
  return user;
}

export async function logout(): Promise<void> {
  await api.logout();
  currentUser = null;
}
