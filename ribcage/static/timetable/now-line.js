// Moves the track's now line along its held scale every few seconds, with no server contact (#163). The minute rule is
// `timetable.track.now_line`'s and the evening's now playing: minutes since the anchor instant against Date.now() (#159).
(function () {
  const TICK_MS = 5000;

  function place(line) {
    const track = line.closest(".track");
    const start = Number(track.dataset.scaleStart);
    const length = Number(track.dataset.scaleLength);
    const now = Date.now();
    const at = (((now - Date.parse(line.dataset.anchor)) / 60000 - start) / length) * 100;
    line.hidden = !(at >= 0 && at <= 100);
    if (line.hidden) return;
    line.style.setProperty("--at", at.toFixed(3) + "%");
    line.classList.toggle("is-late", at > Number(line.dataset.lateFrom));
    const label = new Intl.DateTimeFormat("en-GB", { timeZone: line.dataset.zone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(now);
    const text = line.querySelector(".track__now-label");
    if (text.textContent !== label) text.textContent = label;
  }

  // Each tick reads the page's lines afresh, so a track a preview swapped in is moved on the next tick, or at once on its swap.
  function refresh() {
    document.querySelectorAll(".track__now[data-anchor]").forEach(place);
  }

  document.addEventListener("DOMContentLoaded", refresh);
  document.addEventListener("htmx:afterSettle", refresh);
  setInterval(refresh, TICK_MS);
})();
