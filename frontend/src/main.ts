/**
 * MANSA — entry point (Vite scaffold, P1-1).
 *
 * This is the future entry point for the modular frontend. It's NOT yet wired
 * to the live `app.html` — that file continues to ship the monolith. Once we
 * port a tab to a module, we import it from here and remove the equivalent
 * code block from app.html.
 *
 * Order of migration (see docs/VITE_MIGRATION.md):
 *   1. data.ts         — extract `S=[...]` array (✅ scaffolded)
 *   2. i18n.ts         — extract translation dictionaries
 *   3. auth.ts         — extract login/register/me wrappers
 *   4. api.ts          — fetch helpers + types
 *   5. tabs/dashboard.ts, tabs/screener.ts, …
 *   6. main.ts         — replace app.html monolith with this entry
 */

import './styles/global.css';
import { initI18n } from './i18n';
import { initAuth } from './auth';
import { mountRouter } from './router';

async function bootstrap() {
  initI18n();
  await initAuth();
  mountRouter();

  // Service worker registration (unchanged from current app.html).
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  }
}

document.addEventListener('DOMContentLoaded', bootstrap);
