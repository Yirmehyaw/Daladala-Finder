// Small page helpers (no libraries needed)
document.addEventListener("DOMContentLoaded", () => {
  // Swap "From" and "To" in the search form
  document.querySelectorAll("[data-swap]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const form = btn.closest("form");
      const a = form.querySelector('[name="start"]');
      const b = form.querySelector('[name="destination"]');
      [a.value, b.value] = [b.value, a.value];
      btn.classList.remove("spin");
      void btn.offsetWidth;            // restart the animation
      btn.classList.add("spin");
    });
  });

  // Filter a list of cards as you type (All routes page)
  document.querySelectorAll("[data-filter]").forEach((input) => {
    const cards = document.querySelectorAll(input.dataset.filter);
    const noMatch = document.querySelector(".no-match");
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      let shown = 0;
      cards.forEach((card) => {
        const match = !q || card.dataset.search.includes(q);
        card.hidden = !match;
        if (match) shown++;
      });
      if (noMatch) noMatch.hidden = shown > 0;
    });
  });
});
