(function () {
  const claims = Auth.requireAuth();
  if (!claims) return;

  renderSidebar("expenses");

  const CATEGORY_LABELS = {
    banda: "Banda",
    comida: "Comida",
    lembranca: "Lembranca",
    local: "Local",
    outros: "Outros",
  };

  let expenses = [];
  const listEl = document.getElementById("expenses-list");
  const subtitle = document.getElementById("expenses-subtitle");

  // Mercado Pago fee rates. The data model only tracks payment_method as
  // "pix" or "card" (no debit/credit distinction), so every card payment is
  // treated as credit 1x -- the debit rate has no way to be applied.
  const MP_FEE_RATES = { pix: 0.0099, card: 0.0498 };

  function calculateMpFees(participants, ticketPrice) {
    const paid = participants.filter((p) => p.payment_status === "paid");

    let grossPix = 0;
    let grossCard = 0;
    paid.forEach((p) => {
      if (p.payment_method === "pix") grossPix += ticketPrice;
      else if (p.payment_method === "card") grossCard += ticketPrice;
    });

    const feePix = grossPix * MP_FEE_RATES.pix;
    const feeCard = grossCard * MP_FEE_RATES.card;
    const gross = grossPix + grossCard;
    const totalFees = feePix + feeCard;
    // Only the Pix fee is absorbed by the organizadora -- the card fee is
    // passed on to whoever pays by card, so it's excluded from the "real"
    // net figure (and from the expense totals below).
    const net = gross - feePix;

    return { paidCount: paid.length, gross, feePix, feeCard, totalFees, net };
  }

  function renderMpFees(fees) {
    document.getElementById("mp-gross").textContent = formatCurrency(fees.gross);
    document.getElementById("mp-fees-total").textContent = formatCurrency(fees.totalFees);
    document.getElementById("mp-net").textContent = formatCurrency(fees.net);

    document.getElementById("mp-fees-breakdown").innerHTML = `
      <div class="expense-row">
        <div class="expense-info">
          <div>
            <div class="cell-name">Taxas Mercado Pago - Pix</div>
            <div class="cell-sub">Absorvida pela organizadora</div>
          </div>
        </div>
        <span class="expense-value">${formatCurrency(fees.feePix)}</span>
      </div>
      <div class="expense-row">
        <div class="expense-info">
          <div>
            <div class="cell-name">Taxas Mercado Pago - Cartao</div>
            <div class="cell-sub">Cobrada dos participantes</div>
          </div>
        </div>
        <span class="expense-value">${formatCurrency(fees.feeCard)}</span>
      </div>`;
  }

  async function load() {
    try {
      const [expensesData, dashboard, participants] = await Promise.all([
        Api.listExpenses(),
        Api.getDashboard(),
        Api.listParticipants(),
      ]);
      expenses = expensesData;
      subtitle.textContent = `${expenses.length} despesa(s) cadastrada(s)`;

      // dashboard.value_per_person is the raw event ticket_price (see
      // backend/app/routes/dashboard.py) -- reused here instead of an extra
      // event fetch.
      const ticketPrice = parseFloat(dashboard.value_per_person) || 0;
      const fees = calculateMpFees(participants, ticketPrice);
      renderMpFees(fees);

      const totalExpensesWithFees = parseFloat(dashboard.total_expenses) + fees.feePix;
      const remainingWithFees = Math.max(totalExpensesWithFees - parseFloat(dashboard.total_collected), 0);
      const netPerPerson = fees.paidCount > 0 ? fees.net / fees.paidCount : ticketPrice;

      document.getElementById("total-expenses").textContent = formatCurrency(totalExpensesWithFees);
      document.getElementById("total-collected").textContent = formatCurrency(dashboard.total_collected);
      document.getElementById("total-remaining").textContent = formatCurrency(remainingWithFees);
      document.getElementById("total-per-person").textContent = formatCurrency(netPerPerson);

      render();
    } catch (err) {
      showToast(errorMessage(err), "error");
      listEl.innerHTML = `<div class="empty-state"><i class="ti ti-alert-triangle"></i>Nao foi possivel carregar as despesas.</div>`;
    }
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
  }

  function render() {
    if (expenses.length === 0) {
      listEl.innerHTML = `<div class="empty-state"><i class="ti ti-receipt-off"></i>Nenhuma despesa cadastrada ainda.</div>`;
      return;
    }

    listEl.innerHTML = expenses
      .map(
        (e) => `
        <div class="expense-row">
          <div class="expense-info">
            <span class="category-dot cat-${e.category}"></span>
            <div>
              <div class="cell-name">${escapeHtml(e.name)}</div>
              <div class="cell-sub">${CATEGORY_LABELS[e.category] || e.category}</div>
            </div>
          </div>
          <div style="display:flex; align-items:center;">
            <span class="expense-value">${formatCurrency(e.value)}</span>
            <button class="btn btn-sm btn-outline" data-edit="${e.id}" style="margin-right:8px;">
              <i class="ti ti-pencil"></i>
            </button>
            <button class="btn btn-sm btn-danger" data-delete="${e.id}">
              <i class="ti ti-trash"></i>
            </button>
          </div>
        </div>`
      )
      .join("");
  }

  const modalTitle = document.getElementById("expense-modal-title");
  const form = document.getElementById("expense-form");
  const idField = document.getElementById("expense-id");
  const nameField = document.getElementById("expense-name");
  const categoryField = document.getElementById("expense-category");
  const valueField = document.getElementById("expense-value");
  const submitBtn = document.getElementById("expense-submit-btn");

  function openAddModal() {
    modalTitle.textContent = "Nova despesa";
    form.reset();
    idField.value = "";
    openModal("expense-modal");
  }

  function openEditModal(expense) {
    modalTitle.textContent = "Editar despesa";
    idField.value = expense.id;
    nameField.value = expense.name;
    categoryField.value = expense.category;
    valueField.value = expense.value;
    openModal("expense-modal");
  }

  document.getElementById("add-expense-btn").addEventListener("click", openAddModal);
  document.getElementById("expense-modal-close").addEventListener("click", () => closeModal("expense-modal"));
  document.getElementById("expense-cancel-btn").addEventListener("click", () => closeModal("expense-modal"));

  listEl.addEventListener("click", async (event) => {
    const editBtn = event.target.closest("[data-edit]");
    const deleteBtn = event.target.closest("[data-delete]");

    if (editBtn) {
      const expense = expenses.find((e) => String(e.id) === editBtn.dataset.edit);
      if (expense) openEditModal(expense);
      return;
    }

    if (deleteBtn) {
      const id = deleteBtn.dataset.delete;
      const confirmed = await confirmAction("Remover esta despesa? Essa acao nao pode ser desfeita.");
      if (!confirmed) return;
      deleteBtn.disabled = true;
      try {
        await Api.deleteExpense(id);
        showToast("Despesa removida.", "success");
        await load();
      } catch (err) {
        showToast(errorMessage(err), "error");
        deleteBtn.disabled = false;
      }
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="ti ti-loader-2"></i> Salvando...';

    const payload = {
      name: nameField.value.trim(),
      category: categoryField.value,
      value: valueField.value,
    };

    try {
      if (idField.value) {
        await Api.updateExpense(idField.value, payload);
        showToast("Despesa atualizada.", "success");
      } else {
        await Api.createExpense(payload);
        showToast("Despesa adicionada.", "success");
      }
      closeModal("expense-modal");
      await load();
    } catch (err) {
      showToast(errorMessage(err), "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="ti ti-check"></i> Salvar';
    }
  });

  load();
})();
