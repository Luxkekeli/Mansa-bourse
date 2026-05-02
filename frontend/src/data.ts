/**
 * P1-1 Vite scaffold — extracted ticker metadata.
 *
 * Long-term goal: this file is GENERATED at build time from the API
 * (`scripts/dump_tickers_to_data_ts.py`) so the bundle ships a fresh snapshot
 * AND the running app can hydrate from `/api/tickers` for live updates.
 *
 * For now this is a STUB — the live frontend continues to read the inline
 * `const S=[…]` array in `app.html`. When P1-1 lands fully, replace the
 * monolith section with `import { S } from './data';`.
 */

export interface TickerMeta {
  t: string;          // short ticker (SGBC)
  full: string;       // canonical full symbol (SGBC.ci)
  n: string;          // company name
  s: string;          // sector code (FIN/DIS/...)
  c: number;          // last close
  v1?: number;        // 1-day variation %
  vol?: number;
  cap?: number;
  per?: number;
  pbr?: number;
  roe?: number;
  rdtDiv?: number;    // dividend yield %
  div?: number;       // dividend amount FCFA
}

// Empty for now — the migration script populates this from the DB.
// Run: `python scripts/dump_tickers_to_data_ts.py`
export const S: TickerMeta[] = [];
