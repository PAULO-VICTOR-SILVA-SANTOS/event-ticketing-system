(function () {
  Theme.init();

  const existingClaims = Auth.getClaims();
  if (existingClaims && !Auth.isExpired(existingClaims)) {
    window.location.href = "dashboard.html";
    return;
  }

  const form = document.getElementById("login-form");
  const errorBox = document.getElementById("login-error");
  const errorText = document.getElementById("login-error-text");
  const submitBtn = document.getElementById("login-submit");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorBox.hidden = true;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="ti ti-loader-2"></i> Entrando...';

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
      const data = await Api.login(username, password);
      Auth.setToken(data.access_token);
      window.location.href = "dashboard.html";
    } catch (err) {
      errorText.textContent = err.message || "Usuario ou senha invalidos.";
      errorBox.hidden = false;
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="ti ti-login-2"></i> Entrar';
    }
  });
})();
