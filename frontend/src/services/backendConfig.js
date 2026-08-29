const envHttpBaseUrl = import.meta.env.VITE_BACKEND_HTTP_URL;
const envWsUrl = import.meta.env.VITE_BACKEND_WS_URL;

const DEFAULT_LOCAL_HTTP_URL = 'http://127.0.0.1:8000';
const DEFAULT_LOCAL_WS_URL = 'ws://127.0.0.1:8000/ws';
const DEFAULT_PROD_HTTP_URL = 'https://sfcollab-sentiment-backend.onrender.com';
const DEFAULT_PROD_WS_URL = 'wss://sfcollab-sentiment-backend.onrender.com/ws';

function normalizeHttpBaseUrl(value) {
  if (!value) return null;
  return value.endsWith('/') ? value.slice(0, -1) : value;
}

function buildWebSocketUrl(httpBaseUrl) {
  try {
    const url = new URL(httpBaseUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '/ws';
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch {
    return null;
  }
}

const httpBaseUrl =
  normalizeHttpBaseUrl(envHttpBaseUrl) ||
  (import.meta.env.PROD ? DEFAULT_PROD_HTTP_URL : DEFAULT_LOCAL_HTTP_URL);
const wsUrl =
  envWsUrl ||
  buildWebSocketUrl(httpBaseUrl) ||
  (import.meta.env.PROD ? DEFAULT_PROD_WS_URL : DEFAULT_LOCAL_WS_URL);

export const backendConfig = {
  httpBaseUrl,
  wsUrl,
};
