/*
 * Restate each timestamp's tooltip in the browser's timezone.
 *
 * The server already renders a title in the viewer's OTIS profile timezone,
 * so with JavaScript off the tooltip is still there and still correct; this
 * only ever rewrites a title that exists.
 */

function otisLocalizeTimestamp(element) {
  const date = new Date(element.dateTime);
  if (Number.isNaN(date.getTime())) {
    return;
  }
  element.title = date.toLocaleString(undefined, {
    dateStyle: "full",
    timeStyle: "long",
  });
}

document.addEventListener("DOMContentLoaded", function () {
  document
    .querySelectorAll("time[datetime][title]")
    .forEach(otisLocalizeTimestamp);
});
