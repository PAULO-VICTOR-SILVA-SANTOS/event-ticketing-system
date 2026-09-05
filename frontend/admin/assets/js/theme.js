const THEME_KEY = "admin_theme";

const Theme = {
  get() {
    return localStorage.getItem(THEME_KEY) || "light";
  },

  apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);

    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      const label = theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro";
      btn.innerHTML = theme === "dark" ? '<i class="ti ti-sun"></i>' : '<i class="ti ti-moon"></i>';
      btn.setAttribute("aria-label", label);
      btn.title = label;
    });
  },

  toggle() {
    this.apply(this.get() === "dark" ? "light" : "dark");
  },

  init() {
    this.apply(this.get());
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => this.toggle());
    });
  },
};
