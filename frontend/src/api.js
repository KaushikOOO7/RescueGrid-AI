export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const hasBody = options.body !== undefined && options.body !== null;
  if (hasBody && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(path, { ...options, headers });
  const contentType = response.headers.get('content-type') || '';
  let payload = null;
  if (contentType.includes('application/json')) {
    try { payload = await response.json(); } catch { payload = null; }
  } else {
    payload = await response.text().catch(() => '');
  }
  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || item.message || 'Invalid input').join('; ')
      : (detail || payload?.message || `Request failed (${response.status})`);
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  return payload;
}

export const getIncidents = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
  });
  const queryString = query.toString();
  return api(`/api/incidents${queryString ? `?${queryString}` : ''}`);
};

export const getResources = () => api('/api/resources');

export const createResource = (payload) => api('/api/resources', {
  method: 'POST',
  body: JSON.stringify(payload),
});

export const updateResource = (id, payload) => api(`/api/resources/${id}`, {
  method: 'PATCH',
  body: JSON.stringify(payload),
});

export const allocateResource = (payload) => api('/api/resources/allocate', {
  method: 'POST',
  body: JSON.stringify(payload),
});

export const releaseAllocation = (allocationId, coordinator = 'Coordinator') =>
  api(`/api/resources/allocate/${allocationId}?coordinator=${encodeURIComponent(coordinator)}`, {
    method: 'DELETE',
  });

export const resetDemoData = () => api('/api/demo/reset', { method: 'POST' });
