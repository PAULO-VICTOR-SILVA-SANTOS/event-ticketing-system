(function () {
  const claims = Auth.requireAuth();
  if (!claims) return;

  renderSidebar("dashboard");

  async function load() {
    try {
      const [event, dashboard, participants] = await Promise.all([
        Api.getEvent(claims.event_id),
        Api.getDashboard(),
        Api.listParticipants(),
      ]);

      document.getElementById("event-title").textContent = event.name;
      document.getElementById("event-subtitle").textContent = `${formatDate(event.date)} - ${event.location}`;

      document.getElementById("stat-total").textContent = dashboard.total_registered;
      document.getElementById("stat-paid").textContent = dashboard.total_paid;
      document.getElementById("stat-pending").textContent = dashboard.total_pending;
      document.getElementById("stat-collected").textContent = formatCurrency(dashboard.total_collected);
      document.getElementById("stat-collected-sub").textContent = `${dashboard.total_paid} pagamento(s) confirmado(s)`;

      const filled = dashboard.total_registered;
      const capacity = filled + dashboard.remaining_slots;
      const pct = capacity > 0 ? Math.min(100, Math.round((filled / capacity) * 100)) : 0;
      document.getElementById("slots-progress").style.width = `${pct}%`;
      document.getElementById("slots-badge").textContent = `${filled} / ${capacity} (${pct}%)`;

      document.getElementById("fin-collected").textContent = formatCurrency(dashboard.total_collected);
      document.getElementById("fin-expenses").textContent = formatCurrency(dashboard.total_expenses);
      document.getElementById("fin-remaining").textContent = formatCurrency(dashboard.remaining_to_collect);
      document.getElementById("fin-per-person").textContent = formatCurrency(dashboard.value_per_person);

      renderRegistrationsChart(participants);
      renderMethodsChart(participants);
    } catch (err) {
      showToast(errorMessage(err), "error");
    }
  }

  function renderRegistrationsChart(participants) {
    const counts = {};
    participants.forEach((p) => {
      const day = p.created_at.slice(0, 10);
      counts[day] = (counts[day] || 0) + 1;
    });
    const days = Object.keys(counts).sort();
    const values = days.map((d) => counts[d]);
    const labels = days.map((d) => formatDate(d));

    new Chart(document.getElementById("registrations-chart"), {
      type: "line",
      data: {
        labels: labels.length ? labels : ["-"],
        datasets: [
          {
            label: "Cadastros",
            data: values.length ? values : [0],
            borderColor: "#8b5cf6",
            backgroundColor: "rgba(139, 92, 246, 0.12)",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } },
        },
      },
    });
  }

  function renderMethodsChart(participants) {
    const pixCount = participants.filter((p) => p.payment_method === "pix").length;
    const cardCount = participants.filter((p) => p.payment_method === "card").length;

    new Chart(document.getElementById("methods-chart"), {
      type: "doughnut",
      data: {
        labels: ["Pix", "Cartao"],
        datasets: [
          {
            data: [pixCount, cardCount],
            backgroundColor: ["#8b5cf6", "#22d3ee"],
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } },
      },
    });
  }

  load();
})();
