const configuredApiBase = import.meta.env.VITE_API_URL?.trim();
const configuredWsBase = import.meta.env.VITE_WS_URL?.trim();

export function apiUrl(path) {
  if (!path.startsWith('/')) {
    throw new Error(`API path must start with '/': ${path}`);
  }

  if (!configuredApiBase) {
    return path;
  }

  return `${configuredApiBase}${path}`;
}

export function wsUrl(path) {
  if (!path.startsWith('/')) {
    throw new Error(`WebSocket path must start with '/': ${path}`);
  }

  if (configuredWsBase) {
    return `${configuredWsBase}${path}`;
  }

  if (configuredApiBase) {
    const base = new URL(configuredApiBase);
    const protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${base.host}${path}`;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
}
