(() => {
  const body = document.body;
  const menu = document.querySelector(".mobile-menu");
  const closeTargets = document.querySelectorAll("[data-sidebar-close]");

  function setNavigation(open) {
    body.classList.toggle("navigation-open", open);
    if (menu) menu.setAttribute("aria-expanded", String(open));
  }

  menu?.addEventListener("click", () => {
    setNavigation(!body.classList.contains("navigation-open"));
  });
  closeTargets.forEach((target) => target.addEventListener("click", () => setNavigation(false)));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setNavigation(false);
  });

  window.ezeusUI = {
    setBusy(button, busy, label = "Wird verarbeitet …") {
      if (!button) return;
      if (busy) {
        button.dataset.originalLabel = button.textContent;
        button.textContent = label;
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
      } else {
        button.textContent = button.dataset.originalLabel || button.textContent;
        button.disabled = false;
        button.removeAttribute("aria-busy");
      }
    },
    announce(element, text, tone = "success") {
      if (!element) return;
      element.textContent = text;
      element.className = `notice ${tone}`;
      element.hidden = !text;
    },
  };
})();
