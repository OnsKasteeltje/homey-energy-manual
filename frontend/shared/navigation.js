const ITEMS = [
  { key: "live", label: "Live", href: "../live/" },
  { key: "settings", label: "Invoer", href: "../settings/" },
  { key: "history", label: "Historie", href: "../history/" },
  { key: "planner", label: "Planner", href: "../planner/" },
  { key: "pv-flex", label: "Evaluatie", href: "../pv-flex/" },
  { key: "heating", label: "Verwarming", href: "../heating/" },
  { key: "ai", label: "AI Analyse", href: "../ai/" },
  { key: "groups", label: "Groepen & fasen", disabled: true },
];

const MOBILE_PRIMARY = ["live", "settings", "history"];
const MOBILE_MORE = ["planner", "pv-flex", "heating", "ai", "groups"];

const ICONS = {
  live: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
  settings: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M6 14v6"/></svg>',
  history: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7v5l3 2M4.9 5.3A9 9 0 1 1 3 12M3 5v5h5"/></svg>',
  more: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>',
};

function currentPage() {
  const parts = window.location.pathname.split("/").filter(Boolean);
  return parts.at(-1) || "live";
}

function markActive(element, item, active) {
  if (item.key === active) {
    element.classList.add("active");
    element.setAttribute("aria-current", "page");
  }
  return element;
}

function desktopItem(item, active) {
  if (item.disabled) {
    const span = document.createElement("span");
    span.textContent = item.label;
    span.setAttribute("aria-disabled", "true");
    return span;
  }
  const link = document.createElement("a");
  link.href = item.href;
  link.textContent = item.label;
  return markActive(link, item, active);
}

function mobileLink(item, active) {
  const link = document.createElement("a");
  link.href = item.href;
  link.className = "ems-mobile-tab";
  link.innerHTML = (ICONS[item.key] || "") + '<span>' + item.label + '</span>';
  return markActive(link, item, active);
}

function renderNavigation() {
  const nav = document.querySelector("[data-ems-main-nav]");
  if (!nav) return;

  const active = currentPage();
  nav.classList.add("ems-main-nav");

  const desktop = document.createElement("div");
  desktop.className = "ems-nav-desktop";
  desktop.replaceChildren(...ITEMS.map((item) => desktopItem(item, active)));
  nav.replaceChildren(desktop);

  document.querySelector(".ems-mobile-dock")?.remove();
  document.querySelector(".ems-mobile-more-sheet")?.remove();

  const dock = document.createElement("nav");
  dock.className = "ems-mobile-dock";
  dock.setAttribute("aria-label", "Mobiele hoofdnavigatie");

  const mobile = document.createElement("div");
  mobile.className = "ems-nav-mobile";
  const primary = MOBILE_PRIMARY.map((key) => ITEMS.find((item) => item.key === key))
    .filter(Boolean)
    .map((item) => mobileLink(item, active));

  const moreButton = document.createElement("button");
  moreButton.type = "button";
  moreButton.className = "ems-mobile-tab ems-mobile-more-toggle";
  moreButton.setAttribute("aria-expanded", "false");
  moreButton.setAttribute("aria-controls", "ems-mobile-more-sheet");
  moreButton.innerHTML = ICONS.more + "<span>Meer</span>";
  if (MOBILE_MORE.includes(active)) moreButton.classList.add("active");

  mobile.replaceChildren(...primary, moreButton);
  dock.appendChild(mobile);

  const sheet = document.createElement("div");
  sheet.id = "ems-mobile-more-sheet";
  sheet.className = "ems-mobile-more-sheet";
  sheet.hidden = true;
  sheet.setAttribute("aria-label", "Meer EMS-pagina's");

  for (const key of MOBILE_MORE) {
    const item = ITEMS.find((candidate) => candidate.key === key);
    if (!item) continue;
    if (item.disabled) {
      const disabled = document.createElement("span");
      disabled.className = "ems-mobile-more-item disabled";
      disabled.textContent = item.label;
      disabled.setAttribute("aria-disabled", "true");
      sheet.appendChild(disabled);
      continue;
    }
    const link = document.createElement("a");
    link.className = "ems-mobile-more-item";
    link.href = item.href;
    link.textContent = item.label;
    markActive(link, item, active);
    sheet.appendChild(link);
  }

  const closeSheet = () => {
    sheet.hidden = true;
    moreButton.setAttribute("aria-expanded", "false");
  };

  moreButton.addEventListener("click", (event) => {
    event.stopPropagation();
    const opening = sheet.hidden;
    sheet.hidden = !opening;
    moreButton.setAttribute("aria-expanded", String(opening));
  });
  sheet.addEventListener("click", (event) => event.stopPropagation());
  document.addEventListener("click", closeSheet);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSheet();
  });

  document.body.append(dock, sheet);
}

renderNavigation();
