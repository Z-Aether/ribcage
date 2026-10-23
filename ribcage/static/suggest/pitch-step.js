// The pitch step's runtime pencil opens the box in place of the line, in the page alone: the box goes with Add (#21, #93).
document.addEventListener("click", (event) => {
  const pencil = event.target.closest("[data-pitch-step] [data-runtime-pencil]");
  if (!pencil) return;
  event.preventDefault();
  const line = pencil.closest("[data-runtime]");
  line.classList.add("is-editing");
  pencil.closest(".pitch-step__runtime-line").hidden = true;
  const field = line.querySelector(".runtime__field");
  field.hidden = false;
  const box = field.querySelector("input");
  box.focus();
  box.select();
});

// Add stays disabled until every box it needs holds more than blanks; the server still refuses a post that slips past (the dev, 2026-10-23).
function settleAdd(step) {
  const add = step.querySelector("[data-add-needs]");
  if (!add) return;
  const needs = add.dataset.addNeeds.split(" ");
  add.disabled = needs.some((name) => !step.elements[name]?.value.trim());
}

document.addEventListener("input", (event) => {
  const step = event.target.closest("[data-pitch-step]");
  if (step) settleAdd(step);
});

// A step swapped in, fresh or refused, starts settled.
document.addEventListener("htmx:load", (event) => {
  const swapped = event.detail.elt;
  if (!(swapped instanceof Element)) return;
  const steps = swapped.matches("[data-pitch-step]") ? [swapped] : swapped.querySelectorAll("[data-pitch-step]");
  steps.forEach(settleAdd);
});
