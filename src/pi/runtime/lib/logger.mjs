export function log(level, event, fields = {}) {
  const record = {
    ts: new Date().toISOString(),
    level,
    event,
    ...fields,
  };
  process.stdout.write(`${JSON.stringify(record)}\n`);
}

export const logger = {
  info: (event, fields) => log('INFO', event, fields),
  warn: (event, fields) => log('WARN', event, fields),
  error: (event, fields) => log('ERROR', event, fields),
};
