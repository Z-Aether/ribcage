// Flips the theme direction in place and remembers it, so other pages wear it too (#58).
(() => {
  const nav = document.querySelector("[data-direction-switch]");
  const choices = [...nav.querySelectorAll("[data-direction-choice]")];
  const keys = choices.map((choice) => choice.dataset.directionChoice);

  function choose(key) {
    document.documentElement.dataset.direction = key;
    document.cookie = `theme_direction=${key}; path=/; SameSite=Lax`;
    choices.forEach((choice) => choice.toggleAttribute("aria-current", choice.dataset.directionChoice === key));
    const url = new URL(location.href);
    url.searchParams.set("direction", key);
    history.replaceState(null, "", url);
  }

  function step(by) {
    const at = keys.indexOf(document.documentElement.dataset.direction);
    choose(keys[(at + by + keys.length) % keys.length]);
  }

  nav.addEventListener("click", (event) => {
    const choice = event.target.closest("[data-direction-choice]");
    const stepper = event.target.closest("[data-direction-step]");
    if (choice) {
      event.preventDefault();
      choose(choice.dataset.directionChoice);
    } else if (stepper) {
      step(Number(stepper.dataset.directionStep));
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.target.closest("input, textarea, select, [contenteditable]")) return;
    if (event.key === "ArrowLeft") step(-1);
    if (event.key === "ArrowRight") step(1);
  });

  choose(document.documentElement.dataset.direction);
})();
