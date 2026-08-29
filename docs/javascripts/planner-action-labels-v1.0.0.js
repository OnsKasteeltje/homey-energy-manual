(() => {
  const enhance = root => {
    if (!root) return;
    root.querySelectorAll('.ps-action-segment').forEach(seg => {
      const title = String(seg.title || '');
      const match = title.match(/FORECAST\s*·\s*([^·]+)\s*·/);
      if (!match) return;
      const range = match[1].trim();
      const parts = range.split('–');
      const columns = String(seg.style.gridColumn || '').match(/(\d+)\s*\/\s*(\d+)/);
      const slots = columns ? Math.max(1, Number(columns[2]) - Number(columns[1])) : 1;
      seg.classList.toggle('ps-action-segment-short', slots < 5);
      seg.textContent = slots >= 5 ? range : (parts[0] || range).trim();
      seg.setAttribute('aria-label', `${range} ${title.split('·').slice(2).join('·').trim()}`.trim());
    });
  };

  const boot = () => {
    const root = document.getElementById('planner-shadow');
    if (!root) return;
    enhance(root);
    const observer = new MutationObserver(() => enhance(root));
    observer.observe(root, { childList: true, subtree: true });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
  document.addEventListener('DOMContentSwitch', boot);
})();
