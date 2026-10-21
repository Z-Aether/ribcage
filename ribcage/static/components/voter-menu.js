// The name menu is a <details>, so it opens without script; this closes it on a click outside or Escape (#73).
document.addEventListener("click", (event) => {
  document.querySelectorAll("[data-voter-menu][open]").forEach((menu) => {
    if (!menu.contains(event.target)) menu.open = false;
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const menu = event.target.closest?.("[data-voter-menu][open]");
  if (!menu) return;
  menu.open = false;
  menu.querySelector("summary").focus();
});
