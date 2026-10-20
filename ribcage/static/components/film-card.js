// The film card opens in place, one card at a time within its list, and its title collapses it (#21).
document.addEventListener("click", (event) => {
  const card = event.target.closest("[data-film-card]");
  if (!card || event.target.closest("a")) return;
  const onTitle = event.target.closest(".film-card__toggle");
  const open = card.classList.contains("is-open");
  if (open && !onTitle) return;
  if (!open) {
    const list = card.closest("[data-film-cards]") || document;
    list.querySelectorAll("[data-film-card].is-open").forEach((other) => setOpen(other, false));
  }
  setOpen(card, !open);
});

function setOpen(card, open) {
  card.classList.toggle("is-open", open);
  card.querySelector(".film-card__toggle").setAttribute("aria-expanded", String(open));
}
