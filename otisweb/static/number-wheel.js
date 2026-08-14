/*
 * Turning the mouse wheel over a focused <input type="number"> can step its
 * value, silently rewriting an answer that was just typed. Firefox did this
 * unconditionally until it was removed in Firefox 130; Chrome and Safari do it
 * only when a non-passive "wheel" listener is registered on the input or on
 * one of its ancestors, which any jQuery plugin can do by accident.
 *
 * Dropping focus when the wheel turns cancels the step, since the value only
 * moves while the input is focused. The wheel listener lives on the input and
 * only while it is focused, so no handler runs on the vast majority of wheel
 * events; "focusin" fires rarely enough that watching it costs nothing.
 *
 * The listener must stay passive: a non-passive one is itself the opt-in that
 * turns this behavior on in Chrome and Safari.
 */
function blurOnWheel(event) {
  event.currentTarget.blur();
}

function isNumberInput(el) {
  return el instanceof HTMLInputElement && el.type === "number";
}

document.addEventListener("focusin", function (event) {
  if (isNumberInput(event.target)) {
    event.target.addEventListener("wheel", blurOnWheel, { passive: true });
  }
});

document.addEventListener("focusout", function (event) {
  if (isNumberInput(event.target)) {
    event.target.removeEventListener("wheel", blurOnWheel);
  }
});
