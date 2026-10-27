// A box's Save waits for a change: it is disabled while the box holds the text it was saved with, and enabled as soon as the box differs (#132).
// A form marked data-save-waits holds its boxes, each naming its saved text in data-saved; one more box or flag joins the same check (#133).
// A box drawn holding words not yet saved, data-unsaved, starts enabled; without script Save is always enabled and the post is as it was.
(function () {
  function changed(form) {
    return [...form.querySelectorAll("[data-saved]")].some((box) => box.value.replace(/\r\n/g, "\n") !== box.dataset.saved.replace(/\r\n/g, "\n"));
  }

  // A form is fresh until the voter types in it, and again once it is posted, so what the server answers is read as drawn.
  function sync(form, fresh) {
    const save = form.querySelector('button[type="submit"]');
    if (!save) return;
    save.disabled = !(changed(form) || (fresh && !form.touched && form.hasAttribute("data-unsaved")));
  }

  function syncAll(root) {
    root.querySelectorAll("form[data-save-waits]").forEach((form) => sync(form, true));
  }

  document.addEventListener("input", (event) => {
    const form = event.target.closest && event.target.closest("form[data-save-waits]");
    if (!form) return;
    form.touched = true;
    sync(form, false);
  });

  // A save from the keyboard closes the card under the focus, so the focus goes back to the title, or the tile on the ballot, as Escape does (#131, #132).
  let keyboardSave = null;

  document.body.addEventListener("htmx:beforeRequest", (event) => {
    const form = event.target;
    if (!form.matches || !form.matches("form[data-save-waits]")) return;
    form.touched = false;
    keyboardSave = form.contains(document.activeElement) && form.elements.suggestion ? { form, id: form.elements.suggestion.value } : null;
  });

  // A save that fails never settles, so it is let go, and another request's settle is no save's (#132).
  const letGo = () => { keyboardSave = null; };
  document.body.addEventListener("htmx:responseError", letGo);
  document.body.addEventListener("htmx:sendError", letGo);

  document.body.addEventListener("htmx:afterSettle", (event) => {
    if (!keyboardSave || !event.detail.requestConfig || event.detail.requestConfig.elt !== keyboardSave.form) return;
    const id = keyboardSave.id;
    keyboardSave = null;
    if (!id || (document.activeElement && document.activeElement !== document.body)) return;
    const tile = document.querySelector(`[data-board] li[data-suggestion="${id}"]:not(.card-item)`);
    if (tile) {
      tile.tabIndex = 0;
      return tile.focus({ preventScroll: true });
    }
    const title = document.querySelector(`[data-film-card][data-suggestion="${id}"]:not(.is-open) .film-card__toggle`);
    if (title) title.focus({ preventScroll: true });
  });

  document.addEventListener("DOMContentLoaded", () => syncAll(document));
  // Each form the server draws again, in the swap or out of band, and a page shown again from the history, is read as drawn.
  document.body.addEventListener("htmx:afterSettle", () => syncAll(document));
  document.body.addEventListener("htmx:oobAfterSwap", () => syncAll(document));
  window.addEventListener("pageshow", () => syncAll(document));

  // A saved note closes its card, which shrinks the page under the pointer; the card is kept in view (#132).
  document.body.addEventListener("htmx:afterSwap", (event) => {
    const card = event.target.matches && event.target.matches("[data-film-card]:not(.is-open)") ? event.target : null;
    if (!card || !event.detail.requestConfig || !event.detail.requestConfig.elt.matches("[data-save-waits]")) return;
    const box = card.getBoundingClientRect();
    if (box.top < 0 || box.bottom > window.innerHeight) card.scrollIntoView({ block: "nearest" });
  });
})();
