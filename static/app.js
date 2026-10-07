// =====================================================
// GLOBAL DATA
// =====================================================

let currentResults = [];

let countries = [];

let cities = [];

let selectedCountry = "";

let selectedCity = "";

// =====================================================
// ELEMENTS
// =====================================================

const countryDropdown = document.getElementById("countryDropdown");

const cityDropdown = document.getElementById("cityDropdown");

const countryTrigger = document.getElementById("countryTrigger");

const cityTrigger = document.getElementById("cityTrigger");

const countryText = document.getElementById("countryText");

const cityText = document.getElementById("cityText");

const countryOptions = document.getElementById("countryOptions");

const cityOptions = document.getElementById("cityOptions");

const countrySearch = document.getElementById("countrySearch");

const citySearch = document.getElementById("citySearch");

// =====================================================
// CLOSE DROPDOWNS
// =====================================================

function closeDropdowns() {
  countryDropdown.classList.remove("open");

  cityDropdown.classList.remove("open");
}

// =====================================================
// COUNTRY DROPDOWN
// =====================================================

countryTrigger.addEventListener("click", function () {
  if (countryTrigger.disabled) {
    return;
  }

  const isOpen = countryDropdown.classList.contains("open");

  closeDropdowns();

  if (!isOpen) {
    countryDropdown.classList.add("open");

    countrySearch.value = "";

    renderCountries();

    setTimeout(function () {
      countrySearch.focus();
    }, 50);
  }
});

// =====================================================
// CITY DROPDOWN
// =====================================================

cityTrigger.addEventListener("click", function () {
  if (cityTrigger.disabled) {
    return;
  }

  const isOpen = cityDropdown.classList.contains("open");

  closeDropdowns();

  if (!isOpen) {
    cityDropdown.classList.add("open");

    citySearch.value = "";

    renderCities();

    setTimeout(function () {
      citySearch.focus();
    }, 50);
  }
});

// =====================================================
// CLICK OUTSIDE
// =====================================================

document.addEventListener("click", function (event) {
  if (
    !countryDropdown.contains(event.target) &&
    !cityDropdown.contains(event.target)
  ) {
    closeDropdowns();
  }
});

// =====================================================
// RENDER COUNTRIES
// =====================================================

function renderCountries(searchValue = "") {
  countryOptions.innerHTML = "";

  const search = searchValue.toLowerCase().trim();

  const filtered = countries.filter(function (country) {
    return country.toLowerCase().includes(search);
  });

  if (!filtered.length) {
    const empty = document.createElement("div");

    empty.className = "select-option disabled";

    empty.textContent = "No countries found.";

    countryOptions.appendChild(empty);

    return;
  }

  filtered.forEach(function (country) {
    const option = document.createElement("div");

    option.className = "select-option";

    if (country === selectedCountry) {
      option.classList.add("selected");
    }

    option.textContent = country;

    option.addEventListener("click", function () {
      selectCountry(country);
    });

    countryOptions.appendChild(option);
  });
}

// =====================================================
// SELECT COUNTRY
// =====================================================

function selectCountry(country) {
  selectedCountry = country;

  selectedCity = "";

  countryText.textContent = country;

  cityText.textContent = "Loading cities...";

  cityTrigger.disabled = true;

  cityTrigger.classList.add("disabled");

  closeDropdowns();

  cities = [];

  cityOptions.innerHTML = "";

  loadCities();

  resetPagination();
}

// =====================================================
// COUNTRY SEARCH
// =====================================================

countrySearch.addEventListener("input", function () {
  renderCountries(countrySearch.value);
});

// =====================================================
// LOAD COUNTRIES
// =====================================================

async function loadCountries() {
  const status = document.getElementById("status");

  try {
    const response = await fetch("/api/countries");

    const contentType = response.headers.get("content-type") || "";

    if (!response.ok) {
      const text = await response.text();

      throw new Error(
        `Countries API failed (${response.status}): ${text.substring(0, 200)}`,
      );
    }

    if (!contentType.includes("application/json")) {
      const text = await response.text();

      throw new Error(
        `Countries API returned non-JSON response: ${text.substring(0, 200)}`,
      );
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.message || "Could not load countries.");
    }

    countries = Array.isArray(data.countries) ? data.countries : [];

    countryText.textContent = "Select Country";

    renderCountries();
  } catch (error) {
    console.error("Countries Error:", error);

    countryText.textContent = "Could not load countries";

    status.className = "status error";

    status.textContent = error.message;
  }
}

