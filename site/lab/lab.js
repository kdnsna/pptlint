document.querySelectorAll(".filter").forEach((button) =>
  button.addEventListener("click", () => {
    document
      .querySelectorAll(".filter")
      .forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    const category = button.dataset.category;
    document.querySelectorAll(".case-card").forEach((card) => {
      card.hidden = category !== "全部" && card.dataset.category !== category;
    });
  }),
);
