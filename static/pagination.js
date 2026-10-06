// =====================================================
// BACKEND PAGINATION
// 15 RESULTS PER PAGE
//
// NEW SEARCH:
//     /api/search
//
// NEXT / PREVIOUS:
//     /api/search/page
//
// IMPORTANT:
// Google API aur website scraping sirf NEW SEARCH par
// chalegi.
// Pagination cached results use karegi.
// =====================================================

const RESULTS_PER_PAGE = 15;

let currentPage = 1;

let currentSearchId = "";

// =====================================================
// SET SEARCH ID
// =====================================================

function setSearchId(searchId) {
  currentSearchId = String(searchId || "").trim();

  // Save in hidden input if it exists
  const searchIdInput = document.getElementById("searchId");

  if (searchIdInput) {
    searchIdInput.value = currentSearchId;
  }

  console.log("[SEARCH ID SET]", currentSearchId);
}

// =====================================================
// GET SEARCH ID
// =====================================================

function getSearchId() {
  // First try variable
  if (currentSearchId) {
    return currentSearchId;
  }

  // Then try hidden input
  const searchIdInput = document.getElementById("searchId");

  if (searchIdInput && searchIdInput.value) {
    currentSearchId = searchIdInput.value.trim();

    return currentSearchId;
  }

  return "";
}

// =====================================================
// LOAD PAGE
//
// IMPORTANT:
// This function NEVER calls Google Places.
//
// It only calls:
//     /api/search/page
//
// with:
//     search_id
//     page
// =====================================================

async function loadPage(page = 1) {
  try {
    // =================================================
    // GET SEARCH ID
    // =================================================

    const searchId = getSearchId();

    console.log("[PAGINATION] Search ID:", searchId);

    // =================================================
    // CHECK SEARCH ID
    // =================================================

    if (!searchId) {
      alert("Search session not found. Please perform a new search first.");

      return;
    }

    // =================================================
    // PAGE
    // =================================================

    page = Number(page);

    if (!Number.isInteger(page) || page < 1) {
      page = 1;
    }

    // =================================================
    // REQUEST CACHE
    // =================================================

    const response = await fetch("/api/search/page", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        search_id: searchId,

        page: page,
      }),
    });

    // =================================================
    // RESPONSE JSON
    // =================================================

    const data = await response.json();

    console.log("[PAGINATION RESPONSE]", data);

    // =================================================
    // ERROR
    // =================================================

    if (!response.ok || !data.success) {
      throw new Error(data.message || "Unable to load page.");
    }

    // =================================================
    // KEEP SEARCH ID
    // =================================================

    if (data.search_id) {
      setSearchId(data.search_id);
    }

    // =================================================
    // PAGINATION
    // =================================================

    const pagination = data.pagination || {};

    currentPage = Number(pagination.page || page);

    // =================================================
    // RESULTS
    // =================================================

    const results = Array.isArray(data.results) ? data.results : [];

    // =================================================
    // KEEP CURRENT RESULTS
    //
    // Important for export buttons.
    // =================================================

    if (typeof currentResults !== "undefined") {
      currentResults = results;
    }

    // =================================================
    // DISPLAY RESULTS
    // =================================================

    if (typeof displayBackendResults === "function") {
      displayBackendResults(results, currentPage);
    } else if (typeof displayResults === "function") {
      displayResults(results, currentPage);
    }

    // =================================================
    // TOTAL RESULTS
    // =================================================

    const total = Number(pagination.total || 0);

    const totalPages = Number(
      pagination.total_pages ||
        Math.max(1, Math.ceil(total / RESULTS_PER_PAGE)),
    );

    // =================================================
    // RESULT COUNT
    // =================================================

    const resultCount = document.getElementById("resultCount");

    if (resultCount) {
      resultCount.textContent = `${total} results`;
    }

    // =================================================
    // STATUS
    // =================================================

    const status = document.getElementById("status");

    if (status) {
      status.className = "status success";

      status.textContent = `Showing page ${currentPage} of ${totalPages}. ${total} businesses found.`;
    }

    // =================================================
    // PAGINATION UI
    // =================================================

    updateBackendPagination(pagination);
  } catch (error) {
    console.error("[PAGINATION ERROR]", error);

    const status = document.getElementById("status");

    if (status) {
      status.className = "status error";

      status.textContent = error.message || "Unable to load page.";
    }
  }
}

// =====================================================
// UPDATE PAGINATION UI
// =====================================================

function updateBackendPagination(pagination) {
  const container = document.getElementById("paginationContainer");

  const numbersContainer = document.getElementById("paginationNumbers");

  const previousButton = document.getElementById("prevPageButton");

  const nextButton = document.getElementById("nextPageButton");

  // =================================================
  // ELEMENT CHECK
  // =================================================

  if (!container || !numbersContainer || !previousButton || !nextButton) {
    console.error("Pagination HTML elements not found.");

    return;
  }

  // =================================================
  // VALUES
  // =================================================

  const total = Number(pagination.total || 0);

  const totalPages = Number(
    pagination.total_pages || Math.ceil(total / RESULTS_PER_PAGE),
  );

  const page = Number(pagination.page || 1);

  currentPage = page;

  console.log("[PAGINATION UI]", {
    page: page,
    totalPages: totalPages,
    total: total,
  });

  // =================================================
  // ONLY ONE PAGE
  // =================================================

  if (totalPages <= 1) {
    container.style.display = "none";

    numbersContainer.innerHTML = "";

    previousButton.disabled = true;

    nextButton.disabled = true;

    return;
  }

  // =================================================
  // SHOW PAGINATION
  // =================================================

  container.style.display = "flex";

  // =================================================
  // PREVIOUS BUTTON
  // =================================================

  previousButton.disabled = !pagination.has_previous;

  previousButton.onclick = function () {
    if (pagination.has_previous && pagination.previous_page) {
      loadPage(Number(pagination.previous_page));
    }
  };

  // =================================================
  // NEXT BUTTON
  // =================================================

  nextButton.disabled = !pagination.has_next;

  nextButton.onclick = function () {
    if (pagination.has_next && pagination.next_page) {
      loadPage(Number(pagination.next_page));
    }
  };

  // =================================================
  // PAGE NUMBERS
  // =================================================

  numbersContainer.innerHTML = "";

  for (let pageNumber = 1; pageNumber <= totalPages; pageNumber++) {
    const button = document.createElement("button");

    button.type = "button";

    button.className = "pagination-number";

    button.textContent = pageNumber;

    // =================================================
    // ACTIVE PAGE
    // =================================================

    if (pageNumber === page) {
      button.classList.add("active");
    }

    // =================================================
    // PAGE CLICK
    // =================================================

    button.onclick = function () {
      loadPage(pageNumber);
    };

    numbersContainer.appendChild(button);
  }
}

// =====================================================
// RESET PAGINATION
//
// ONLY CALL THIS WHEN USER STARTS A COMPLETELY
// NEW SEARCH.
// =====================================================

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

// =====================================================
// SET CURRENT PAGE
// =====================================================

function setCurrentPage(page) {
  page = Number(page);

  if (Number.isInteger(page) && page >= 1) {
    currentPage = page;
  }
}
