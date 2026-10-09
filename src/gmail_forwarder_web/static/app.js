document.querySelectorAll("[data-busy-form]").forEach((form) => {
  form.addEventListener("submit", () => {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    button.disabled = true;
    button.classList.add("is-busy");
    button.querySelector("span").textContent = "Working…";
  });
});

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = "Copied";
      window.setTimeout(() => { button.textContent = "Copy"; }, 1400);
    } catch {
      button.textContent = "Copy unavailable";
      window.setTimeout(() => { button.textContent = "Copy"; }, 1800);
    }
  });
});

const recipientSelect = document.querySelector("[data-recipient]");
const domainSuffix = document.querySelector("[data-domain-suffix]");
if (recipientSelect && domainSuffix) {
  const updateSuffix = () => {
    const recipient = recipientSelect.value;
    domainSuffix.textContent = recipient.includes("@") ? `@${recipient.split("@").pop()}` : "";
  };
  recipientSelect.addEventListener("change", updateSuffix);
  updateSuffix();
}