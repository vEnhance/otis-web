/*
 * Searchable <select> dropdowns, backed by Tom Select.
 *
 * This replaces the Chosen plugin, which was the last thing on the site that
 * needed jQuery. Two behavior notes carried over from that migration:
 *
 * Chosen refused to run on phones (harvesthq/chosen#1388), so any page that
 * needed a picker on mobile had to ship a separate plain-text fallback. Tom
 * Select works on touch devices, so those fallbacks are gone.
 *
 * Chosen's "search_contains" has no equivalent here because it is the default:
 * Tom Select matches anywhere in an option's label, not just at the start.
 */

/**
 * Upgrade every <select> matching `selector` into a searchable dropdown.
 *
 * Options:
 *   placeholder - text shown while nothing is selected.
 *   width       - CSS width for the widget, e.g. "90%". Defaults to whatever
 *                 the surrounding stylesheet gives the original <select>.
 *   maxOptions  - how many rows the dropdown renders at once (default 500).
 *                 Only the display is capped; searching still sees every
 *                 option, which is what keeps the ARCH problem picker quick.
 */
function otisSelect(selector, options = {}) {
  document.querySelectorAll(selector).forEach(function (select) {
    /* Bail on anything already upgraded: Tom Select hangs its instance off the
     * element, and initializing twice detaches the first widget's listeners. */
    if (!(select instanceof HTMLSelectElement) || select.tomselect) {
      return;
    }
    const settings = {
      /* Django renders an empty choice for optional fields; without this it is
       * hidden, and a value once picked could never be cleared again. */
      allowEmptyOption: true,
      maxOptions: options.maxOptions ?? 500,
    };
    if (options.placeholder !== undefined) {
      settings.placeholder = options.placeholder;
    }
    if (select.multiple) {
      /* Chosen put an X on each chip; remove_button is the equivalent. */
      settings.plugins = ["remove_button"];
    }
    const instance = new TomSelect(select, settings);
    if (options.width !== undefined) {
      instance.wrapper.style.width = options.width;
    }
  });
}
