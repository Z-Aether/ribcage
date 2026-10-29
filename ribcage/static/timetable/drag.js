// Dragging a box along the admin's track: the box follows the pointer, the server answers each new snapped value with the track it
// would leave, and the release saves through the same call. The engine is the server's alone; this file only snaps and paints (#22, #139).
{
  const GRID = 5;
  // Within this many minutes of a neighbour's edge, the box lands flush against it.
  const NEAR = 6;
  // Pixels the pointer must travel before a press is a drag and no longer a click that selects.
  const SLOP = 4;
  const region = () => document.getElementById("track-region");
  const form = () => region().querySelector("form.track-move");

  let drag = null;
  let suppressClick = false;

  const snap = (raw, d) => {
    let best = Math.round(raw / GRID) * GRID;
    let distance = NEAR;
    // Under a push mode the grid alone: flush-to-neighbour fought the push (#22, #140).
    for (const other of d.pushes ? [] : d.others) {
      const end = other.start + other.length;
      if (Math.abs(raw - end) < distance) {
        distance = Math.abs(raw - end);
        best = end;
      }
      if (Math.abs(raw + d.length - other.start) < distance) {
        distance = Math.abs(raw + d.length - other.start);
        best = other.start - d.length;
      }
    }
    // Held inside the locked scale, which the track keeps until the release refits it.
    const low = Math.ceil(d.scale.start / GRID) * GRID;
    const high = Math.floor((d.scale.start + d.scale.length - d.length) / GRID) * GRID;
    return high < low ? best : Math.min(Math.max(best, low), high);
  };

  const ask = async (url, fields) => {
    const body = new FormData(form());
    for (const [name, value] of Object.entries(fields)) body.set(name, value);
    // Marked as htmx's, so a box gone since answers HX-Redirect and not a redirect that fetch would follow (#78).
    const response = await fetch(url, { method: "POST", body, headers: { "HX-Request": "true" }, credentials: "same-origin" });
    const redirect = response.headers.get("HX-Redirect");
    if (redirect) return { redirect };
    if (!response.ok || response.redirected) return { redirect: location.href };
    return { html: await response.text() };
  };

  // Show the answer with the dragged box left alone: its place is the pointer's, not the server's.
  const show = (html, held) => {
    const newer = new DOMParser().parseFromString(html, "text/html");
    const answered = held && newer.querySelector(`[data-box="${held.dataset.box}"]`);
    Idiomorph.morph(region(), html, {
      morphStyle: "outerHTML",
      callbacks: { beforeNodeMorphed: (old) => old !== held },
    });
    // The panel beside the track shows the selected box's end as the preview has it (#140).
    const span = region().dataset.selectedSpan;
    const starts = document.querySelector(".box-panel [data-box-span]");
    if (span && starts) starts.textContent = span;
    if (!answered) return;
    // What the server says of the held box: the row it sits in, whether it overlaps, and its times as of that answer.
    held.style.setProperty("--lane", answered.style.getPropertyValue("--lane"));
    const box = held.querySelector(".box");
    const said = answered.querySelector(".box");
    box.className = said.className;
    box.querySelector(".box__times").textContent = said.querySelector(".box__times").textContent;
  };

  const preview = (d, start) => {
    d.lastStart = start;
    const seq = ++d.sent;
    ask(form().dataset.preview, { box: d.key, start, scale_start: d.scale.start, scale_length: d.scale.length }).then((answer) => {
      if (answer.redirect) return location.assign(answer.redirect);
      // Any answer newer than the one on screen is shown, not only the latest: strict latest-wins froze the neighbours while the pointer outran the round trip (#22).
      if (drag !== d || d.cancelled || seq <= d.shown) return;
      d.shown = seq;
      show(answer.html, d.slot);
    });
  };

  addEventListener("pointerdown", (event) => {
    const slot = event.target.closest?.("#track-region .track__slot");
    if (!slot || event.button !== 0 || event.pointerType === "touch" || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const track = slot.closest(".track");
    const width = track.querySelector(".track__lanes").getBoundingClientRect().width;
    const scale = { start: Number(track.dataset.scaleStart), length: Number(track.dataset.scaleLength) };
    drag = {
      slot,
      key: slot.dataset.box,
      x0: event.clientX,
      start0: Number(slot.dataset.start),
      length: Number(slot.dataset.length),
      scale,
      minutesPerPixel: scale.length / width,
      others: [...track.querySelectorAll(".track__slot")]
        .filter((other) => other !== slot)
        .map((other) => ({ start: Number(other.dataset.start), length: Number(other.dataset.length) })),
      pushes: form().elements.mode.value !== "none",
      moved: false,
      cancelled: false,
      sent: 0,
      shown: 0,
      lastStart: null,
      start: null,
    };
  });

  addEventListener("pointermove", (event) => {
    const d = drag;
    if (!d || d.cancelled) return;
    const travelled = event.clientX - d.x0;
    if (!d.moved && Math.abs(travelled) < SLOP) return;
    if (!d.moved) {
      d.moved = true;
      d.slot.classList.add("is-dragging");
      d.slot.setPointerCapture(event.pointerId);
    }
    d.start = snap(d.start0 + travelled * d.minutesPerPixel, d);
    d.slot.style.setProperty("--at", `${((d.start - d.scale.start) / d.scale.length) * 100}%`);
    if (d.start !== d.lastStart) preview(d, d.start);
  });

  addEventListener("pointerup", () => {
    const d = drag;
    if (!d) return;
    drag = null;
    // The click that ends a drag would select and navigate, racing the save, so it is not a click.
    if (d.moved) {
      suppressClick = true;
      setTimeout(() => (suppressClick = false));
    }
    if (!d.moved || d.cancelled) return;
    const saving = form();
    saving.elements.box.value = d.key;
    saving.elements.start.value = d.start;
    saving.requestSubmit();
  });

  // Escape ends a drag, and so does the system taking the pointer away.
  const cancel = () => {
    const d = drag;
    if (!d || !d.moved || d.cancelled) return;
    d.cancelled = true;
    d.slot.classList.remove("is-dragging");
    // Asking for the box's own start puts the track back as stored, refitted, with nothing written.
    ask(form().dataset.preview, { box: d.key, start: d.start0 }).then((answer) => {
      if (answer.redirect) return location.assign(answer.redirect);
      show(answer.html, null);
    });
  };
  addEventListener("keydown", (event) => event.key === "Escape" && cancel());
  addEventListener("pointercancel", cancel);

  addEventListener(
    "click",
    (event) => {
      if (!suppressClick) return;
      event.preventDefault();
      event.stopPropagation();
    },
    true,
  );
  // A poster or link dragged natively would start the browser's own drag and take the pointer events.
  addEventListener("dragstart", (event) => event.target.closest?.("#track-region") && event.preventDefault());
}
