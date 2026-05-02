/**
 * Stub router. Real impl uses dynamic imports per tab so each tab is
 * code-split.
 *
 * Future: replace this with the goTab() / renderTab() dispatch from app.html.
 */

const TAB_LOADERS: Record<string, () => Promise<{ render: (root: HTMLElement) => void }>> = {
  dashboard: () => import('./tabs/dashboard'),
  // screener: () => import('./tabs/screener'),
  // portfolio: () => import('./tabs/portfolio'),
};

export function mountRouter(): void {
  const root = document.getElementById('app-root');
  if (!root) return;

  const route = () => {
    const hash = (location.hash || '#dashboard').slice(1);
    const loader = TAB_LOADERS[hash] || TAB_LOADERS.dashboard;
    loader().then(mod => mod.render(root)).catch(err => {
      root.textContent = `Error loading tab: ${err.message}`;
    });
  };

  window.addEventListener('hashchange', route);
  route();
}
