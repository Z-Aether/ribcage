// The ballot's board: Sortable moves a tile between the tray and the bands, and one placement is one post naming the target (#9, #119).
(function () {
  function reload() {
    window.location.reload();
  }

  // A close swaps the card for its tile, so the reason typed and not saved is kept here by film until that card opens again; a reload drops it (#131).
  var typed = {};

  function stash(card) {
    var box = card && card.querySelector("[data-vote-reason] textarea");
    if (!box) return;
    // The baseline is the saved text, not defaultValue, which holds the typing once a refusal draws the box again (#132).
    var saved = (box.dataset.saved || "").replace(/\r\n/g, "\n");
    if (box.value.replace(/\r\n/g, "\n") !== saved) typed[card.dataset.suggestion] = box.value;
    else delete typed[card.dataset.suggestion];
  }

  function restore(board) {
    board.querySelectorAll(".card-item").forEach(function (card) {
      var text = typed[card.dataset.suggestion];
      var box = card.querySelector("[data-vote-reason] textarea");
      if (text === undefined || !box) return;
      delete typed[card.dataset.suggestion];
      box.value = text;
      // The box now differs from what is saved, which anything watching it for a change reads (#132).
      box.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  // A saved reason closes its card, so words stashed for the film before are stale and would overwrite it when the card next opens (#132).
  document.body.addEventListener("htmx:beforeSwap", function (event) {
    var form = event.detail.requestConfig && event.detail.requestConfig.elt;
    if (!form || !form.matches || !form.matches("[data-vote-reason] form")) return;
    if (event.detail.xhr.getResponseHeader("HX-Retarget")) delete typed[form.elements.suggestion.value];
  });

  function start(board) {
    // A drag is not a click: while one runs, and just after, nothing closes or opens (#131).
    var dragging = false;
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
          dragging = true;
          var tray = event.from.closest(".tray");
          if (tray) tray.setAttribute("data-holding", "");
        },
        onEnd: function (event) {
          setTimeout(function () {
            dragging = false;
          }, 50);
          board.querySelectorAll("[data-holding]").forEach(function (held) {
            held.removeAttribute("data-holding");
          });
          // The gallery's board has no route to post to, and a tile placed where it began changes nothing.
          if (!url || event.from === event.to) return;
          var values = { suggestion: event.item.dataset.suggestion, to: event.to.dataset.place };
          // A drop into the Veto band may open the film's card, which closes the card open now (#120).
          var other = board.querySelector(".card-item");
          if (other) {
            stash(other);
            values.closes = other.dataset.suggestion;
          }
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
      if (other) {
        stash(other);
        values.closes = other.dataset.suggestion;
      }
      htmx.ajax("GET", cardAt, { source: item, target: item, swap: "outerHTML", values: values });
    }
    // The tile a click opens, if it opens one.
    function opensOn(event) {
      if (event.target.closest(".seen-toggle, a, button, input, textarea")) return null;
      var tile = event.target.closest(".tile");
      return tile ? tile.closest("li") : null;
    }
    board.addEventListener("click", function (event) {
      if (dragging) return;
      var item = opensOn(event);
      if (item) open(item);
    });
    // The open card closes to its tile through the server, as its title does, with its typing kept (#122, #131).
    function close() {
      var card = board.querySelector(".card-item");
      if (!cardAt || !card) return null;
      stash(card);
      return htmx.ajax("GET", cardAt, { source: card, target: card, swap: "outerHTML", values: { suggestion: card.dataset.suggestion, close: "1" } });
    }
    // The title closes by its own request; its typing is kept as it goes.
    board.addEventListener("click", function (event) {
      var title = event.target.closest(".film-card__toggle");
      if (title) stash(title.closest(".card-item"));
    });
    // A click anywhere outside the open card closes it, unless the click opens a tile, which closes it in the same answer.
    // A press that began in the card and was released outside it, a text selection dragged past the edge, is no outside click.
    var pressPath = [];
    document.addEventListener("pointerdown", function (event) {
      pressPath = event.composedPath();
    }, true);
    document.addEventListener("click", function (event) {
      var card = board.querySelector(".card-item");
      var began = pressPath;
      pressPath = [];
      if (dragging || !card || event.composedPath().includes(card) || began.includes(card)) return;
      if (board.contains(event.target) && opensOn(event)) return;
      close();
    });
    document.addEventListener("keydown", function (event) {
      var card = board.querySelector(".card-item");
      if (event.key !== "Escape" || event.defaultPrevented || !card) return;
      var request = close();
      if (!request) return;
      // The tile that replaces the card is where the focus goes, as when the title closes it.
      request.then(function () {
        var tile = board.querySelector('li[data-suggestion="' + card.dataset.suggestion + '"]');
        if (!tile) return;
        tile.tabIndex = 0;
        tile.focus({ preventScroll: true });
      });
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
    document.body.addEventListener("htmx:afterSettle", function () {
      restore(board);
      bringIntoView();
    });
    document.body.addEventListener("htmx:oobAfterSwap", function () {
      setTimeout(function () {
        restore(board);
        bringIntoView();
      }, 30);
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
