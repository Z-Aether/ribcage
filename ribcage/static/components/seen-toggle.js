// The gallery's seen-it toggles post nowhere, so they only flip their tile's look; a real one has an hx-post and the server answers (#121).
document.addEventListener("click", function (event) {
  var toggle = event.target.closest(".seen-toggle:not([hx-post])");
  if (!toggle) return;
  var on = toggle.getAttribute("aria-pressed") !== "true";
  toggle.setAttribute("aria-pressed", on ? "true" : "false");
  toggle.classList.toggle("is-on", on);
  toggle.closest(".tile").classList.toggle("is-seen-it", on);
});
