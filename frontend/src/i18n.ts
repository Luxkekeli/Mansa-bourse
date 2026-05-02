/**
 * Vite-friendly i18n module. Pulls JSON dictionaries via Vite's import.meta.glob
 * for tree-shaking. The current monolith ships dicts inline; this is the future
 * shape.
 */

const FR = (await import('./i18n/fr.json', { with: { type: 'json' } })).default;
const EN = (await import('./i18n/en.json', { with: { type: 'json' } })).default;

const DICTS = { fr: FR, en: EN } as const;
type Lang = keyof typeof DICTS;
let currentLang: Lang = 'fr';

export function initI18n(): void {
  const stored = (typeof localStorage !== 'undefined' ? localStorage.getItem('mansa_lang') : null) as Lang | null;
  if (stored && stored in DICTS) {
    currentLang = stored;
  } else {
    const nav = (navigator?.language || 'fr').toLowerCase();
    currentLang = nav.startsWith('en') ? 'en' : 'fr';
  }
  document.documentElement.lang = currentLang;
}

export function t(key: string, fallback?: string): string {
  const dict = DICTS[currentLang] || DICTS.fr;
  return (dict as any)[key] || fallback || (DICTS.fr as any)[key] || key;
}

export function switchLang(): void {
  currentLang = currentLang === 'fr' ? 'en' : 'fr';
  try { localStorage.setItem('mansa_lang', currentLang); } catch {}
  document.documentElement.lang = currentLang;
}

export function getLang(): Lang { return currentLang; }
