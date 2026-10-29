// Dragging a box along the admin's track: the box follows the pointer, the server answers each new snapped value with the track it
// would leave, and the release saves through the same call. The engine is the server's alone; this file only snaps and paints (#22, #139).
// A candidate picked up from the list is the same drag with no box yet: over the track it previews an insert, and a drop there places it (#144).
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

  // A handle's new length: its end flush with a neighbour's start when that is whole 5-minute steps long, else the grid; never under the smallest (#22, #143).
  const snapLength = (raw, d) => {
    let best = Math.round(raw / GRID) * GRID;
    let distance = NEAR;
    for (const other of d.pushes ? [] : d.others) {
      const flush = other.start - d.start0;
      if (flush % GRID === 0 && Math.abs(raw - flush) < distance) {
        distance = Math.abs(raw - flush);
        best = flush;
      }
    }
    // Held inside the locked scale, which the track keeps until the release refits it.
    const reach = Math.floor((d.scale.start + d.scale.length - d.start0) / GRID) * GRID;
    return Math.max(GRID, Math.min(best, Math.max(reach, GRID)));
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
    box.querySelector(".box__length").textContent = said.querySelector(".box__length").textContent;
  };

  const preview = (d, value) => {
    d.lastValue = value;
    const seq = ++d.sent;
    // A handle names the new length, a drag the new start; a candidate names its film, or with no start, asks for the track as stored.
    let named = d.resizing ? { box: d.key, length: value } : { box: d.key, start: value };
    if (d.film) named = value === null ? { box: d.rest.key, start: d.rest.start } : { suggestion: d.film, start: value };
    ask(form().dataset.preview, { ...named, scale_start: d.scale.start, scale_length: d.scale.length }).then((answer) => {
      if (answer.redirect) return location.assign(answer.redirect);
      // Any answer newer than the one on screen is shown, not only the latest: strict latest-wins froze the neighbours while the pointer outran the round trip (#22).
      if (drag !== d || d.cancelled || seq <= d.shown) return;
      d.shown = seq;
      show(answer.html, d.slot ?? null);
      // A selected box's panel shows the length it would have.
      const field = d.resizing && document.querySelector(".box-panel #box-length");
      if (field && field.form.elements.box.value === d.key) field.value = d.length;
    });
  };

  addEventListener("pointerdown", (event) => {
    // An armed preview is inert: its times are not the stored ones an edit would run on (#145).
    if (region()?.hasAttribute("data-armed")) return;
    const slot = event.target.closest?.("#track-region .track__slot");
    const resizing = !!event.target.closest?.(".track__handle");
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
      length0: Number(slot.dataset.length),
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
      resizing,
      lastValue: null,
      start: null,
    };
  });

  // A candidate row, picked up: nothing is on the track until the pointer is over it (#144).
  addEventListener("pointerdown", (event) => {
    if (region()?.hasAttribute("data-armed")) return;
    const row = event.target.closest?.("[data-drag-film]");
    if (!row || !region() || event.button !== 0 || event.pointerType === "touch" || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (event.target.closest("form, a, button")) return;
    const track = region().querySelector(".track");
    const slots = [...track.querySelectorAll(".track__slot")];
    drag = {
      film: row.dataset.dragFilm,
      row,
      x0: event.clientX,
      y0: event.clientY,
      length: Number(row.dataset.length),
      // Widened by the film's length on the right, so a drop after the last box fits; posted so the server draws this scale (#144).
      scale: { start: Number(track.dataset.scaleStart), length: Number(track.dataset.scaleLength) + Number(row.dataset.length) },
      others: slots.map((other) => ({ start: Number(other.dataset.start), length: Number(other.dataset.length) })),
      // Any stored box, to ask for the track as stored when the pointer leaves it.
      rest: { key: slots[0].dataset.box, start: Number(slots[0].dataset.start) },
      pushes: form().elements.mode.value !== "none",
      moved: false,
      cancelled: false,
      over: false,
      sent: 0,
      shown: 0,
      lastValue: null,
      start: null,
      chip: null,
    };
  });

  const overTrack = (event) => {
    const lanes = region().querySelector(".track__lanes");
    const rect = lanes.getBoundingClientRect();
    const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top - 24 && event.clientY <= rect.bottom + 24;
    return inside ? rect : null;
  };

  const carryFilm = (event, d) => {
    if (!d.moved && Math.hypot(event.clientX - d.x0, event.clientY - d.y0) < SLOP) return;
    if (!d.moved) {
      d.moved = true;
      d.row.classList.add("is-dragging");
      d.row.setPointerCapture(event.pointerId);
      d.chip = document.createElement("div");
      d.chip.className = "drag-chip";
      d.chip.textContent = `${d.row.querySelector(".candidate__title").textContent} · ${d.length} min`;
      document.body.append(d.chip);
    }
    d.chip.style.left = `${event.clientX}px`;
    d.chip.style.top = `${event.clientY}px`;
    const rect = overTrack(event);
    d.chip.hidden = !!rect;
    if (!rect) {
      // Back off the track: it shows as stored again, and a drop here saves nothing.
      if (d.over) {
        d.over = false;
        d.start = null;
        preview(d, null);
      }
      return;
    }
    d.over = true;
    // The box's middle is under the pointer, read against the scale the track is drawn in now: the first answer widens it.
    const shown = region().querySelector(".track");
    const drawn = { start: Number(shown.dataset.scaleStart), length: Number(shown.dataset.scaleLength) };
    const raw = drawn.start + ((event.clientX - rect.left) / rect.width) * drawn.length - d.length / 2;
    d.start = snap(raw, d);
    if (d.start !== d.lastValue) preview(d, d.start);
  };

  addEventListener("pointermove", (event) => {
    const d = drag;
    if (!d || d.cancelled) return;
    if (d.film) return carryFilm(event, d);
    const travelled = event.clientX - d.x0;
    if (!d.moved && Math.abs(travelled) < SLOP) return;
    if (!d.moved) {
      d.moved = true;
      d.slot.classList.add("is-dragging");
      d.slot.setPointerCapture(event.pointerId);
    }
    if (d.resizing) {
      d.length = snapLength(d.length0 + travelled * d.minutesPerPixel, d);
      d.slot.style.setProperty("--span", `${(d.length / d.scale.length) * 100}%`);
      if (d.length !== d.lastValue) preview(d, d.length);
      return;
    }
    d.start = snap(d.start0 + travelled * d.minutesPerPixel, d);
    d.slot.style.setProperty("--at", `${((d.start - d.scale.start) / d.scale.length) * 100}%`);
    if (d.start !== d.lastValue) preview(d, d.start);
  });

  const putDown = (d) => {
    d.row.classList.remove("is-dragging");
    d.chip?.remove();
  };

  const dropFilm = (d) => {
    putDown(d);
    if (!d.moved || d.cancelled) return;
    if (d.over && d.start !== null) {
      const placing = region().querySelector("form.track-place");
      placing.querySelector("[name=suggestion]").value = d.film;
      placing.querySelector("[name=start]").value = d.start;
      return placing.requestSubmit();
    }
    // Dropped anywhere else: nothing is saved, and an answer still in flight must not leave the insert showing.
    if (d.sent) ask(form().dataset.preview, { box: d.rest.key, start: d.rest.start }).then((answer) => (answer.redirect ? location.assign(answer.redirect) : show(answer.html, null)));
  };

  addEventListener("pointerup", () => {
    const d = drag;
    if (!d) return;
    drag = null;
    // The click that ends a drag would select and navigate, racing the save, so it is not a click.
    if (d.moved) {
      suppressClick = true;
      setTimeout(() => (suppressClick = false));
    }
    if (d.film) return dropFilm(d);
    if (!d.moved || d.cancelled) return;
    // A handle saves through its own form, whose route is the labelled box's one write of a length (#143).
    const saving = d.resizing ? region().querySelector("form.track-resize") : form();
    saving.elements.box.value = d.key;
    // By name: `elements.length` is the collection's own count.
    saving.querySelector(d.resizing ? "[name=length]" : "[name=start]").value = d.resizing ? d.length : d.start;
    saving.requestSubmit();
  });

  // Escape ends a drag, and so does the system taking the pointer away.
  const cancel = () => {
    const d = drag;
    if (!d || !d.moved || d.cancelled) return;
    d.cancelled = true;
    if (d.film) {
      putDown(d);
      return ask(form().dataset.preview, { box: d.rest.key, start: d.rest.start }).then((answer) => (answer.redirect ? location.assign(answer.redirect) : show(answer.html, null)));
    }
    d.slot.classList.remove("is-dragging");
    // Asking for the box's own start puts the track back as stored, refitted, with nothing written.
    const field = d.resizing && document.querySelector(".box-panel #box-length");
    if (field && field.form.elements.box.value === d.key) field.value = d.length0;
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
  addEventListener("dragstart", (event) => event.target.closest?.("#track-region, [data-drag-film]") && event.preventDefault());
}
