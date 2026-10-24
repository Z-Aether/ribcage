// A link or form in a data-keeps-scroll region opens its target where the tab was, so Cancel and a reset's password come up in view (#85).
{
  const key = (path) => `kept-scroll:${path}`;
  // An entry older than this is from a navigation that never landed, so a later visit ignores it (#85).
  const freshFor = 10_000;
  const regions = () => [...document.querySelectorAll("[data-keeps-scroll]")];
  // A row marked data-keeps-place comes back at the same height on screen, though a card open above it closed; if it left
  // the filter, the row after it takes its place (#96).
  const places = (element) => {
    const all = [...document.querySelectorAll("[data-keeps-place]")];
    const at = all.indexOf(element.closest("[data-keeps-place]"));
    return at < 0 ? [] : all.slice(at, at + 2).map((place) => ({ name: place.dataset.keepsPlace, top: place.getBoundingClientRect().top }));
  };
  const keep = (address, element) => {
    const region = element.closest("[data-keeps-scroll]");
    const kept = { y: scrollY, at: Date.now(), region: regions().indexOf(region), x: region.scrollLeft, places: places(element) };
    sessionStorage.setItem(key(new URL(address, location.href).pathname), JSON.stringify(kept));
  };
  addEventListener("click", (event) => {
    const link = event.target.closest("[data-keeps-scroll] a[href]");
    if (link && !event.defaultPrevented && !(event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)) keep(link.href, link);
  });
  // Remove and the phase move redirect elsewhere, so the key they leave goes stale unread (#85);
  // a form that redirects back names the page it lands on in data-lands-on, as approve and drop do (#96).
  addEventListener("submit", (event) => {
    const form = event.target.closest("[data-keeps-scroll] form");
    if (form && !event.defaultPrevented) keep(form.dataset.landsOn ?? form.action, form);
  });
  const kept = JSON.parse(sessionStorage.getItem(key(location.pathname)));
  sessionStorage.removeItem(key(location.pathname));
  if (kept && Date.now() - kept.at < freshFor) {
    // A ledger wider than a phone keeps its sideways scroll, so the acts stay in view decision after decision (#96).
    const region = regions()[kept.region];
    if (region) region.scrollLeft = kept.x ?? 0;
    scrollTo(0, kept.y);
    const place = (kept.places ?? []).find(({ name }) => document.querySelector(`[data-keeps-place="${CSS.escape(name)}"]`));
    if (place) scrollBy(0, document.querySelector(`[data-keeps-place="${CSS.escape(place.name)}"]`).getBoundingClientRect().top - place.top);
  }
}
