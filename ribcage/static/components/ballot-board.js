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
        // An open card is scored from its bar, never dragged (#122).
        draggable: "li:not(.card-item)",
        sort: false,
        animation: 150,
        // A touch must hold before it drags, or a swipe to scroll would pick a tile up.
        delay: 150,
        delayOnTouchOnly: true,
        ghostClass: "is-dragged",
        // The tray scrolls sideways, so a drag near its ends scrolls it, and the small tiles ask for a wider edge than the default (#126).
        scroll: true,
        scrollSensitivity: 60,
        scrollSpeed: 14,
        // The seen-it toggle is pressed, not dragged by (#121).
        filter: ".seen-toggle",
        preventOnFilter: false,
        // A drag begun in the tray holds it open until the drop, so its last tile leaving doesn't pull the bands up under the pointer (#126).
        onStart: function (event) {
          var tray = event.from.closest(".tray");
          if (tray) tray.setAttribute("data-holding", "");
        },
        onEnd: function (event) {
          board.querySelectorAll("[data-holding]").forEach(function (held) {
            held.removeAttribute("data-holding");
          });
          // The gallery's board has no route to post to, and a tile placed where it began changes nothing.
          if (!url || event.from === event.to) return;
          var values = { suggestion: event.item.dataset.suggestion, to: event.to.dataset.place };
          // A drop into the Veto band may open the film's card, which closes the card open now (#120).
          var other = board.querySelector(".card-item");
          if (other) values.closes = other.dataset.suggestion;
          htmx.ajax("POST", url, { source: event.item, swap: "none", values: values });
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
    // A tile is reached by keyboard, and so is each one the server draws again.
    function focusable() {
      board.querySelectorAll("li[data-suggestion]:not(.card-item):not([tabindex])").forEach(function (item) {
        item.tabIndex = 0;
      });
    }
    focusable();
    document.body.addEventListener("htmx:afterSettle", focusable);
    document.body.addEventListener("htmx:oobAfterSwap", function () {
      setTimeout(focusable, 30);
    });
    // A tile opens as its card where it stands, and the card open before it closes in the same answer (#122).
    var cardAt = board.dataset.cardAt;
    function open(item) {
      if (!cardAt || !item || item.matches(".card-item")) return;
      var other = board.querySelector(".card-item");
      var values = { suggestion: item.dataset.suggestion };
      if (other) values.closes = other.dataset.suggestion;
      htmx.ajax("GET", cardAt, { source: item, target: item, swap: "outerHTML", values: values });
    }
    board.addEventListener("click", function (event) {
      if (event.target.closest(".seen-toggle, a, button, input, textarea")) return;
      var tile = event.target.closest(".tile");
      if (tile) open(tile.closest("li"));
    });
    // Without a pointer, Enter or Space on a focused tile opens it.
    board.addEventListener("keydown", function (event) {
      if ((event.key === "Enter" || event.key === " ") && event.target.matches("li[data-suggestion]:not(.card-item)")) {
        event.preventDefault();
        open(event.target);
      }
    });
    // An opened card, or one moved to its new band, is brought into view; the tile or the title that closes it keeps the focus, and a card a veto drop opened has the cursor in its reason box (#120, #122).
    function bringIntoView() {
      var card = board.querySelector("[data-scroll-here]");
      if (!card) return;
      card.removeAttribute("data-scroll-here");
      card.scrollIntoView({ block: "start", behavior: "smooth" });
      var reason = card.hasAttribute("data-focus-reason") && card.querySelector("[data-vote-reason] textarea");
      card.removeAttribute("data-focus-reason");
      if (reason) return reason.focus({ preventScroll: true });
      var title = card.querySelector(".film-card__toggle");
      if (title && !card.contains(document.activeElement)) title.focus({ preventScroll: true });
    }
    document.body.addEventListener("htmx:afterSettle", bringIntoView);
    document.body.addEventListener("htmx:oobAfterSwap", function () {
      setTimeout(bringIntoView, 30);
    });
    // A placement the server didn't take leaves the tile where it doesn't belong, so the board is loaded again.
    board.addEventListener("htmx:responseError", reload);
    board.addEventListener("htmx:sendError", reload);
    // A moved card whose neighbour this page lacks, such as a film approved since, has no place to land and is dropped, so the board is loaded as it is now (#122).
    document.body.addEventListener("htmx:oobErrorNoTarget", reload);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-board]").forEach(start);
  });
})();
