// Prevent a form from being submitted twice.
//
// A slow response invites an impatient second click, and for anything that
// creates a row or grants something rather than just updating a field, that
// second click means a duplicate: two unit petitions, two job claims, two
// mystery unlocks. Every POST on this site is a "do this once" action, so
// guard them all: the first submit wins, later ones are dropped, and the
// button shows a spinner so a slow response no longer looks like nothing
// happened.
//
// A form that genuinely wants to be submitted repeatedly can opt out with
// data-multi-submit. GET forms (searches, lookups) are safe to repeat and are
// left alone.
//
// This is progressive enhancement: with JavaScript off, nothing here runs and
// every form posts exactly as it did before. Deliberately no jQuery and no
// DOMContentLoaded wrapper, since both listeners attach to objects that
// already exist -- the guard is armed before the first form is parsed, and it
// survives the jQuery CDN being blocked.

(function () {
  function submitButtons(form) {
    return form.querySelectorAll("button[type=submit], input[type=submit]");
  }

  document.addEventListener("submit", function (event) {
    // another handler already cancelled this submit, so there is nothing to
    // guard and locking the form would strand it. This is also why the
    // listener bubbles rather than captures: handlers on the form itself get
    // to run first.
    if (event.defaultPrevented) return;

    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.method.toLowerCase() !== "post") return;
    if (form.hasAttribute("data-multi-submit")) return;

    if (form.dataset.submitting === "1") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "1";

    // disable on the next tick, so the button still contributes its
    // name/value (if any) to the submitted form data
    window.setTimeout(function () {
      submitButtons(form).forEach(function (button) {
        button.disabled = true;
        if (button.tagName !== "BUTTON") return;
        if (button.dataset.originalHtml === undefined) {
          button.dataset.originalHtml = button.innerHTML;
        }
        button.innerHTML =
          '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> ' +
          button.dataset.originalHtml;
      });
    }, 0);
  });

  // the back button can restore the page from the bfcache with the button
  // still disabled, which would leave the form unusable
  window.addEventListener("pageshow", function (event) {
    if (!event.persisted) return;
    document.querySelectorAll("form").forEach(function (form) {
      if (form.dataset.submitting !== "1") return;
      delete form.dataset.submitting;
      submitButtons(form).forEach(function (button) {
        button.disabled = false;
        if (button.dataset.originalHtml !== undefined) {
          button.innerHTML = button.dataset.originalHtml;
        }
      });
    });
  });
})();
