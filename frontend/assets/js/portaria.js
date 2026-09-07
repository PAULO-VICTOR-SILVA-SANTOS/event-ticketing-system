(function () {
  const STORAGE_KEY = "portaria_key";

  const el = (id) => document.getElementById(id);

  const gateScreen = el("gate-screen");
  const scannerApp = el("scanner-app");
  const video = el("scanner-video");
  const canvas = el("scanner-canvas");
  const canvasCtx = canvas.getContext("2d", { willReadFrequently: true });

  let portariaKey = null;
  let scanning = false;
  let busy = false;
  let mediaStream = null;
  let rafId = null;

  const REASON_MESSAGES = {
    already_checked_in: "Ingresso ja utilizado",
    payment_pending: "Pagamento pendente",
    invalid_ticket: "Ingresso invalido",
  };

  function showGate(errorMessage) {
    stopCamera();
    scannerApp.classList.add("hidden");
    gateScreen.classList.remove("hidden");
    if (errorMessage) {
      el("gate-error-text").textContent = errorMessage;
      el("gate-error").classList.remove("hidden");
    } else {
      el("gate-error").classList.add("hidden");
    }
  }

  function showScanner() {
    gateScreen.classList.add("hidden");
    scannerApp.classList.remove("hidden");
    startCamera();
    refreshStats();
  }

  async function unlock(key) {
    try {
      await Api.getCheckinStats(key);
      portariaKey = key;
      localStorage.setItem(STORAGE_KEY, key);
      showScanner();
    } catch (err) {
      showGate("Chave invalida. Tente novamente.");
    }
  }

  el("gate-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const key = el("gate-key").value.trim();
    if (key) unlock(key);
  });

  el("logout-btn").addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEY);
    portariaKey = null;
    showGate();
  });

  async function startCamera() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      video.srcObject = mediaStream;
      await video.play();
      scanning = true;
      rafId = requestAnimationFrame(scanFrame);
    } catch (err) {
      el("scanner-hint").textContent =
        "Nao foi possivel acessar a camera. Verifique as permissoes do navegador.";
    }
  }

  function stopCamera() {
    scanning = false;
    if (rafId) cancelAnimationFrame(rafId);
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
  }

  function scanFrame() {
    if (!scanning) return;

    if (!busy && video.readyState === video.HAVE_ENOUGH_DATA) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvasCtx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = canvasCtx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(imageData.data, imageData.width, imageData.height, {
        inversionAttempts: "dontInvert",
      });

      if (code && code.data) {
        handleScannedValue(code.data);
      }
    }

    rafId = requestAnimationFrame(scanFrame);
  }

  function extractTicketCode(rawValue) {
    try {
      const parsed = JSON.parse(rawValue);
      return parsed.ticket_code || null;
    } catch (err) {
      return rawValue.trim() || null;
    }
  }

  async function handleScannedValue(rawValue) {
    const ticketCode = extractTicketCode(rawValue);
    if (!ticketCode) return;

    busy = true;
    try {
      const result = await Api.checkin(ticketCode, portariaKey);
      showResult(true, result.name, "Entrada liberada");
    } catch (err) {
      const reason = err.data && err.data.reason;
      const message = REASON_MESSAGES[reason] || "Nao foi possivel validar o ingresso";
      let detail = "";
      if (reason === "already_checked_in" && err.data.checkin_at) {
        const time = new Date(err.data.checkin_at).toLocaleTimeString("pt-BR", {
          hour: "2-digit",
          minute: "2-digit",
        });
        detail = ` as ${time}`;
      }
      showResult(false, message + detail, "");
    }

    await refreshStats();
  }

  function showResult(isSuccess, primaryText, secondaryText) {
    const overlay = el("result-overlay");
    overlay.classList.remove("hidden", "is-success", "is-error");
    overlay.classList.add(isSuccess ? "is-success" : "is-error");

    el("result-icon").innerHTML = isSuccess
      ? '<i class="ti ti-circle-check"></i>'
      : '<i class="ti ti-circle-x"></i>';
    el("result-name").textContent = primaryText;
    el("result-reason").textContent = secondaryText;

    setTimeout(() => {
      overlay.classList.add("hidden");
      busy = false;
    }, 2200);
  }

  async function refreshStats() {
    if (!portariaKey) return;
    try {
      const stats = await Api.getCheckinStats(portariaKey);
      el("stats-count").innerHTML = `${stats.total_checkin} <span>/ ${stats.total_confirmados} entraram</span>`;
      el("stats-fill").style.width = `${Math.min(stats.percentual, 100)}%`;
    } catch (err) {
      // ignore transient stats failures
    }
  }

  const savedKey = localStorage.getItem(STORAGE_KEY);
  if (savedKey) {
    unlock(savedKey);
  }

  setInterval(refreshStats, 15000);
})();
