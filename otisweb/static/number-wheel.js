/*
 * Browsers treat the mouse wheel as a "step the value" gesture whenever the
 * cursor is over a focused <input type="number">, so scrolling down a page
 * after typing into one silently rewrites the answer that was just entered.
 *
 * Dropping focus when the wheel turns over such an input cancels that
 * behavior: the value change only happens while the input is focused, and the
 * event is left alone otherwise so the page still scrolls as usual.
 */
document.addEventListener(
  "wheel",
  function (event) {
    const el = document.activeElement;
    if (
      el instanceof HTMLInputElement &&
      el.type === "number" &&
      el === event.target
    ) {
      el.blur();
    }
  },
  { capture: true, passive: true },
);
