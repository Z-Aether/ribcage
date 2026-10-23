// The pool's Everyone's / Mine filter switches in the page: it sets which choice the pool is on, and the theme hides the rest (#91).
document.querySelectorAll("[data-pool-filter]").forEach((filter) => {
  filter.hidden = false;
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-pool-filter] [data-choice]");
  if (!button) return;
  button.closest("[data-pool]").dataset.filter = button.dataset.choice;
  button.parentElement.querySelectorAll("[data-choice]").forEach((other) => {
    other.setAttribute("aria-pressed", String(other === button));
  });
});
