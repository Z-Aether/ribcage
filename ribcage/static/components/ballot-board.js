// The ballot's board: Sortable moves a tile between the tray and the bands, and one placement is one post naming the target (#9, #119).
(function () {
  function reload() {
    window.location.reload();
  }

  function start(board) {
    var url = board.dataset.placesAt;
    board.querySelectorAll("[data-place]").forEach(function (list) {
      Sortable.create(list, {
        group: "ballot",
        sort: false,
        animation: 150,
        // A touch must hold before it drags, or a swipe to scroll would pick a tile up.
        delay: 150,
        delayOnTouchOnly: true,
        ghostClass: "is-dragged",
        onEnd: function (event) {
          // The gallery's board has no route to post to, and a tile placed where it began changes nothing.
          if (!url || event.from === event.to) return;
          htmx.ajax("POST", url, {
            source: event.item,
            swap: "none",
            values: { suggestion: event.item.dataset.suggestion, to: event.to.dataset.place },
          });
        },
      });
    });
    // A placement the server didn't take leaves the tile where it doesn't belong, so the board is loaded again.
    board.addEventListener("htmx:responseError", reload);
    board.addEventListener("htmx:sendError", reload);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-board]").forEach(start);
  });
})();
