const API_BASE_URL = window.location.hostname.endsWith(".github.io")
  ? "https://your-backend-domain.example/api/v1"
  : "http://127.0.0.1:8000/api/v1";

async function apiRequest(path, { method = "GET", body, headers = {} } = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }

  if (!response.ok) {
    const error = new Error(
      (data && (data.detail || data.reason)) || "Erro na requisicao"
    );
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

const Api = {
  getEvent(eventId) {
    return apiRequest(`/events/${eventId}`);
  },

  getPublicConfig() {
    return apiRequest("/config/public");
  },

  createParticipant(eventId, payload) {
    return apiRequest(`/participants/?event_id=${eventId}`, {
      method: "POST",
      body: payload,
    });
  },

  createPixPayment(participantId, eventId) {
    return apiRequest("/payments/pix", {
      method: "POST",
      body: { participant_id: participantId, event_id: eventId },
    });
  },

  createCardPayment(participantId, eventId, token, installments) {
    return apiRequest("/payments/card", {
      method: "POST",
      body: {
        participant_id: participantId,
        event_id: eventId,
        token,
        installments,
      },
    });
  },

  getPaymentStatus(paymentId) {
    return apiRequest(`/payments/status/${paymentId}`);
  },

  checkin(ticketCode, portariaKey) {
    return apiRequest("/checkin", {
      method: "POST",
      body: { ticket_code: ticketCode },
      headers: { "X-Portaria-Key": portariaKey },
    });
  },

  getCheckinStats(portariaKey) {
    return apiRequest("/checkin/stats", {
      headers: { "X-Portaria-Key": portariaKey },
    });
  },
};
