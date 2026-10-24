// The bat beside the wordmark takes off at random, 12 to 30 s apart, rather than on a beat (#99).
// It stays put under reduced motion, in a hidden tab, and on the admin skin.
const BAT_SOONEST_MS = 12000;
const BAT_LATEST_MS = 30000;
const batStillness = window.matchMedia("(prefers-reduced-motion: reduce)");

function batTakesOffLater() {
  setTimeout(batTakesOff, BAT_SOONEST_MS + Math.random() * (BAT_LATEST_MS - BAT_SOONEST_MS));
}

function batTakesOff() {
  if (!batStillness.matches && !document.hidden) {
    document.querySelectorAll(".wordmark").forEach((wordmark) => {
      if (wordmark.closest("[data-skin]")?.dataset.skin !== "admin") wordmark.classList.add("is-flying");
    });
  }
  batTakesOffLater();
}

// Landed, or stilled mid-flight, the bat roosts until the next take-off.
for (const ending of ["animationend", "animationcancel"]) {
  document.addEventListener(ending, (event) => {
    if (event.animationName === "bat-flight") event.target.classList.remove("is-flying");
  });
}

batTakesOffLater();