// =====================================================
// RENDER CITIES
// =====================================================

function renderCities(searchValue = "") {
  cityOptions.innerHTML = "";

  const search = searchValue.toLowerCase().trim();

  const filtered = cities.filter(function (city) {
    return city.toLowerCase().includes(search);
  });

  if (!filtered.length) {
    const empty = document.createElement("div");

    empty.className = "select-option disabled";

    empty.textContent = "No cities found.";

    cityOptions.appendChild(empty);

    return;
  }

  filtered.forEach(function (city) {
    const option = document.createElement("div");

    option.className = "select-option";

    if (city === selectedCity) {
      option.classList.add("selected");
    }

    option.textContent = city;

    option.addEventListener("click", function () {
      selectCity(city);
    });

    cityOptions.appendChild(option);
  });
}

// =====================================================
// SELECT CITY
// =====================================================

function selectCity(city) {
  selectedCity = city;

  cityText.textContent = city;

  closeDropdowns();

  resetPagination();
}

// =====================================================
// CITY SEARCH
// =====================================================

citySearch.addEventListener("input", function () {
  renderCities(citySearch.value);
});

// =====================================================
// LOAD CITIES
// =====================================================

async function loadCities() {
  const status = document.getElementById("status");

  if (!selectedCountry) {
    cityText.textContent = "Select country first";

    cityTrigger.disabled = true;

    cityTrigger.classList.add("disabled");

    return;
  }

  status.className = "status loading";

  status.textContent = `Loading cities of ${selectedCountry}...`;

  try {
    const response = await fetch("/api/cities", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        country: selectedCountry,
      }),
    });

    const contentType = response.headers.get("content-type") || "";

    if (!response.ok) {
      const text = await response.text();

      throw new Error(
        `Cities API failed (${response.status}): ${text.substring(0, 200)}`,
      );
    }

    if (!contentType.includes("application/json")) {
      const text = await response.text();

      throw new Error(
        `Cities API returned non-JSON response: ${text.substring(0, 200)}`,
      );
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.message || "Could not load cities.");
    }

    cities = Array.isArray(data.cities) ? data.cities : [];

    cityText.textContent = "Select City";

    renderCities();

    if (cities.length > 0) {
      cityTrigger.disabled = false;

      cityTrigger.classList.remove("disabled");

      status.className = "status success";

      status.textContent = `${cities.length} cities loaded for ${selectedCountry}.`;
    } else {
      cityTrigger.disabled = true;

      cityTrigger.classList.add("disabled");

      status.className = "status error";

      status.textContent = `No cities found for ${selectedCountry}.`;
    }
  } catch (error) {
    console.error("Cities Error:", error);

    cities = [];

    cityText.textContent = "Could not load cities";

    cityTrigger.disabled = true;

    cityTrigger.classList.add("disabled");

    status.className = "status error";

    status.textContent = error.message;
  }
}

// =====================================================
// PLAN / USAGE DISPLAY
// =====================================================

