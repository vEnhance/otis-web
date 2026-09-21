/*
 * Restate each timestamp's tooltip in the browser's timezone.
 *
 * The server already renders a title in the viewer's OTIS profile timezone,
 * so with JavaScript off the tooltip is still there and still correct; this
 * only ever rewrites a title that exists.
 *
 * A Bootstrap tooltip replaces the native one where Bootstrap is loaded: it
 * appears at once rather than after the browser's own delay, and it matches
 * the rest of the page. Otherwise the title attribute keeps the local text.
 */

function otisLocalTime(element) {
  const date = new Date(element.dateTime);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleString(undefined, {
    dateStyle: "full",
    timeStyle: "long",
  });
}

function otisLocalizeTimestamp(element) {
  const text = otisLocalTime(element);
  if (text === null) {
    return;
  }
  element.title = text;
  if (window.bootstrap === undefined) {
    return;
  }
  window.bootstrap.Tooltip.getOrCreateInstance(element, {
    container: "body",
    customClass: "local-time-tooltip",
  });
}

document.addEventListener("DOMContentLoaded", function () {
  document
    .querySelectorAll("time[datetime][title]")
    .forEach(otisLocalizeTimestamp);
});
