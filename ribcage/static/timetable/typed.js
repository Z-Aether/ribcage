// A labelled box's length, or a film's runtime, typed in its panel is previewed on the track as a drag is: the same server call, which writes nothing.
// Save applies it, and a value left unsaved changes nothing, so an empty or refused one is answered with the stored track (#22, #140).
{
  const field = (event) => event.target.closest?.("form.box-panel__form[data-preview] #box-length, form.box-panel__form[data-preview] #box-runtime");
  let sent = 0;
  let shown = 0;

  // Reset puts TMDB's runtime in the box and previews it as typing does.
  addEventListener("click", (event) => {
    const reset = event.target.closest?.("[data-reset]");
    const input = reset?.form?.elements.runtime;
    if (!input) return;
    input.value = reset.dataset.reset;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });

  addEventListener("input", async (event) => {
    const input = field(event);
    if (!input) return;
    const form = input.form;
    const seq = ++sent;
    const ask = (length) => {
      const body = new FormData();
      body.set("csrfmiddlewaretoken", form.elements.csrfmiddlewaretoken.value);
      body.set("box", form.elements.box.value);
      body.set("mode", form.elements.mode.value);
      body.set("selected", form.elements.box.value);
      body.set(input.name, length);
      return fetch(form.dataset.preview, { method: "POST", body, headers: { "HX-Request": "true" }, credentials: "same-origin" });
    };
    // The server answers a length the save would refuse with the stored track, so one call serves every keystroke.
    const response = await ask(input.value);
    const redirect = response.headers.get("HX-Redirect");
    if (redirect) return location.assign(redirect);
    if (!response.ok || seq <= shown) return;
    shown = seq;
    const region = document.getElementById("track-region");
    Idiomorph.morph(region, await response.text(), { morphStyle: "outerHTML" });
    // The panel sits outside the region, so it takes its end from the previewed slot.
    const span = document.getElementById("track-region").dataset.selectedSpan;
    const starts = form.closest(".box-panel").querySelector("[data-box-span]");
    if (span && starts) starts.textContent = span;
  });
}
