// Any <tr data-href="..."> becomes clickable and navigates to that URL.
// Using event delegation on the table body so this works for any page
// that renders rows this way, without needing a separate listener per row.
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("tr.clickable-row[data-href]").forEach(function (row) {
    row.addEventListener("click", function () {
      window.location = row.dataset.href;
    });
  });
});
