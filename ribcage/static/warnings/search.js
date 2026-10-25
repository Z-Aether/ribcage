// The search filters the rows already on the page and sends nothing; it shows only once this script has run (#108).
const search = document.querySelector("[data-warnings-search]");
const box = search?.querySelector("input");
const noMatch = document.querySelector("[data-warnings-no-match]");
const wasOpen = new Map();

function filter() {
  const words = box.value.toLowerCase().split(/\s+/).filter(Boolean);
  const sections = document.querySelectorAll(".warnings__section");
  if (!words.length) {
    // Clearing puts the page back as it was: every section as it stood before the search began.
    document.querySelectorAll(".warnings__topic").forEach((row) => (row.hidden = false));
    sections.forEach((section) => {
      section.hidden = false;
      if (wasOpen.has(section)) section.open = wasOpen.get(section);
    });
    wasOpen.clear();
    noMatch.hidden = true;
    return;
  }
  let any = false;
  sections.forEach((section) => {
    if (!wasOpen.has(section)) wasOpen.set(section, section.open);
    let matching = 0;
    section.querySelectorAll(".warnings__topic").forEach((row) => {
      const matches = words.every((word) => row.dataset.search.includes(word));
      row.hidden = !matches;
      if (matches) matching += 1;
    });
    section.hidden = !matching;
    if (matching) section.open = true;
    any ||= matching > 0;
  });
  noMatch.hidden = any;
}

if (box) {
  search.hidden = false;
  box.addEventListener("input", filter);
  // A tick's swap morphs the row back to the server's markup, so the filter is applied again once it settles; this script loads before holds-the-row.js, so the row is placed before it is held.
  document.addEventListener("htmx:afterSettle", filter);
  // Enter in the box must not do anything; it is in no form, but a stray one would reload the page.
  box.addEventListener("keydown", (event) => {
    if (event.key === "Enter") event.preventDefault();
  });
}