function updateUsageDisplay(usage) {
  if (!usage) {
    return;
  }

  const plan = String(usage.plan || "free").toLowerCase();

  const used = Number(usage.used || 0);

  const limit = Number(usage.limit || 0);

  const remaining = Number(usage.remaining || 0);

  // ===================================================
  // ELEMENTS
  // ===================================================

  const badge = document.getElementById("planBadge");

  const planNameElement = document.getElementById("planName");

  const planDescriptionElement = document.getElementById("planDescription");

  const planIcon = document.getElementById("planIcon");

  const usageRemaining = document.getElementById("usageRemaining");

  if (!badge) {
    return;
  }

  // ===================================================
  // PLAN NAME
  // ===================================================

  let displayName = "Free Plan";

  if (plan === "pro") {
    displayName = "Pro Plan";
  } else if (plan === "business") {
    displayName = "Business Plan";
  }

  // ===================================================
  // REMOVE OLD CLASSES
  // ===================================================

  badge.classList.remove(
    "plan-free",
    "plan-pro",
    "plan-business",
    "usage-limit-reached",
  );

  // ===================================================
  // APPLY PLAN CLASS
  // ===================================================

  if (plan === "pro") {
    badge.classList.add("plan-pro");
  } else if (plan === "business") {
    badge.classList.add("plan-business");
  } else {
    badge.classList.add("plan-free");
  }

  // ===================================================
  // PLAN ICON
  // ===================================================

  if (plan === "pro") {
    planIcon.textContent = "★";
  } else if (plan === "business") {
    planIcon.textContent = "♛";
  } else {
    planIcon.textContent = "✓";
  }

  // ===================================================
  // PLAN NAME
  // ===================================================

  planNameElement.textContent = displayName;

  // ===================================================
  // PLAN DESCRIPTION
  // ===================================================

  if (remaining <= 0) {
    planDescriptionElement.textContent = "Monthly search limit reached";
  } else {
    planDescriptionElement.textContent = `${used} of ${limit} searches used`;
  }

  // ===================================================
  // REMAINING SEARCHES
  // ===================================================

  usageRemaining.textContent = remaining;

  // ===================================================
  // LIMIT REACHED
  // ===================================================

  if (remaining <= 0) {
    badge.classList.add("usage-limit-reached");
  }
}

// =====================================================
// LOAD USAGE FROM DATABASE
// =====================================================

async function loadUsage() {
  const badge = document.getElementById("planBadge");

  if (!badge) {
    return;
  }

  try {
    const response = await fetch("/api/usage");

    if (!response.ok) {
      return;
    }

    const data = await response.json();

    if (data.success && data.usage) {
      updateUsageDisplay(data.usage);
    }
  } catch (error) {
    console.error("Usage Error:", error);
  }
}

// =====================================================
// SEARCH PLACES
// =====================================================

