// The name menu is a <details>, so it opens without script; this closes it on a click outside, Escape or tabbing out (#73).
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

// Only focus that lands elsewhere closes it: Safari clicks focus nothing, and closing then would swallow the click (#73).
document.addEventListener("focusout", (event) => {
  const menu = event.target.closest?.("[data-voter-menu][open]");
  if (menu && event.relatedTarget && !menu.contains(event.relatedTarget)) menu.open = false;
});
