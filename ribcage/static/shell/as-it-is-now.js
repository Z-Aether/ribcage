// Chromium keeps even no-store pages in its back/forward cache, so a restored page reloads, by GET so no form is sent again (#84).
addEventListener("pageshow", (event) => {
  if (event.persisted) location.replace(location.href);
});