async function searchPlaces() {
  const country = selectedCountry;

  const city = selectedCity;

  const keyword = document.getElementById("keyword").value.trim();

  const button = document.getElementById("searchButton");

  const status = document.getElementById("status");

  const resultsBody = document.getElementById("resultsBody");

  const resultCount = document.getElementById("resultCount");

  const csvButton = document.getElementById("csvButton");

  const excelButton = document.getElementById("excelButton");

  // =================================================
  // VALIDATION
  // =================================================

  if (!country) {
    status.className = "status error";

    status.textContent = "Please select a country.";

    return;
  }

  if (!city) {
    status.className = "status error";

    status.textContent = "Please select a city.";

    return;
  }

  if (!keyword) {
    status.className = "status error";

    status.textContent = "Please enter a keyword.";

    return;
  }

  // =================================================
  // NEW SEARCH
  // =================================================

  currentResults = [];

  csvButton.disabled = true;

  excelButton.disabled = true;

  if (typeof resetPagination === "function") {
    resetPagination();
  }

  // =================================================
  // LOADING
  // =================================================

  button.disabled = true;

  button.textContent = "Scraping leads...";

  status.className = "status loading";

  status.textContent = `Searching ${city}, ${country}...`;

  resultsBody.innerHTML = "";

  resultCount.textContent = "Searching...";

  // =================================================
  // SEARCH API
  // =================================================

  try {
    const response = await fetch("/api/search", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        country: country,

        city: city,

        keyword: keyword,

        page: 1,
      }),
    });

    const contentType = response.headers.get("content-type") || "";

    // =============================================
    // ERROR
    // =============================================

    if (!response.ok) {
      if (contentType.includes("application/json")) {
        const error = await response.json();

        // =======================================
        // UPDATE USAGE
        // =======================================

        if (error.usage) {
          updateUsageDisplay(error.usage);
        }

        throw new Error(error.message || "Search failed.");
      }

      const text = await response.text();

      throw new Error(
        `Search failed (${response.status}): ${text.substring(0, 200)}`,
      );
    }

    // =============================================
    // JSON CHECK
    // =============================================

    if (!contentType.includes("application/json")) {
      const text = await response.text();

      throw new Error(
        `Server returned non-JSON response: ${text.substring(0, 200)}`,
      );
    }

    // =============================================
    // RESPONSE
    // =============================================

    const data = await response.json();

    if (!data.success) {
      if (data.usage) {
        updateUsageDisplay(data.usage);
      }

      throw new Error(data.message || "Search failed.");
    }

    // =============================================
    // UPDATE USAGE
    // =============================================

    if (data.usage) {
      updateUsageDisplay(data.usage);
    }

    // =============================================
    // SAVE SEARCH ID
    // =============================================

    if (!data.search_id) {
      throw new Error("Search ID was not returned by server.");
    }

    setSearchId(data.search_id);

    // =============================================
    // BACKEND RESULTS
    // =============================================

    currentResults = Array.isArray(data.results) ? data.results : [];

    // =============================================
    // PAGINATION DATA
    // =============================================

    const pagination = data.pagination || {};

    const current = Number(pagination.page || 1);

    const backendTotal = Number(pagination.total || 0);

    const backendTotalPages = Number(pagination.total_pages || 0);

    const total = backendTotal > 0 ? backendTotal : currentResults.length;

    const totalPages =
      backendTotalPages > 0
        ? backendTotalPages
        : Math.max(1, Math.ceil(total / 15));

    // =============================================
    // DISPLAY RESULTS
    // =============================================

    displayResults(currentResults, current);

    // =============================================
    // RESULT COUNT
    // =============================================

    resultCount.textContent = `${total} results`;

    // =============================================
    // EXPORT BUTTONS
    // =============================================

    if (currentResults.length > 0) {
      csvButton.disabled = false;

      excelButton.disabled = false;
    } else {
      csvButton.disabled = true;

      excelButton.disabled = true;
    }

    // =============================================
    // STATUS
    // =============================================

    status.className = "status success";

    status.textContent = `Showing page ${current} of ${totalPages}. ${total} businesses found.`;

    // =============================================
    // UPDATE PAGINATION
    // =============================================

    updateBackendPagination(pagination);
  } catch (error) {
    console.error("Search Error:", error);

    status.className = "status error";

    status.textContent = error.message || "Search failed.";
  } finally {
    button.disabled = false;

    button.textContent = "🔍 Search Google Maps";
  }
}

// =====================================================
// DISPLAY RESULTS
// =====================================================

function displayResults(results, page = 1) {
  const resultsBody = document.getElementById("resultsBody");

  resultsBody.innerHTML = "";

  // =================================================
  // NO RESULTS
  // =================================================

  if (!results.length) {
    resultsBody.innerHTML = `

      <tr>

        <td
          colspan="14"
          class="no-results"
        >
          No businesses found.
        </td>

      </tr>

    `;

    return;
  }

  // =================================================
  // RESULT NUMBER
  // =================================================

  const startIndex = (page - 1) * 15;

  // =================================================
  // RENDER
  // =================================================

  renderResultRows(results, startIndex);
}

// =====================================================
// CREATE RESULT ROW
// =====================================================

