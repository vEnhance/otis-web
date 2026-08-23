/*
 * Searchable <select> dropdowns, backed by Tom Select.
 *
 * Matching is substring-based and needs no opting in: a query hits anywhere in
 * an option's label, not just at the start.
 *
 * Tom Select is loaded from a CDN, so it may not arrive. That is survivable --
 * an un-upgraded <select> is still a working <select>, just without search --
 * but only if we bail early: throwing here would also take out whatever else
 * the calling page put in the same DOMContentLoaded handler.
 */

/**
 * Upgrade every <select> matching `selector` into a searchable dropdown.
 *
 * Options:
 *   placeholder - text shown while nothing is selected. Defaults to the label
 *                 Django gave its empty choice, e.g. "---------".
 *   width       - CSS width for the widget, e.g. "90%". Defaults to whatever
 *                 the surrounding stylesheet gives the original <select>.
 *   maxOptions  - how many rows the dropdown renders at once (default 500).
 *                 Only the display is capped; searching still sees every
 *                 option, which is what keeps the ARCH problem picker quick.
 */
function otisSelect(selector, options = {}) {
  if (typeof TomSelect === "undefined") {
    return;
  }
  document.querySelectorAll(selector).forEach(function (select) {
    /* Bail on anything already upgraded: Tom Select hangs its instance off the
     * element, and initializing twice detaches the first widget's listeners. */
    if (!(select instanceof HTMLSelectElement) || select.tomselect) {
      return;
    }
    const settings = {
      /* Keep Django's empty choice ("---------") out of the option list, as
       * Tom Select reads its label as a real option otherwise. */
      allowEmptyOption: false,
      maxOptions: options.maxOptions ?? 500,
      ...(options.placeholder !== undefined
        ? { placeholder: options.placeholder }
        : {}),
      plugins: [
        /* remove_button puts an X on each selected chip;
         * dropdown_input moves the query into the dropdown */
        ...(select.multiple ? ["remove_button"] : ["dropdown_input"]),
        /* clear_button puts an X on the control */
        ...(select.required ? [] : ["clear_button"]),
      ],
    };
    const instance = new TomSelect(select, settings);
    if (options.width !== undefined) {
      instance.wrapper.style.width = options.width;
    }
  });
}
