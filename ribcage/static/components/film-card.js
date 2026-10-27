// The film card opens in place, one card at a time within its list, and its title collapses it (#21).
// A link or a form on it acts rather than toggles, so the runtime pencil edits a closed card's line in place (#90).
// An open card also closes on a click outside it and on Escape, nothing posted, and its boxes stay in the page, so typing in them survives (#131).
// Under a ledger row the card is always open, and its row's title or its own opens and closes the row (#28, #95).
// A press that began inside a card and was released outside it, as a text selection dragged past the edge is, fires its click on a common ancestor, so where the press began is kept (#131).
let pressPath = [];
document.addEventListener("pointerdown", (event) => {
  pressPath = event.composedPath();
}, true);

document.addEventListener("click", (event) => {
  // The path is read as dispatched, so a click that removed its own target still counts as inside.
  const path = event.composedPath();
  const began = pressPath;
  pressPath = [];
  poolCards().forEach((open) => {
    if (!path.includes(open) && !began.includes(open)) setOpen(open, false);
  });
  const opens = event.target.closest(".ledger__opens");
  if (opens) return setRowOpen(opens, opens.getAttribute("aria-expanded") !== "true");
  const card = event.target.closest("[data-film-card]");
  // A card on the ballot opens from its tile and closes by its title, both answered by the server (#122).
  if (!card || event.target.closest("a, form") || card.closest("[data-board]")) return;
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

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || event.defaultPrevented) return;
  poolCards().forEach((open) => {
    setOpen(open, false);
    open.querySelector(".film-card__toggle").focus();
  });
});

// The open cards that close by themselves: a ledger row's and the ballot's have their own ways (#95, #122).
function poolCards() {
  return [...document.querySelectorAll("[data-film-card].is-open")].filter((card) => !card.closest(".ledger__detail, [data-board]"));
}

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
