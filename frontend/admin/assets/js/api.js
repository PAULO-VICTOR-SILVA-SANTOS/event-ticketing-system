const API_BASE_URL = "https://web-production-e71e8.up.railway.app/api/v1";
const TOKEN_KEY = "admin_token";

const Auth = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
  },

  clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  },

  decode(token) {
    try {
      const payload = token.split(".")[1];
      const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
      return JSON.parse(json);
    } catch (err) {
      return null;
    }
  },

  getClaims() {
    const token = this.getToken();
    return token ? this.decode(token) : null;
  },

  getEventId() {
    const claims = this.getClaims();
    return claims ? claims.event_id : null;
  },

  isExpired(claims) {
    if (!claims || !claims.exp) return true;
    return Date.now() >= claims.exp * 1000;
  },

  requireAuth() {
    const token = this.getToken();
    const claims = token ? this.decode(token) : null;
    if (!token || !claims || this.isExpired(claims)) {
      this.clearToken();
      window.location.href = "login.html";
      return null;
    }
    return claims;
  },

  logout() {
    this.clearToken();
    window.location.href = "login.html";
  },
};

async function apiRequest(path, { method = "GET", body, headers = {}, auth = true } = {}) {
  const finalHeaders = { "Content-Type": "application/json", ...headers };

  if (auth) {
    const token = Auth.getToken();
    if (token) {
      finalHeaders["Authorization"] = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401 && auth) {
    Auth.logout();
    throw new Error("Sessao expirada. Faca login novamente.");
  }

  let data = null;
  if (response.status !== 204) {
    try {
      data = await response.json();
    } catch (err) {
      data = null;
    }
  }

  if (!response.ok) {
    let message = "Erro na requisicao";
    if (data) {
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]) {
        message = data.detail[0].msg || message;
      } else if (data.reason) message = data.reason;
    }
    const error = new Error(message);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

const Api = {
  login(username, password) {
    return apiRequest("/auth/login", {
      method: "POST",
      body: { username, password },
      auth: false,
    });
  },

  getDashboard() {
    return apiRequest("/dashboard/");
  },

  getEvent(eventId) {
    return apiRequest(`/events/${eventId}`, { auth: false });
  },

  updateEvent(eventId, payload) {
    return apiRequest(`/events/${eventId}`, { method: "PUT", body: payload });
  },

  getConfigStatus() {
    return apiRequest("/config/status");
  },

  listParticipants() {
    return apiRequest("/participants/");
  },

  createParticipant(eventId, payload) {
    return apiRequest(`/participants/?event_id=${eventId}`, {
      method: "POST",
      body: payload,
      auth: false,
    });
  },

  setPaymentStatus(participantId, status) {
    return apiRequest(`/participants/${participantId}/payment?status=${status}`, {
      method: "PATCH",
    });
  },

  deleteParticipant(participantId) {
    return apiRequest(`/participants/${participantId}`, { method: "DELETE" });
  },

  checkinByTicket(ticketCode) {
    return apiRequest("/participants/checkin", {
      method: "PATCH",
      body: { ticket_code: ticketCode },
    });
  },

  listExpenses() {
    return apiRequest("/expenses/");
  },

  createExpense(payload) {
    return apiRequest("/expenses/", { method: "POST", body: payload });
  },

  updateExpense(expenseId, payload) {
    return apiRequest(`/expenses/${expenseId}`, { method: "PUT", body: payload });
  },

  deleteExpense(expenseId) {
    return apiRequest(`/expenses/${expenseId}`, { method: "DELETE" });
  },
};
