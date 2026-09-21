const ITEMS = [
  { key: "live", label: "Live", href: "../live/" },
  { key: "settings", label: "Invoer", href: "../settings/" },
  { key: "history", label: "Historie", href: "../history/" },
  { key: "planner", label: "Planner", href: "../planner/" },
  { key: "pv-flex", label: "PV & Flex", href: "../pv-flex/" },
  { key: "heating", label: "Verwarming", href: "../heating/" },
  { key: "groups", label: "Groepen & fasen", disabled: true },
];

function currentPage() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts.at(-1) || "live";
}

function renderNavigation() {
  const nav = document.querySelector("[data-ems-main-nav]");
  if (!nav) return;

  const active = currentPage();
  nav.replaceChildren(...ITEMS.map((item) => {
    if (item.disabled) {
      const span = document.createElement("span");
      span.textContent = item.label;
      span.setAttribute("aria-disabled", "true");
      return span;
    }
    const link = document.createElement("a");
    link.href = item.href;
    link.textContent = item.label;
    if (item.key === active) {
      link.classList.add("active");
      link.setAttribute("aria-current", "page");
    }
    return link;
  }));
}

renderNavigation();
