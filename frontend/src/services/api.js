// All calls go to our FastAPI backend. The Shopify token never reaches the browser.
const BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export const getToken = () => sessionStorage.getItem("crm_token") || "";
export const setToken = (t) =>
  t ? sessionStorage.setItem("crm_token", t) : sessionStorage.removeItem("crm_token");

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (getToken()) headers.Authorization = `Bearer ${getToken()}`;
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? "Please check the form values." : data.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return data;
}

const qs = (params) => {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v && q.set(k, v));
  const s = q.toString();
  return s ? `?${s}` : "";
};

export const api = {
  products: (params) => request(`/products${qs(params)}`),
  product: (id) => request(`/products/${id}`),
  customers: (params) => request(`/customers${qs(params)}`),
  orders: (params) => request(`/orders${qs(params)}`),
  crmDashboard: () => request("/crm/dashboard"),
  crmCustomers: () => request("/crm/customers"),
  crmCustomer: (id) => request(`/crm/customers/${id}`),
  interactions: (id) => request(`/crm/customers/${id}/interactions`),
  addInteraction: (id, body) =>
    request(`/crm/customers/${id}/interactions`, { method: "POST", body: JSON.stringify(body) }),
  followUps: (params = {}) => request(`/crm/follow-ups${qs(params)}`),
  addFollowUp: (body) => request("/crm/follow-ups", { method: "POST", body: JSON.stringify(body) }),
};
