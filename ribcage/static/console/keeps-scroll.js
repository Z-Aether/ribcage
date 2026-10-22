// A link or form in a data-keeps-scroll region opens its target where the tab was, so Cancel and a reset's password come up in view (#85).
{
  const key = (path) => `kept-scroll:${path}`;
  // An entry older than this is from a navigation that never landed, so a later visit ignores it (#85).
  const freshFor = 10_000;
  const keep = (address) => sessionStorage.setItem(key(new URL(address).pathname), JSON.stringify({ y: scrollY, at: Date.now() }));
  addEventListener("click", (event) => {
    const link = event.target.closest("[data-keeps-scroll] a[href]");
    if (link && !event.defaultPrevented && !(event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)) keep(link.href);
  });
  // Remove and the phase move redirect elsewhere, so the key they leave goes stale unread (#85).
  addEventListener("submit", (event) => {
    const form = event.target.closest("[data-keeps-scroll] form");
    if (form && !event.defaultPrevented) keep(form.action);
  });
  const kept = JSON.parse(sessionStorage.getItem(key(location.pathname)));
  sessionStorage.removeItem(key(location.pathname));
  if (kept && Date.now() - kept.at < freshFor) scrollTo(0, kept.y);
}
