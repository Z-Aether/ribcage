// Choosing a picker tile for a film already in the pool opens its card there instead, so the voter writes a note (#26, #92).
document.addEventListener("click", (event) => {
  const tile = event.target.closest("[data-opens-suggestion]");
  if (!tile) return;
  const card = document.querySelector(`[data-film-card][data-suggestion="${tile.dataset.opensSuggestion}"]`);
  // Suggested since this page loaded: the page as it is now holds its card.
  if (!card) {
    window.location.reload();
    return;
  }
  // Mine would hide another voter's card, so the pool goes back to Everyone's first (#91, #92).
  const everyone = card.closest("[data-pool]")?.querySelector('[data-pool-filter] [data-choice="everyone"]');
  if (everyone && everyone.getAttribute("aria-pressed") !== "true") everyone.click();
  const toggle = card.querySelector(".film-card__toggle");
  if (!card.classList.contains("is-open")) toggle.click();
  toggle.focus({ preventScroll: true });
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  card.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
});
