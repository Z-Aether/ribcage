// A reveal row opens as its film's card under it, answered by the server, one card at a time (#29, #158).
// A click on a row opens it, and closes the card open before it in the same answer, a row clicked at once waiting for the last answer; the card's title, a click outside it and Escape close it.
// The sort in force rides on every request so the answer keeps it, and the matrix's own horizontal scroll is never touched.
(function () {
  function start(reveal) {
    const cardAt = reveal.dataset.cardAt;
    if (!cardAt) return;
    const sort = () => reveal.dataset.sort || "";
    const groupOf = (node) => node.closest(".reveal__group");
    const openGroup = () => reveal.querySelector(".reveal__group:has(.reveal__detail)");
    const idOf = (group) => group.querySelector(".reveal__row").dataset.suggestion;

    // A row clicked before the last one's answer is swapped in waits for it, so it reads which card is open then and closes it: one card is open at a time.
    let asking = Promise.resolve();

    function open(group) {
      const ask = () => {
        const other = openGroup();
        const values = { suggestion: idOf(group), sort: sort() };
        if (other) values.closes = idOf(other);
        return htmx.ajax("GET", cardAt, { source: group, target: group, swap: "outerHTML", values });
      };
      asking = asking.then(ask, ask);
      return asking;
    }

    function close(group) {
      return htmx.ajax("GET", cardAt, { source: group, target: group, swap: "outerHTML", values: { suggestion: idOf(group), sort: sort(), close: "1" } });
    }

    // A click on a row opens its card, or closes it when it is the open one; a link in the row is left to act.
    reveal.addEventListener("click", (event) => {
      const row = event.target.closest(".reveal__row");
      if (!row || event.target.closest("a")) return;
      const group = groupOf(row);
      if (group.querySelector(".reveal__detail")) close(group);
      else open(group);
    });

    // A press that began in the card and was released outside it, as a text selection dragged past the edge is, is no outside click.
    let pressPath = [];
    document.addEventListener("pointerdown", (event) => {
      pressPath = event.composedPath();
    }, true);
    document.addEventListener("click", (event) => {
      const group = openGroup();
      const began = pressPath;
      pressPath = [];
      if (!group) return;
      const card = group.querySelector(".reveal__card");
      // A row's own click opens or closes through its handler; a link navigates on its own.
      if (event.composedPath().includes(card) || began.includes(card) || (reveal.contains(event.target) && event.target.closest(".reveal__row")) || event.target.closest("a")) return;
      close(group);
    });

    // Escape closes the open card and the focus returns to its row's title.
    document.addEventListener("keydown", (event) => {
      const group = openGroup();
      if (event.key !== "Escape" || event.defaultPrevented || !group) return;
      const id = idOf(group);
      const request = close(group);
      if (request) request.then(() => {
        const back = reveal.querySelector(`.reveal__row[data-suggestion="${id}"] .reveal__open`);
        if (back) back.focus({ preventScroll: true });
      });
    });

    // The card's title closes it by its own request and hides itself, so the focus goes back to the row's title once the row is drawn.
    let titleClosed = null;
    reveal.addEventListener("click", (event) => {
      const title = event.target.closest(".film-card__toggle");
      if (title) titleClosed = idOf(groupOf(title));
    });
    document.body.addEventListener("htmx:afterSettle", () => {
      if (titleClosed === null) return;
      const back = reveal.querySelector(`.reveal__row[data-suggestion="${titleClosed}"] .reveal__open`);
      titleClosed = null;
      if (back) back.focus({ preventScroll: true });
    });

    // An opened card comes into view with its row at the top, moving the page down and never sideways.
    function bringIntoView() {
      const group = reveal.querySelector("[data-scroll-here]");
      if (!group) return;
      group.removeAttribute("data-scroll-here");
      const box = group.getBoundingClientRect();
      if (box.top < 0 || box.bottom > window.innerHeight) window.scrollBy({ top: box.top - 16, behavior: "smooth" });
      const title = group.querySelector(".film-card__toggle");
      if (title && !group.contains(document.activeElement)) title.focus({ preventScroll: true });
    }
    document.body.addEventListener("htmx:afterSettle", bringIntoView);
    // A row the server doesn't take, or an answer that finds no place, loads the page as it is now.
    reveal.addEventListener("htmx:responseError", () => window.location.reload());
    reveal.addEventListener("htmx:sendError", () => window.location.reload());
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-reveal]").forEach(start);
  });
})();
