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
        // A Veto row's reason box and its topics are for typing in and reading, not for dragging by (#120).
        // The seen-it toggle is pressed, not dragged by (#121).
        filter: ".veto-row__detail, .seen-toggle",
        preventOnFilter: false,
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
    // Seen it redraws the tile it sits on, so the keyboard's focus is put back on the new toggle (#121).
    var refocus = null;
    board.addEventListener("htmx:beforeRequest", function (event) {
      var toggle = event.target.closest && event.target.closest(".seen-toggle");
      refocus = toggle && toggle === document.activeElement ? toggle.closest("[data-suggestion]").dataset.suggestion : null;
    });
    document.body.addEventListener("htmx:oobAfterSwap", function (event) {
      var holder = refocus && event.target.closest("[data-suggestion]");
      if (!holder || holder.dataset.suggestion !== refocus) return;
      refocus = null;
      var toggle = holder.querySelector(".seen-toggle");
      if (toggle) toggle.focus();
    });
    // A placement the server didn't take leaves the tile where it doesn't belong, so the board is loaded again.
    board.addEventListener("htmx:responseError", reload);
    board.addEventListener("htmx:sendError", reload);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-board]").forEach(start);
  });
})();
