// Where the night is, worked out on this phone from each box's start and end instants against its own clock, with no server
// contact (#13, #159). The rule and the words are `timetable.engine.now_playing` and `in_words`; keep the two together.
(function () {
  const TICK_MS = 5000;

  function inWords(minutes) {
    const whole = Math.max(1, Math.ceil(minutes));
    if (whole < 60) return whole + "m";
    if (whole < 24 * 60) {
      const hours = Math.floor(whole / 60);
      const rest = whole % 60;
      return rest ? hours + "h" + String(rest).padStart(2, "0") + "m" : hours + "h";
    }
    const days = Math.floor(whole / (24 * 60));
    return days === 1 ? "1 day" : days + " days";
  }

  function mark(slot, state, status, elapsed) {
    for (const name of ["past", "playing", "next", "later"]) slot.classList.toggle("evening__slot--" + name, name === state);
    slot.style.setProperty("--elapsed", (elapsed * 100).toFixed(3) + "%");
    const line = slot.querySelector("[data-status]");
    if (line && line.textContent !== status) line.textContent = status;
  }

  function refresh() {
    const slots = Array.from(document.querySelectorAll("#evening .evening__slot"));
    const boxes = slots.map((slot) => ({ slot, start: Date.parse(slot.dataset.start), end: Date.parse(slot.dataset.end) }));
    const now = Date.now();
    const playing = boxes.filter((box) => box.start <= now && now < box.end);
    const coming = boxes.filter((box) => box.start > now).map((box) => box.start);
    const soonest = coming.length && !playing.length ? Math.min(...coming) : null;
    for (const box of boxes) {
      if (playing.includes(box)) {
        const left = (box.end - now) / 60000;
        mark(box.slot, "playing", "NOW PLAYING · " + inWords(left) + " left", (now - box.start) / (box.end - box.start));
      } else if (box.end <= now) {
        mark(box.slot, "past", "", 0);
      } else if (box.start === soonest) {
        mark(box.slot, "next", "NEXT · in " + inWords((box.start - now) / 60000), 0);
      } else {
        mark(box.slot, "later", "", 0);
      }
    }
  }

  // Each tick reads the page's boxes afresh, so a region swapped in by a poll is marked on the next tick, or at once on its swap.
  window.Evening = { refresh, inWords };
  document.addEventListener("DOMContentLoaded", refresh);
  document.addEventListener("htmx:afterSettle", refresh);
  setInterval(refresh, TICK_MS);
})();
