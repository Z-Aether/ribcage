// A sort by a voter reloads the page with the matrix scrolled back to its left edge, so the column it sorted by can be off-screen on a phone (#157).
// This brings that column's header into view, clear of the sticky film column. Without script the sort works as it did; the page keeps the default scroll.
(function () {
  function bringSortedColumnIntoView() {
    const matrix = document.querySelector(".reveal__scroll");
    const head = matrix && matrix.querySelector("th.reveal__voter[aria-sort]");
    const film = matrix && matrix.querySelector(".reveal__film-head");
    if (!head) return;
    const frame = matrix.getBoundingClientRect();
    const box = head.getBoundingClientRect();
    const left = frame.left + film.getBoundingClientRect().width;
    if (box.left >= left && box.right <= frame.right) return;
    matrix.scrollLeft += box.left - left;
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bringSortedColumnIntoView);
  else bringSortedColumnIntoView();
})();
