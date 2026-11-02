/*
 * Upgrade the native title tooltip on prestige stars (see rpg/components/level.html) to a
 * Bootstrap tooltip, which appears at once and matches the rest of the page.
 * Without Bootstrap the title attribute still works on its own.
 */

document.addEventListener("DOMContentLoaded", function () {
  if (window.bootstrap === undefined) {
    return;
  }
  document
    .querySelectorAll(".otis-prestige[title]")
    .forEach(function (element) {
      window.bootstrap.Tooltip.getOrCreateInstance(element, {
        container: "body",
        customClass: "otis-prestige-tooltip",
      });
    });
});
