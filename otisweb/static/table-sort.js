/*
 * Click-to-sort table columns.
 *
 * Any <table class="otis-sortable"> with a <thead> and a <tbody> is picked up
 * automatically; no per-page setup is needed. A header opts out of sorting
 * with data-sort="none", which is what the emoji "Actions" columns use.
 *
 * Clicking a header cycles it ascending -> descending -> back to the order the
 * server rendered, which is usually meaningful (newest first, OTIS unit order,
 * leaderboard rank) and is otherwise unreachable without a reload.
 *
 * Sort state lives in aria-sort: otis.css draws the arrow from it, and screen
 * readers announce it.
 */

/* Leading number in a cell, so that "1st" sorts as 1 and "+1.23" as 1.23. */
const OTIS_SORT_NUMBER = /^[+-]?(?:\d[\d,]*)?(?:\.\d+)?/;

function otisSortValue(text) {
  const match = OTIS_SORT_NUMBER.exec(text);
  if (match === null || /\d/.test(match[0]) === false) {
    return Number.NaN;
  }
  return Number.parseFloat(match[0].replace(/,/g, ""));
}

function otisSortTable(table, headers, th, index, original) {
  const body = table.tBodies[0];
  const textOf = (row) => (row.cells[index]?.textContent ?? "").trim();

  /* none -> ascending -> descending -> none. */
  const previous = th.getAttribute("aria-sort");
  const next =
    previous === "none"
      ? "ascending"
      : previous === "ascending"
        ? "descending"
        : "none";
  headers.forEach((other) => other.setAttribute("aria-sort", "none"));
  th.setAttribute("aria-sort", next);
  if (next === "none") {
    body.append(...original);
    return;
  }

  const rows = Array.from(body.rows);
  const filled = rows.filter((row) => textOf(row) !== "");
  const blank = rows.filter((row) => textOf(row) === "");

  /* Sort a column numerically only when every non-empty cell in it is a
   * number; otherwise fall back to text, with numeric-aware collation so that
   * "Unit 10" still lands after "Unit 9". */
  const numeric = filled.every(
    (row) => !Number.isNaN(otisSortValue(textOf(row))),
  );
  const compare = numeric
    ? (a, b) => otisSortValue(textOf(a)) - otisSortValue(textOf(b))
    : (a, b) =>
        textOf(a).localeCompare(textOf(b), undefined, {
          numeric: true,
          sensitivity: "base",
        });

  const descending = next === "descending";
  filled.sort((a, b) => (descending ? -compare(a, b) : compare(a, b)));
  /* Rows with nothing in the sorted column stay at the bottom either way. */
  body.append(...filled, ...blank);
}

function otisMakeSortable(table) {
  const head = table.tHead;
  if (head === null || head.rows.length === 0 || table.tBodies.length === 0) {
    return;
  }
  const headers = Array.from(head.rows[head.rows.length - 1].cells).filter(
    (th) => th.dataset.sort !== "none",
  );
  /* Snapshot before any sorting, so the third click can put it all back. */
  const original = Array.from(table.tBodies[0].rows);
  headers.forEach((th) => {
    const index = th.cellIndex;
    th.tabIndex = 0;
    th.setAttribute("role", "button");
    th.setAttribute("aria-sort", "none");
    th.addEventListener("click", () =>
      otisSortTable(table, headers, th, index, original),
    );
    th.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        otisSortTable(table, headers, th, index, original);
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("table.otis-sortable").forEach(otisMakeSortable);
});
