// Ticking two slate rows asks the server for their swap and lights the dots where their films differ; a third tick unticks the first (#24, #170).
(function () {
  const ticked = [];
  const slot = () => document.getElementById("swap-panel");

  function lightTheDifferences() {
    document.querySelectorAll(".slate-dot--differs").forEach((cell) => cell.classList.remove("slate-dot--differs"));
    document.querySelectorAll("[data-slate-row].is-ticked").forEach((row) => row.classList.remove("is-ticked"));
    ticked.forEach((box) => box.closest("[data-slate-row]").classList.add("is-ticked"));
    if (ticked.length !== 2) return;
    const [left, right] = ticked.map((box) => box.closest("[data-slate-row]"));
    const held = (cell) => !!(cell && cell.querySelector(".slate-dot__mark"));
    left.querySelectorAll("td.slate-dot[data-film]").forEach((cell) => {
      const other = right.querySelector(`td.slate-dot[data-film="${cell.dataset.film}"]`);
      if (held(cell) !== held(other)) {
        cell.classList.add("slate-dot--differs");
        other.classList.add("slate-dot--differs");
      }
    });
  }

  function askForThePanel() {
    const panel = slot();
    if (!panel) return;
    if (ticked.length !== 2) {
      panel.dataset.asking = "";
      panel.replaceChildren();
      panel.hidden = true;
      return;
    }
    const [from, to] = ticked;
    const query = new URLSearchParams({ a: from.value, b: to.value, from: from.dataset.label, to: to.dataset.label });
    const url = `${panel.dataset.at}?${query}`;
    panel.dataset.asking = url;
    htmx.ajax("GET", url, { target: panel, swap: "innerHTML" }).then(() => {
      if (panel.dataset.asking === url) panel.hidden = false;
    });
  }

  document.addEventListener("change", (event) => {
    const box = event.target.closest("[data-swap-tick]");
    if (!box) return;
    const place = ticked.indexOf(box);
    if (box.checked && place < 0) {
      ticked.push(box);
      if (ticked.length > 2) ticked.shift().checked = false;
    } else if (!box.checked && place >= 0) {
      ticked.splice(place, 1);
    }
    lightTheDifferences();
    askForThePanel();
  });

  // An answer for a pair no longer ticked is dropped, not swapped in over the current one.
  document.addEventListener("htmx:beforeSwap", (event) => {
    const panel = slot();
    if (panel && event.detail.target === panel && event.detail.pathInfo.requestPath !== panel.dataset.asking) {
      event.detail.shouldSwap = false;
    }
  });
})();