function createResultRow(place, resultNumber) {
  const website = place.website
    ? `

        <a
          href="${escapeHtml(place.website)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          Website
        </a>

      `
    : "-";

  const email = place.email
    ? `

        <a
          href="mailto:${escapeHtml(place.email)}"
        >
          ${escapeHtml(place.email)}
        </a>

      `
    : "-";

  const facebook = place.facebook
    ? `

        <a
          href="${escapeHtml(place.facebook)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          Facebook
        </a>

      `
    : "-";

  const instagram = place.instagram
    ? `

        <a
          href="${escapeHtml(place.instagram)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          Instagram
        </a>

      `
    : "-";

  const linkedin = place.linkedin
    ? `

        <a
          href="${escapeHtml(place.linkedin)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          LinkedIn
        </a>

      `
    : "-";

  const twitter = place.twitter
    ? `

        <a
          href="${escapeHtml(place.twitter)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          Twitter / X
        </a>

      `
    : "-";

  const otherSocial = place.other_social ? escapeHtml(place.other_social) : "-";

  const maps = place.maps_url
    ? `

        <a
          href="${escapeHtml(place.maps_url)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          📍 Open Maps
        </a>

      `
    : "-";

  return `

    <tr>

      <td>
        ${resultNumber}
      </td>


      <td>

        <strong>
          ${escapeHtml(place.name)}
        </strong>

      </td>


      <td>
        ${escapeHtml(place.phone || "-")}
      </td>


      <td>
        ${website}
      </td>


      <td>
        ${email}
      </td>


      <td>
        ${facebook}
      </td>


      <td>
        ${instagram}
      </td>


      <td>
        ${linkedin}
      </td>


      <td>
        ${twitter}
      </td>


      <td>
        ${otherSocial}
      </td>


      <td>
        ${escapeHtml(place.address || "-")}
      </td>


      <td>
        ⭐ ${place.rating || "-"}
      </td>


      <td>
        ${place.reviews || "-"}
      </td>


      <td>
        ${maps}
      </td>

    </tr>

  `;
}

// =====================================================
// RENDER RESULT ROWS
// =====================================================

function renderResultRows(results, startIndex = 0) {
  const resultsBody = document.getElementById("resultsBody");

  results.forEach(function (place, index) {
    const resultNumber = startIndex + index + 1;

    resultsBody.insertAdjacentHTML(
      "beforeend",

      createResultRow(place, resultNumber),
    );
  });
}

// =====================================================
// EXPORT CSV
// =====================================================

async function exportCSV() {
  if (!currentResults.length) {
    alert("No leads available to export.");

    return;
  }

  try {
    const response = await fetch("/api/export/csv", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        results: currentResults,
      }),
    });

    if (!response.ok) {
      const contentType = response.headers.get("content-type") || "";

      if (contentType.includes("application/json")) {
        const error = await response.json();

        throw new Error(error.message || "CSV export failed.");
      }

      const text = await response.text();

      throw new Error(
        `CSV export failed (${response.status}): ${text.substring(0, 200)}`,
      );
    }

    const blob = await response.blob();

    downloadFile(blob, "google_maps_leads.csv");
  } catch (error) {
    console.error("CSV Export Error:", error);

    alert(error.message || "CSV export failed.");
  }
}

// =====================================================
// EXPORT EXCEL
// =====================================================

async function exportExcel() {
  if (!currentResults.length) {
    alert("No leads available to export.");

    return;
  }

  try {
    const response = await fetch("/api/export/excel", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        results: currentResults,
      }),
    });

    if (!response.ok) {
      const contentType = response.headers.get("content-type") || "";

      if (contentType.includes("application/json")) {
        const error = await response.json();

        throw new Error(error.message || "Excel export failed.");
      }

      const text = await response.text();

      throw new Error(
        `Excel export failed (${response.status}): ${text.substring(0, 200)}`,
      );
    }

    const blob = await response.blob();

    downloadFile(blob, "google_maps_leads.xlsx");
  } catch (error) {
    console.error("Excel Export Error:", error);

    alert(error.message || "Excel export failed.");
  }
}

// =====================================================
// DOWNLOAD FILE
// =====================================================

function downloadFile(blob, filename) {
  const url = window.URL.createObjectURL(blob);

  const link = document.createElement("a");

  link.href = url;

  link.download = filename;

  document.body.appendChild(link);

  link.click();

  link.remove();

  setTimeout(function () {
    window.URL.revokeObjectURL(url);
  }, 100);
}

// =====================================================
// ESCAPE HTML
// =====================================================

function escapeHtml(value) {
  const div = document.createElement("div");

  div.textContent = value ?? "";

  return div.innerHTML;
}

// =====================================================
// ENTER KEY
// =====================================================

document
  .getElementById("keyword")
  .addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      searchPlaces();
    }
  });

// =====================================================
// PAGE LOAD
// =====================================================

document.addEventListener("DOMContentLoaded", function () {
  loadCountries();

  loadUsage();
});
