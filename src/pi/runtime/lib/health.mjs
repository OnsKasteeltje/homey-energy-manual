import http from 'node:http';

export function startHealthServer({ host = '127.0.0.1', port = 8787, getState }) {
  const server = http.createServer((req, res) => {
    if (req.method !== 'GET' || (req.url !== '/health' && req.url !== '/state')) {
      res.writeHead(404, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ status: 'NOT_FOUND' }));
      return;
    }

    const state = getState();
    const healthy = state?.runtimeStatus === 'OK';
    res.writeHead(healthy ? 200 : 503, { 'content-type': 'application/json' });
    res.end(JSON.stringify(state, null, 2));
  });

  server.listen(port, host);
  return server;
}
