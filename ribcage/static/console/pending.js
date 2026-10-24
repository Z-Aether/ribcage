// A confirm marked data-pending disables as its form posts and reads what is under way, since a move's refresh can keep
// the answer waiting about 20 s; a second click or Enter posts nothing more (#104).
addEventListener("submit", (event) => {
  const form = event.target;
  const button = form.querySelector("button[data-pending]");
  if (!button) return;
  if (form.dataset.posting) {
    event.preventDefault();
    return;
  }
  form.dataset.posting = "true";
  form.setAttribute("aria-busy", "true");
  button.disabled = true;
  button.textContent = button.dataset.pending;
});
