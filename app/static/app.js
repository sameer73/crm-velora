function bindLines(root) {
  root.querySelectorAll("select[name=item_id]").forEach((sel) => {
    if (sel.dataset.bound) return;
    sel.dataset.bound = "1";
    sel.addEventListener("change", () => {
      const price = sel.selectedOptions[0]?.dataset.price;
      const input = sel.closest(".line")?.querySelector("[data-money]");
      if (input && price && !input.value) input.value = price;
    });
  });
  root.querySelectorAll(".remove-line").forEach((btn) => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", () => {
      const box = btn.closest(".lines");
      if (box && box.querySelectorAll(".line").length <= 1) return;
      btn.closest(".line")?.remove();
    });
  });
}

document.querySelectorAll("[data-add]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const tmpl = document.querySelector(btn.dataset.add);
    const target = document.querySelector(btn.dataset.target);
    if (!tmpl || !target) return;
    target.appendChild(tmpl.content.cloneNode(true));
    bindLines(target);
  });
});

document.querySelectorAll(".lines").forEach((el) => bindLines(el));
