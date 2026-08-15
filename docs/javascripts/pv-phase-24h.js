document.addEventListener('DOMContentLoaded', async () => {
  const root = document.getElementById('pv-phase-24h');
  if (!root) return;

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (v, d=3) => Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—';
  const fmtDate = (v) => {
    if (!v) return 'Nog geen publicatie';
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? esc(v) : d.toLocaleString('nl-NL');
  };

  try {
    const res = await fetch('../data/pv-phase-24h.json?ts=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const a = data.analysis || {};
    const rows = Object.entries(a).map(([name, r]) => {
      const score = Number.isFinite(Number(r.best_score)) ? Number(r.best_score).toFixed(3) : '—';
      const margin = Number.isFinite(Number(r.margin)) ? Number(r.margin).toFixed(3) : '—';
      return `<tr><td>${esc(name)}</td><td><strong>${esc(r.best_phase || '—')}</strong></td><td>${esc(r.confidence || '—')}</td><td>${score}</td><td>${margin}</td></tr>`;
    }).join('');

    const detail = Object.entries(a).map(([name, r]) => {
      const sr = Array.isArray(r.scores) ? r.scores : [];
      const items = sr.map(s => `<li><strong>${esc(s.phase)}</strong>: corr ${fmt(s.correlation)}, Δ-corr ${fmt(s.delta_correlation)}</li>`).join('');
      return `<details><summary>${esc(name)}</summary><ul>${items || '<li>Nog geen scores</li>'}</ul></details>`;
    }).join('');

    root.innerHTML = `
      <div class="phase-live-meta">
        <strong>Laatste publicatie:</strong> ${fmtDate(data.generated_at)} ·
        <strong>samples:</strong> ${esc(data.sample_count ?? 0)} ·
        <strong>venster:</strong> ${esc(data.window_hours ?? 24)} uur
      </div>
      ${rows ? `<div class="phase-table-wrap"><table><thead><tr><th>Omvormer</th><th>Beste fase</th><th>Confidence</th><th>Score</th><th>Marge</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<p><em>Nog geen 24-uursanalyse beschikbaar. De Homey-publisher wacht op voldoende meetdata.</em></p>'}
      ${detail}
    `;
  } catch (e) {
    root.innerHTML = `<p><em>Live fase-analyse kon niet worden geladen: ${esc(e.message)}</em></p>`;
  }
});
