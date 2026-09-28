// API key is set via the UI modal (App.jsx → API Key Settings).
// Defaults to demo admin key for immediate evaluation
const DEFAULT_API_KEY = 'trapline_admin_secret_key';

const PROD_BACKEND_URL = 'https://trapline-backend.onrender.com';
const LOCAL_BACKEND_URL = 'http://127.0.0.1:8000';

const isLocalhost = typeof window !== 'undefined' && 
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  (isLocalhost ? LOCAL_BACKEND_URL : PROD_BACKEND_URL)
).replace(/\/$/, '');

export function getApiKey() {
  return localStorage.getItem('trapline_api_key') || DEFAULT_API_KEY;
}

export function setApiKey(key) {
  if (key) {
    localStorage.setItem('trapline_api_key', key);
  } else {
    localStorage.removeItem('trapline_api_key');
  }
}

async function request(endpoint, options = {}) {
  const apiKey = getApiKey();
  const headers = {
    'Content-Type': 'application/json',
    'x-api-key': apiKey,
    ...(options.headers || {}),
  };

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = 'API request failed';
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || JSON.stringify(errorJson);
    } catch {
      errorDetail = await response.text();
    }
    const err = new Error(errorDetail);
    err.status = response.status;
    throw err;
  }

  return response.json();
}

export const api = {
  // Conversations
  listConversations: () => request('/conversations'),
  getConversation: (id) => request(`/conversations/${id}`),
  explainRisk: (id) => request(`/conversations/${id}/explain`, { method: 'POST' }),

  // Review Queue
  getReviewQueue: () => request('/review-queue'),
  approveMessage: (messageId) => request(`/review-queue/${messageId}/approve`, { method: 'POST' }),
  editMessage: (messageId, text) => request(`/review-queue/${messageId}/edit`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  }),
  haltMessage: (messageId) => request(`/review-queue/${messageId}/halt`, { method: 'POST' }),

  // Simulation
  startSimulatedConversation: () => request('/simulate/start-conversation', { method: 'POST' }),
  nextSimulatedTurn: (conversationId) => request(`/simulate/${conversationId}/next-turn`, { method: 'POST' }),

  // Indicators (Institution Dashboard)
  listIndicators: (params = {}) => {
    const query = new URLSearchParams();
    if (params.type) query.set('type', params.type);
    if (params.status) query.set('status', params.status);
    if (params.min_risk !== undefined && params.min_risk !== '' && params.min_risk !== null) {
      query.set('min_risk', params.min_risk);
    }
    if (params.correlated_only) query.set('correlated_only', 'true');
    if (params.sort_by) query.set('sort_by', params.sort_by);
    const qs = query.toString();
    return request(`/indicators${qs ? `?${qs}` : ''}`);
  },
  blockIndicator: (indicatorId) => request(`/indicators/${indicatorId}/block`, { method: 'POST' }),
  unblockIndicator: (indicatorId) => request(`/indicators/${indicatorId}/unblock`, { method: 'POST' }),
  resetAllIndicators: () => request('/indicators/reset-all', { method: 'POST' }),
};

