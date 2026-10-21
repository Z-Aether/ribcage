// Says as the voter types whether a confirmation field matches the password it names; the server still decides (#72).
document.querySelectorAll("input[data-confirms-password]").forEach((again) => {
  const first = document.getElementById(again.dataset.confirmsPassword);
  if (!first) return;
  const status = document.createElement("p");
  status.className = "password-match";
  status.setAttribute("aria-live", "polite");
  (again.closest("label") ?? again).after(status);

  const messages = { match: "The two passwords match.", differ: "The two passwords differ.", "": "" };
  const show = () => {
    const next = again.value === "" ? "" : again.value === first.value ? "match" : "differ";
    // Rewrite only on a change, so the live region announces each state once.
    if (status.dataset.state === next) return;
    status.dataset.state = next;
    status.textContent = messages[next];
  };
  again.addEventListener("input", show);
  first.addEventListener("input", show);
  show();
});
