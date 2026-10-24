// The film card opens in place, one card at a time within its list, and its title collapses it (#21).
// A link or a form on it acts rather than toggles, so the runtime pencil edits a closed card's line in place (#90).
// Under a ledger row the card is always open, and its row's title or its own opens and closes the row (#28, #95).
document.addEventListener("click", (event) => {
  const opens = event.target.closest(".ledger__opens");
  if (opens) return setRowOpen(opens, opens.getAttribute("aria-expanded") !== "true");
  const card = event.target.closest("[data-film-card]");
  if (!card || event.target.closest("a, form")) return;
  const onTitle = event.target.closest(".film-card__toggle");
  const detail = card.closest(".ledger__detail");
  if (detail) {
    if (!onTitle) return;
    // The card's title hides itself, so the focus returns to the row's.
    const opens = document.querySelector(`[aria-controls="${detail.id}"]`);
    setRowOpen(opens, false);
    opens.focus();
    return;
  }
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

function setRowOpen(opens, open) {
  if (open) {
    const list = opens.closest("[data-film-cards]") || document;
    list.querySelectorAll('.ledger__opens[aria-expanded="true"]').forEach((other) => setRowOpen(other, false));
  }
  opens.setAttribute("aria-expanded", String(open));
  opens.closest("tr").classList.toggle("is-open", open);
  document.getElementById(opens.getAttribute("aria-controls")).hidden = !open;
}
