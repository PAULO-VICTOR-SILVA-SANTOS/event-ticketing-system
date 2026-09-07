(function () {
  const claims = Auth.requireAuth();
  if (!claims) return;

  renderSidebar("participants");

  const PAGE_SIZE = 10;
  let allParticipants = [];
  let currentFilter = "all";
  let currentSearch = "";
  let currentPage = 1;

  const tbody = document.getElementById("participants-tbody");
  const subtitle = document.getElementById("participants-subtitle");
  const pagination = document.getElementById("pagination");

  async function load() {
    try {
      allParticipants = await Api.listParticipants();
      currentPage = 1;
      render();
    } catch (err) {
      showToast(errorMessage(err), "error");
      tbody.innerHTML = `<tr class="loading-row"><td colspan="6">Nao foi possivel carregar os participantes.</td></tr>`;
    }
  }

  function computeDuplicateIds(participants) {
    const byEmail = new Map();
    const byWhatsapp = new Map();
    participants.forEach((p) => {
      if (p.email) byEmail.set(p.email, (byEmail.get(p.email) || []).concat(p.id));
      if (p.whatsapp) byWhatsapp.set(p.whatsapp, (byWhatsapp.get(p.whatsapp) || []).concat(p.id));
    });

    const duplicateIds = new Set();
    [byEmail, byWhatsapp].forEach((map) => {
      map.forEach((ids) => {
        if (ids.length > 1) ids.forEach((id) => duplicateIds.add(id));
      });
    });
    return duplicateIds;
  }

  function getFiltered() {
    return allParticipants.filter((p) => {
      if (currentFilter === "paid" && p.payment_status !== "paid") return false;
      if (currentFilter === "pending" && p.payment_status !== "pending") return false;
      if (currentSearch) {
        const haystack = `${p.name} ${p.email}`.toLowerCase();
        if (!haystack.includes(currentSearch.toLowerCase())) return false;
      }
      return true;
    });
  }

  function statusBadge(status) {
    if (status === "paid") return `<span class="badge badge-success"><i class="ti ti-circle-check"></i> Paga</span>`;
    if (status === "pending") return `<span class="badge badge-warning"><i class="ti ti-clock"></i> Pendente</span>`;
    return `<span class="badge badge-muted"><i class="ti ti-ban"></i> Expirada</span>`;
  }

  const CHECKIN_REASON_MESSAGES = {
    already_checked_in: "Ingresso ja utilizado.",
    payment_pending: "Pagamento pendente.",
    invalid_ticket: "Ingresso invalido.",
  };

  function checkinCell(p) {
    if (p.checkin_done) {
      return `
        <span class="badge badge-info"><i class="ti ti-circle-check"></i> Entrou</span>
        <div class="cell-sub">${formatDateTime(p.checkin_at)}</div>`;
    }

    // Manual check-in matches by ticket_code, which is only generated once a
    // participant is marked paid through the real payment flow (webhook) --
    // an admin manually flipping status to "paid" doesn't create one, so the
    // button must stay hidden rather than call checkin with a null/blank
    // code (which could match the wrong participant on the backend).
    const canCheckin = p.payment_status === "paid" && p.ticket_code;

    return `
      <div style="display:flex; align-items:center; gap:8px;">
        <span class="badge badge-muted"><i class="ti ti-minus"></i> Nao entrou</span>
        ${
          canCheckin
            ? `<button class="btn btn-sm btn-outline" data-checkin="${escapeHtml(p.ticket_code)}" data-checkin-id="${p.id}">
                <i class="ti ti-check"></i> Check-in
              </button>`
            : ""
        }
      </div>`;
  }

  function methodLabel(method) {
    return method === "pix" ? '<i class="ti ti-qrcode"></i> Pix' : '<i class="ti ti-credit-card"></i> Cartao';
  }

  function render() {
    const filtered = getFiltered();
    const duplicateIds = computeDuplicateIds(allParticipants);
    subtitle.textContent = `${filtered.length} de ${allParticipants.length} participante(s)`;

    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    if (currentPage > totalPages) currentPage = totalPages;
    const start = (currentPage - 1) * PAGE_SIZE;
    const pageItems = filtered.slice(start, start + PAGE_SIZE);

    if (pageItems.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><i class="ti ti-users"></i>Nenhum participante encontrado.</div></td></tr>`;
    } else {
      tbody.innerHTML = pageItems
        .map((p) => {
          const nextStatus = p.payment_status === "paid" ? "pending" : "paid";
          const actionLabel = p.payment_status === "paid" ? "Desfazer" : "Confirmar";
          const actionIcon = p.payment_status === "paid" ? "ti-rotate-2" : "ti-check";
          return `
          <tr>
            <td>
              <div class="cell-name">
                ${escapeHtml(p.name)}
                ${duplicateIds.has(p.id) ? `<span class="badge badge-warning" style="margin-left:8px;" title="Outro participante com mesmo e-mail ou WhatsApp"><i class="ti ti-alert-triangle"></i> Duplicado</span>` : ""}
              </div>
              ${p.nickname ? `<div class="cell-sub">${escapeHtml(p.nickname)}</div>` : ""}
            </td>
            <td>
              <div>${escapeHtml(p.email)}</div>
              <div class="cell-sub">${escapeHtml(p.whatsapp)}</div>
            </td>
            <td>${methodLabel(p.payment_method)}</td>
            <td>${statusBadge(p.payment_status)}</td>
            <td>${checkinCell(p)}</td>
            <td>
              <div style="display:flex; gap:8px;">
                <button class="btn btn-sm btn-outline" data-toggle-payment="${p.id}" data-next-status="${nextStatus}">
                  <i class="ti ${actionIcon}"></i> ${actionLabel}
                </button>
                <button class="btn btn-sm btn-danger" data-remove="${p.id}" title="Remover participante">
                  <i class="ti ti-trash"></i>
                </button>
              </div>
            </td>
          </tr>`;
        })
        .join("");
    }

    renderPagination(totalPages);
  }

  function renderPagination(totalPages) {
    if (totalPages <= 1) {
      pagination.innerHTML = "";
      return;
    }
    let buttons = "";
    for (let i = 1; i <= totalPages; i++) {
      buttons += `<button class="page-btn ${i === currentPage ? "active" : ""}" data-page="${i}">${i}</button>`;
    }
    pagination.innerHTML = `
      <span>Pagina ${currentPage} de ${totalPages}</span>
      <div class="pages">${buttons}</div>`;

    pagination.querySelectorAll("[data-page]").forEach((btn) => {
      btn.addEventListener("click", () => {
        currentPage = parseInt(btn.dataset.page, 10);
        render();
      });
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  tbody.addEventListener("click", async (event) => {
    const toggleBtn = event.target.closest("[data-toggle-payment]");
    const removeBtn = event.target.closest("[data-remove]");
    const checkinBtn = event.target.closest("[data-checkin]");

    if (toggleBtn) {
      const id = toggleBtn.dataset.togglePayment;
      const nextStatus = toggleBtn.dataset.nextStatus;
      toggleBtn.disabled = true;

      try {
        const updated = await Api.setPaymentStatus(id, nextStatus);
        const index = allParticipants.findIndex((p) => String(p.id) === String(id));
        if (index !== -1) allParticipants[index] = updated;
        showToast(
          nextStatus === "paid" ? "Pagamento confirmado." : "Pagamento revertido para pendente.",
          "success"
        );
        render();
      } catch (err) {
        showToast(errorMessage(err), "error");
        toggleBtn.disabled = false;
      }
      return;
    }

    if (removeBtn) {
      const id = removeBtn.dataset.remove;
      const confirmed = await confirmAction("Tem certeza que deseja remover este participante?");
      if (!confirmed) return;

      removeBtn.disabled = true;
      try {
        await Api.deleteParticipant(id);
        allParticipants = allParticipants.filter((p) => String(p.id) !== String(id));
        showToast("Participante removido.", "success");
        render();
      } catch (err) {
        showToast(errorMessage(err), "error");
        removeBtn.disabled = false;
      }
      return;
    }

    if (checkinBtn) {
      const ticketCode = checkinBtn.dataset.checkin;
      const id = checkinBtn.dataset.checkinId;
      checkinBtn.disabled = true;

      try {
        const result = await Api.checkinByTicket(ticketCode);
        const index = allParticipants.findIndex((p) => String(p.id) === String(id));
        if (index !== -1) {
          allParticipants[index] = {
            ...allParticipants[index],
            checkin_done: true,
            checkin_at: result.checkin_at,
          };
        }
        showToast("Check-in confirmado.", "success");
        render();
      } catch (err) {
        const reason = err.data && err.data.reason;
        showToast(CHECKIN_REASON_MESSAGES[reason] || errorMessage(err), "error");
        checkinBtn.disabled = false;
      }
    }
  });

  document.getElementById("search-input").addEventListener("input", (event) => {
    currentSearch = event.target.value;
    currentPage = 1;
    render();
  });

  document.querySelectorAll(".filter-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      currentFilter = pill.dataset.filter;
      currentPage = 1;
      render();
    });
  });

  document.getElementById("export-btn").addEventListener("click", () => {
    const filtered = getFiltered();
    if (filtered.length === 0) {
      showToast("Nao ha participantes para exportar.", "info");
      return;
    }
    const header = ["Nome", "Apelido", "CPF", "Email", "WhatsApp", "Pagamento", "Status", "Check-in", "Cadastro"];
    const rows = filtered.map((p) => [
      p.name,
      p.nickname || "",
      p.cpf || "",
      p.email,
      p.whatsapp,
      p.payment_method,
      p.payment_status,
      p.checkin_done ? "sim" : "nao",
      p.created_at,
    ]);
    const csv = [header, ...rows]
      .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
      .join("\n");

    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "participantes.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });

  const addForm = document.getElementById("add-form");
  const addSubmitBtn = document.getElementById("add-submit-btn");

  document.getElementById("add-btn").addEventListener("click", () => openModal("add-modal"));
  document.getElementById("add-modal-close").addEventListener("click", () => closeModal("add-modal"));
  document.getElementById("add-cancel-btn").addEventListener("click", () => closeModal("add-modal"));

  addForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    addSubmitBtn.disabled = true;
    addSubmitBtn.innerHTML = '<i class="ti ti-loader-2"></i> Adicionando...';

    const payload = {
      name: document.getElementById("p-name").value.trim(),
      nickname: document.getElementById("p-nickname").value.trim() || null,
      cpf: document.getElementById("p-cpf").value.trim() || null,
      email: document.getElementById("p-email").value.trim(),
      whatsapp: document.getElementById("p-whatsapp").value.trim(),
      payment_method: document.getElementById("p-method").value,
    };

    try {
      await Api.createParticipant(claims.event_id, payload);
      showToast("Participante adicionado.", "success");
      closeModal("add-modal");
      addForm.reset();
      await load();
    } catch (err) {
      showToast(errorMessage(err), "error");
    } finally {
      addSubmitBtn.disabled = false;
      addSubmitBtn.innerHTML = '<i class="ti ti-check"></i> Adicionar';
    }
  });

  load();
})();
