const NAV_ITEMS = [
  { page: "dashboard", href: "dashboard.html", icon: "ti-layout-dashboard", label: "Dashboard" },
  { page: "participants", href: "participants.html", icon: "ti-users", label: "Participantes" },
  { page: "expenses", href: "expenses.html", icon: "ti-receipt-2", label: "Despesas" },
  { page: "settings", href: "settings.html", icon: "ti-settings", label: "Configuracoes" },
];

function renderSidebar(activePage) {
  const root = document.getElementById("sidebar-root");
  if (!root) return;

  const links = NAV_ITEMS.map(
    (item) => `
      <a class="nav-link ${item.page === activePage ? "active" : ""}" href="${item.href}">
        <i class="ti ${item.icon}"></i> ${item.label}
      </a>`
  ).join("");

  root.innerHTML = `
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-info">
          <div class="logo-mark-wrap">
            <svg class="logo-ring" viewBox="0 0 100 100"><circle cx="50" cy="50" r="48" stroke="url(#pvRingA)" stroke-width="1.4" stroke-dasharray="6 7"/><circle class="orbit-dot" cx="50" cy="2" r="3" fill="#a855f7"/><defs><linearGradient id="pvRingA" x1="0" y1="0" x2="100" y2="100"><stop offset="0%" stop-color="#0055ff" stop-opacity=".55"/><stop offset="100%" stop-color="#7b2fff" stop-opacity=".55"/></linearGradient></defs></svg>
            <svg class="logo-ring-2" viewBox="0 0 100 100"><circle cx="50" cy="50" r="48" stroke="url(#pvRingB)" stroke-width="1.2" stroke-dasharray="3 8"/><defs><linearGradient id="pvRingB" x1="0" y1="0" x2="100" y2="100"><stop offset="0%" stop-color="#7b2fff" stop-opacity=".45"/><stop offset="100%" stop-color="#0055ff" stop-opacity=".45"/></linearGradient></defs></svg>
            <div class="logo-mark"><span>PV</span></div>
          </div>
          <div class="logo-text">
            PV Technology
            <small>PAINEL DO EVENTO</small>
          </div>
        </div>
        <button class="theme-toggle-btn" id="theme-toggle-btn" data-theme-toggle type="button"></button>
      </div>
      <nav class="sidebar-nav">${links}</nav>
      <div class="sidebar-footer">
        <button class="logout-btn" id="logout-btn"><i class="ti ti-logout-2"></i> Sair</button>
      </div>
    </aside>`;

  document.getElementById("logout-btn").addEventListener("click", () => Auth.logout());
  Theme.init();
}

function showToast(message, type = "info") {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }

  const icons = { success: "ti-circle-check", error: "ti-alert-circle", info: "ti-info-circle" };
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<i class="ti ${icons[type] || icons.info}"></i><span>${message}</span>`;
  stack.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.2s ease";
    setTimeout(() => toast.remove(), 200);
  }, 3600);
}

function openModal(id) {
  document.getElementById(id).hidden = false;
}

function closeModal(id) {
  document.getElementById(id).hidden = true;
}

function confirmAction(message) {
  return new Promise((resolve) => {
    let overlay = document.getElementById("confirm-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "confirm-overlay";
      overlay.className = "modal-overlay";
      overlay.innerHTML = `
        <div class="modal-box" style="max-width: 380px;">
          <div class="modal-header">
            <h3><i class="ti ti-alert-triangle" style="color: var(--warning);"></i> Confirmar</h3>
          </div>
          <p id="confirm-message"></p>
          <div class="modal-actions">
            <button type="button" class="btn btn-ghost" id="confirm-cancel-btn">Cancelar</button>
            <button type="button" class="btn btn-danger" id="confirm-ok-btn">Confirmar</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
    }

    overlay.querySelector("#confirm-message").textContent = message;
    overlay.hidden = false;

    const cleanup = (result) => {
      overlay.hidden = true;
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      resolve(result);
    };
    const okBtn = overlay.querySelector("#confirm-ok-btn");
    const cancelBtn = overlay.querySelector("#confirm-cancel-btn");
    const onOk = () => cleanup(true);
    const onCancel = () => cleanup(false);
    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
  });
}

function formatCurrency(value) {
  const number = typeof value === "string" ? parseFloat(value) : value;
  return (number || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDateTime(isoString) {
  if (!isoString) return "-";
  const date = new Date(isoString);
  return date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function formatDate(isoString) {
  if (!isoString) return "-";
  const date = new Date(isoString + (isoString.length === 10 ? "T00:00:00" : ""));
  return date.toLocaleDateString("pt-BR");
}

function errorMessage(err) {
  return (err && err.message) || "Ocorreu um erro inesperado.";
}
