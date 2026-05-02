import { api } from '../api';
import { t } from '../i18n';

export async function render(root: HTMLElement): Promise<void> {
  root.innerHTML = `<h1>${t('nav.dashboard', 'Dashboard')}</h1>
                    <div id="snapshot-status">${t('common.loading', 'Loading...')}</div>`;

  try {
    const snap = await api.marketSnapshot();
    const status = root.querySelector('#snapshot-status');
    if (status) {
      status.textContent =
        `${t('time.last_update', 'Last update')}: ${snap.date} — ` +
        `${snap.gainers.length} ${t('common.buy', 'gainers')} / ${snap.losers.length} ${t('common.sell', 'losers')}`;
    }
  } catch (e) {
    root.querySelector('#snapshot-status')!.textContent = t('error.network', 'Network error');
  }
}
