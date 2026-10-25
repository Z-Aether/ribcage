// A tick can grow or shrink the chips box above the rows, so the page scrolls by however far the clicked row moved and the row stays under the finger (#107).
let held = null;

document.addEventListener("htmx:beforeRequest", (event) => {
  const row = event.target.closest?.(".warnings__topic");
  held = row ? { id: row.id, top: row.getBoundingClientRect().top } : null;
});

document.addEventListener("htmx:afterSettle", () => {
  if (!held) return;
  const row = document.getElementById(held.id);
  if (row) window.scrollBy(0, row.getBoundingClientRect().top - held.top);
  held = null;
});
