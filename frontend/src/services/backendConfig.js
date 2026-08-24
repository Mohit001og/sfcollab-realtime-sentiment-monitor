const envHttpBaseUrl = import.meta.env.VITE_BACKEND_HTTP_URL;
const envWsUrl = import.meta.env.VITE_BACKEND_WS_URL;

export const backendConfig = {
  httpBaseUrl: envHttpBaseUrl || 'http://127.0.0.1:8000',
  wsUrl: envWsUrl || 'ws://127.0.0.1:8000/ws',
};
