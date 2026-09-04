(function () {
  const params = new URLSearchParams(window.location.search);
  const EVENT_ID = params.get("event_id") || "1";

  const el = (id) => document.getElementById(id);

  const currencyFmt = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  function formatDateBR(isoDate) {
    const [year, month, day] = isoDate.split("-");
    return `${day}/${month}/${year}`;
  }

  function formatTimeBR(isoTime) {
    return isoTime.slice(0, 5);
  }

  function showAlert(alertBoxId, textId, message) {
    el(alertBoxId).classList.remove("hidden");
    el(textId).textContent = message;
  }

  function hideAlert(alertBoxId) {
    el(alertBoxId).classList.add("hidden");
  }

  let currentEvent = null;

  function renderEvent(event) {
    currentEvent = event;

    const hero = el("event-hero");
    const bannerHtml = event.banner_url
      ? `<img class="event-hero__banner" src="${event.banner_url}" alt="${event.name}" />`
      : `<div class="event-hero__banner is-placeholder"><i class="ti ti-confetti"></i></div>`;

    const occupancyRatio =
      event.max_capacity > 0
        ? Math.min(event.registered_count / event.max_capacity, 1)
        : 0;
    const isCritical = event.remaining_slots <= Math.max(event.max_capacity * 0.1, 3);

    hero.innerHTML = `
      ${bannerHtml}
      <div class="event-hero__body">
        <h1 class="event-hero__title">${event.name}</h1>
        ${event.description ? `<p class="event-hero__description">${event.description}</p>` : ""}
        <div class="badge-row">
          <span class="badge"><i class="ti ti-calendar-event"></i> ${formatDateBR(event.date)}</span>
          <span class="badge"><i class="ti ti-clock"></i> ${formatTimeBR(event.time)}</span>
          <span class="badge"><i class="ti ti-map-pin"></i> ${event.location}</span>
        </div>
        <div class="price-row">
          <span class="price-row__label">Valor do ingresso</span>
          <span class="price-row__value">${currencyFmt.format(event.ticket_price)}</span>
        </div>
        <div class="slots">
          <div class="slots__label">
            <span>Vagas preenchidas</span>
            <strong>${event.remaining_slots} restante${event.remaining_slots === 1 ? "" : "s"}</strong>
          </div>
          <div class="slots__bar">
            <div class="slots__fill ${isCritical ? "is-critical" : ""}" style="width:${occupancyRatio * 100}%"></div>
          </div>
        </div>
      </div>
    `;

    if (event.remaining_slots <= 0) {
      el("sold-out").classList.remove("hidden");
      el("registration-card").classList.add("hidden");
    } else {
      el("registration-card").classList.remove("hidden");
    }
  }

  async function loadEvent() {
    try {
      const event = await Api.getEvent(EVENT_ID);
      renderEvent(event);
    } catch (err) {
      el("event-hero").classList.add("hidden");
      showAlert(
        "event-error",
        "event-error-text",
        err.status === 404
          ? "Evento nao encontrado."
          : "Nao foi possivel carregar este evento. Tente novamente mais tarde."
      );
    }
  }

  function setSubmitting(isSubmitting) {
    const btn = el("submit-btn");
    btn.disabled = isSubmitting;
    btn.innerHTML = isSubmitting
      ? `<span class="spinner"></span> Enviando...`
      : `<i class="ti ti-arrow-right"></i> Continuar`;
  }

  async function handleRegistration(event) {
    event.preventDefault();
    hideAlert("form-alert");

    const form = event.target;
    const paymentMethod = form.querySelector('input[name="payment_method"]:checked').value;

    const payload = {
      name: form.name.value.trim(),
      nickname: form.nickname.value.trim() || null,
      cpf: form.cpf.value.trim() || null,
      email: form.email.value.trim(),
      whatsapp: form.whatsapp.value.trim(),
      payment_method: paymentMethod,
    };

    setSubmitting(true);
    try {
      const participant = await Api.createParticipant(EVENT_ID, payload);
      form.classList.add("hidden");
      el("payment-card").classList.remove("hidden");

      if (paymentMethod === "pix") {
        await startPixPayment(participant);
      } else {
        await startCardPayment(participant);
      }
    } catch (err) {
      let message = "Nao foi possivel concluir sua inscricao. Verifique os dados e tente novamente.";
      if (err.status === 400 && err.data && err.data.detail) {
        message = err.data.detail;
      }
      showAlert("form-alert", "form-alert-text", message);
    } finally {
      setSubmitting(false);
    }
  }

  let pixPollTimer = null;

  async function startPixPayment(participant) {
    el("pix-panel").classList.remove("hidden");

    try {
      const payment = await Api.createPixPayment(participant.id, EVENT_ID);
      el("pix-qr-image").src = `data:image/png;base64,${payment.qr_code_base64}`;
      el("pix-copy-code").value = payment.qr_code || "";

      pollPixStatus(payment.payment_id);
    } catch (err) {
      setPixStatus("rejected", "Nao foi possivel gerar o Pix. Contate o organizador.");
    }
  }

  function setPixStatus(kind, text) {
    const pill = el("pix-status");
    pill.className = `status-pill ${kind}`;
    const icon =
      kind === "approved" ? "ti-circle-check" : kind === "rejected" ? "ti-circle-x" : null;
    pill.innerHTML = icon
      ? `<i class="ti ${icon}"></i> ${text}`
      : `<span class="spinner"></span> ${text}`;
  }

  function pollPixStatus(paymentId) {
    let attempts = 0;
    const maxAttempts = 120;

    pixPollTimer = setInterval(async () => {
      attempts += 1;
      try {
        const result = await Api.getPaymentStatus(paymentId);
        if (result.status === "approved") {
          setPixStatus("approved", "Pagamento confirmado! Verifique seu e-mail.");
          clearInterval(pixPollTimer);
        } else if (["rejected", "cancelled"].includes(result.status)) {
          setPixStatus("rejected", "Pagamento nao aprovado.");
          clearInterval(pixPollTimer);
        }
      } catch (err) {
        // keep polling silently; a transient error shouldn't stop the flow
      }

      if (attempts >= maxAttempts) {
        clearInterval(pixPollTimer);
      }
    }, 5000);
  }

  async function startCardPayment(participant) {
    el("card-panel").classList.remove("hidden");

    let publicKey;
    try {
      const config = await Api.getPublicConfig();
      publicKey = config.mp_public_key;
    } catch (err) {
      publicKey = null;
    }

    if (!publicKey || !window.MercadoPago) {
      showCardStatus("rejected", "Pagamento com cartao indisponivel no momento.");
      return;
    }

    const mp = new MercadoPago(publicKey, { locale: "pt-BR" });
    const bricksBuilder = mp.bricks();

    await bricksBuilder.create("cardPayment", "cardPaymentBrick_container", {
      initialization: {
        amount: Number(currentEvent.ticket_price),
      },
      callbacks: {
        onReady: () => {},
        onSubmit: (cardFormData) =>
          new Promise((resolve, reject) => {
            Api.createCardPayment(
              participant.id,
              EVENT_ID,
              cardFormData.token,
              cardFormData.installments
            )
              .then((result) => {
                if (result.status === "approved") {
                  showCardStatus("approved", "Pagamento aprovado! Verifique seu e-mail.");
                } else if (result.status === "in_process" || result.status === "pending") {
                  showCardStatus("pending", "Pagamento em analise.");
                } else {
                  showCardStatus("rejected", "Pagamento nao aprovado.");
                }
                resolve();
              })
              .catch((err) => {
                showCardStatus("rejected", "Nao foi possivel processar o pagamento.");
                reject(err);
              });
          }),
        onError: () => {
          showCardStatus("rejected", "Erro ao processar os dados do cartao.");
        },
      },
    });
  }

  function showCardStatus(kind, text) {
    const box = el("card-status");
    box.classList.remove("hidden");
    box.className = `status-pill ${kind}`;
    const icon = kind === "approved" ? "ti-circle-check" : kind === "pending" ? "ti-clock" : "ti-circle-x";
    box.innerHTML = `<i class="ti ${icon}"></i> ${text}`;
  }

  el("pix-copy-btn").addEventListener("click", () => {
    const input = el("pix-copy-code");
    input.select();
    navigator.clipboard?.writeText(input.value).catch(() => {});
  });

  el("registration-form").addEventListener("submit", handleRegistration);

  loadEvent();
})();
