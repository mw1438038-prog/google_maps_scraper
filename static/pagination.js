const RESULTS_PER_PAGE = 15;
const RELOAD_SEARCH_MESSAGE =
  "Search result pages are held only in the current browser session. Run a new search after reloading the page.";

let currentPage = 1;
let currentSearchId = "";
let searchVersion = 0;

document
  .getElementById("keyword")
  .addEventListener("input", invalidateCurrentSearch);

function beginSearchRequest() {
  searchVersion += 1;
  return searchVersion;
}

function isCurrentSearchRequest(version) {
  return version === searchVersion;
}

function setSearchId(searchId) {
  currentSearchId = String(searchId || "").trim();

  const searchIdInput = document.getElementById("searchId");
  if (searchIdInput) {
    searchIdInput.value = currentSearchId;
  }
}

function getSearchId() {
  return currentSearchId;
}

function renderSearchPage(page = 1) {
  const total = currentResults.length;
  const totalPages = Math.ceil(total / RESULTS_PER_PAGE);
  const requestedPage = Number(page);
  currentPage = Number.isInteger(requestedPage)
    ? Math.min(Math.max(requestedPage, 1), Math.max(totalPages, 1))
    : 1;

  const start = (currentPage - 1) * RESULTS_PER_PAGE;
  const visibleResults = currentResults.slice(
    start,
    start + RESULTS_PER_PAGE,
  );

  displayResults(visibleResults, currentPage);

  const resultCount = document.getElementById("resultCount");
  if (resultCount) {
    resultCount.textContent = total
      ? `Showing ${start + 1}–${Math.min(start + visibleResults.length, total)} of ${total}`
      : "0 results";
  }

  const status = document.getElementById("status");
  if (status) {
    status.className = total ? "status success" : "status";
    status.textContent = total
      ? `Showing ${start + 1}–${Math.min(start + visibleResults.length, total)} of ${total} businesses.`
      : "No businesses found.";
  }

  updatePaginationControls(total, totalPages);
}

function updatePaginationControls(total, totalPages) {
  const container = document.getElementById("paginationContainer");
  const numbersContainer = document.getElementById("paginationNumbers");
  const previousButton = document.getElementById("prevPageButton");
  const nextButton = document.getElementById("nextPageButton");

  if (!container || !numbersContainer || !previousButton || !nextButton) {
    return;
  }

  numbersContainer.innerHTML = "";
  container.style.display = totalPages > 1 ? "flex" : "none";
  previousButton.disabled = currentPage <= 1;
  nextButton.disabled = currentPage >= totalPages;
  previousButton.onclick = () => renderSearchPage(currentPage - 1);
  nextButton.onclick = () => renderSearchPage(currentPage + 1);

  for (let pageNumber = 1; pageNumber <= totalPages; pageNumber += 1) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pagination-number";
    button.textContent = pageNumber;
    button.setAttribute("aria-label", `Page ${pageNumber}`);
    button.setAttribute(
      "aria-current",
      pageNumber === currentPage ? "page" : "false",
    );

    if (pageNumber === currentPage) {
      button.classList.add("active");
    }

    button.onclick = () => renderSearchPage(pageNumber);
    numbersContainer.appendChild(button);
  }
}

function resetPagination() {
  currentPage = 1;
  currentSearchId = "";

  const searchIdInput = document.getElementById("searchId");
  if (searchIdInput) {
    searchIdInput.value = "";
  }

  const container = document.getElementById("paginationContainer");
  const numbersContainer = document.getElementById("paginationNumbers");
  const previousButton = document.getElementById("prevPageButton");
  const nextButton = document.getElementById("nextPageButton");

  if (container) {
    container.style.display = "none";
  }
  if (numbersContainer) {
    numbersContainer.innerHTML = "";
  }
  if (previousButton) {
    previousButton.disabled = true;
  }
  if (nextButton) {
    nextButton.disabled = true;
  }
}

function clearSearchResults(message = RELOAD_SEARCH_MESSAGE) {
  currentResults = [];
  resetPagination();

  const csvButton = document.getElementById("csvButton");
  const excelButton = document.getElementById("excelButton");
  if (csvButton) {
    csvButton.disabled = true;
  }
  if (excelButton) {
    excelButton.disabled = true;
  }

  const resultCount = document.getElementById("resultCount");
  if (resultCount) {
    resultCount.textContent = "0 results";
  }

  const resultsBody = document.getElementById("resultsBody");
  if (resultsBody) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 15;
    cell.className = "no-results";
    cell.textContent = message;
    row.appendChild(cell);
    resultsBody.replaceChildren(row);
  }

  const status = document.getElementById("status");
  if (status) {
    status.className = "status";
    status.textContent = message;
  }
}

function invalidateCurrentSearch() {
  searchVersion += 1;

  const searchButton = document.getElementById("searchButton");
  if (searchButton) {
    searchButton.disabled = false;
    searchButton.textContent = "🔍 Search Google Maps";
  }

  if (!currentResults.length && !currentSearchId) {
    resetPagination();
    return;
  }

  clearSearchResults("Search criteria changed. Run a new search to view results.");
}
