// A slate ledger row opens its breakdown in place on a click and closes it on a second (#164).
document.addEventListener("click", (event) => {
  const row = event.target.closest("[data-slate-row]");
  if (!row || event.target.closest("a, form, input, select, textarea, label")) return;
  const opens = row.querySelector(".slate-row__opens");
  const open = opens.getAttribute("aria-expanded") !== "true";
  opens.setAttribute("aria-expanded", String(open));
  row.classList.toggle("is-open", open);
  document.getElementById(opens.getAttribute("aria-controls")).hidden = !open;
});
