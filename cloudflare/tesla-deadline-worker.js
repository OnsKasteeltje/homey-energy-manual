const OWNER = 'OnsKasteeltje';
const REPO = 'homey-energy-manual';
const BRANCH = 'main';
const PATH = 'docs/data/tesla-deadline-command.json';
const ALLOWED_ORIGIN = 'https://onskasteeltje.github.io';

function cors(origin) {
  return {
    'Access-Control-Allow-Origin': origin === ALLOWED_ORIGIN ? ALLOWED_ORIGIN : 'null',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Tesla-Control-Pin',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin'
  };
}

function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...cors(origin) }
  });
}

function validDeadline(v) {
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(String(v || ''));
}

function toBase64(text) {
  return btoa(unescape(encodeURIComponent(text)));
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';
    if (request.method === 'OPTIONS') {
      if (origin !== ALLOWED_ORIGIN) return json({ ok: false, error: 'origin_not_allowed' }, 403, origin);
      return new Response(null, { status: 204, headers: cors(origin) });
    }
    if (request.method !== 'POST') return json({ ok: false, error: 'method_not_allowed' }, 405, origin);
    if (origin !== ALLOWED_ORIGIN) return json({ ok: false, error: 'origin_not_allowed' }, 403, origin);

    const pin = request.headers.get('X-Tesla-Control-Pin') || '';
    if (!env.WRITE_PIN || pin !== env.WRITE_PIN) return json({ ok: false, error: 'unauthorized' }, 401, origin);
    if (!env.GITHUB_TOKEN) return json({ ok: false, error: 'worker_not_configured' }, 500, origin);

    let input;
    try { input = await request.json(); }
    catch { return json({ ok: false, error: 'invalid_json' }, 400, origin); }

    const active = input.active === true;
    let deadline = '';
    let goalKWh = 0;
    let maxA = 11;

    if (active) {
      deadline = String(input.deadline || '').trim();
      goalKWh = Number(input.goalKWh);
      maxA = Math.round(Number(input.maxA));
      if (!validDeadline(deadline)) return json({ ok: false, error: 'invalid_deadline' }, 400, origin);
      if (!Number.isFinite(goalKWh) || goalKWh < 1 || goalKWh > 75) return json({ ok: false, error: 'invalid_goal_kwh' }, 400, origin);
      if (!Number.isFinite(maxA) || maxA < 6 || maxA > 16) return json({ ok: false, error: 'invalid_max_a' }, 400, origin);
    }

    const command = {
      schema: 1,
      requestId: crypto.randomUUID(),
      requestedAt: new Date().toISOString(),
      source: 'website',
      active,
      deadline,
      goalKWh,
      maxA
    };

    const apiUrl = `https://api.github.com/repos/${OWNER}/${REPO}/contents/${PATH}`;
    const ghHeaders = {
      'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'homey-energy-manual-tesla-worker'
    };

    let sha;
    const current = await fetch(`${apiUrl}?ref=${encodeURIComponent(BRANCH)}`, { headers: ghHeaders });
    if (current.ok) {
      const meta = await current.json();
      sha = meta.sha;
    } else if (current.status !== 404) {
      return json({ ok: false, error: 'github_read_failed', status: current.status }, 502, origin);
    }

    const payload = {
      message: active ? `Set Tesla deadline ${deadline}` : 'Disable Tesla deadline',
      content: toBase64(JSON.stringify(command, null, 2) + '\n'),
      branch: BRANCH
    };
    if (sha) payload.sha = sha;

    const written = await fetch(apiUrl, {
      method: 'PUT',
      headers: { ...ghHeaders, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!written.ok) {
      const detail = await written.text();
      return json({ ok: false, error: 'github_write_failed', status: written.status, detail: detail.slice(0, 300) }, 502, origin);
    }

    return json({ ok: true, command }, 200, origin);
  }
};
