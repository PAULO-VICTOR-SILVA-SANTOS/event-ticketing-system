(function () {
  const claims = Auth.requireAuth();
  if (!claims) return;

  renderSidebar("settings");

  const form = document.getElementById("settings-form");
  const submitBtn = document.getElementById("settings-submit-btn");
  const bannerPreview = document.getElementById("banner-preview");
  const bannerInput = document.getElementById("s-banner");

  function updateBannerPreview(url) {
    if (url) {
      bannerPreview.style.backgroundImage = `url("${url}")`;
      bannerPreview.innerHTML = "";
    } else {
      bannerPreview.style.backgroundImage = "none";
      bannerPreview.innerHTML = '<span><i class="ti ti-photo" style="font-size:1.6rem;"></i></span>';
    }
  }

  bannerInput.addEventListener("input", () => updateBannerPreview(bannerInput.value.trim()));

  async function loadEvent() {
    try {
      const event = await Api.getEvent(claims.event_id);
      document.getElementById("s-name").value = event.name || "";
      document.getElementById("s-description").value = event.description || "";
      document.getElementById("s-date").value = event.date || "";
      document.getElementById("s-time").value = (event.time || "").slice(0, 5);
      document.getElementById("s-location").value = event.location || "";
      document.getElementById("s-banner").value = event.banner_url || "";
      document.getElementById("s-capacity").value = event.max_capacity || "";
      document.getElementById("s-price").value = event.ticket_price || "";
      document.getElementById("s-pix-key").value = event.pix_key || "";
      updateBannerPreview(event.banner_url);
    } catch (err) {
      showToast(errorMessage(err), "error");
    }
  }

  async function loadConfigStatus() {
    const rows = document.querySelectorAll("#config-status-list .config-status-row");
    try {
      const status = await Api.getConfigStatus();
      const items = [
        status.mercadopago_access_token_configured,
        status.mercadopago_public_key_configured,
        status.resend_configured,
      ];
      items.forEach((configured, index) => {
        const badge = rows[index].querySelector(".badge");
        if (configured) {
          badge.className = "badge badge-success";
          badge.innerHTML = '<i class="ti ti-circle-check"></i> Configurado';
        } else {
          badge.className = "badge badge-danger";
          badge.innerHTML = '<i class="ti ti-alert-triangle"></i> Nao configurado';
        }
      });
    } catch (err) {
      showToast(errorMessage(err), "error");
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="ti ti-loader-2"></i> Salvando...';

    let time = document.getElementById("s-time").value;
    if (time && time.length === 5) time = `${time}:00`;

    const payload = {
      name: document.getElementById("s-name").value.trim(),
      description: document.getElementById("s-description").value.trim() || null,
      date: document.getElementById("s-date").value,
      time,
      location: document.getElementById("s-location").value.trim(),
      banner_url: document.getElementById("s-banner").value.trim() || null,
      max_capacity: parseInt(document.getElementById("s-capacity").value, 10),
      ticket_price: document.getElementById("s-price").value,
      pix_key: document.getElementById("s-pix-key").value.trim() || null,
    };

    try {
      await Api.updateEvent(claims.event_id, payload);
      showToast("Configuracoes salvas com sucesso.", "success");
    } catch (err) {
      showToast(errorMessage(err), "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="ti ti-device-floppy"></i> Salvar alteracoes';
    }
  });

  loadEvent();
  loadConfigStatus();
})();
