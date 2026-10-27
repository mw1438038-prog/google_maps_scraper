
document.addEventListener("DOMContentLoaded", function () {
  const paymentForm = document.getElementById("paymentForm");

  if (!paymentForm) {
    return;
  }

  paymentForm.addEventListener("submit", startFreemiusCheckout);
});

// =====================================================
// START FREEMIUS CHECKOUT
// =====================================================

async function startFreemiusCheckout(event) {
  event.preventDefault();

  const paymentButton = document.getElementById("paymentButton");

  if (!paymentButton || paymentButton.disabled) {
    return;
  }

  const plan = paymentButton.dataset.plan;
  const originalHTML = paymentButton.innerHTML;

  if (!["pro", "business"].includes(plan)) {
    showCheckoutStatus("Invalid subscription plan. Please try again.", "error");
    return;
  }

  paymentButton.disabled = true;
  paymentButton.textContent = "Connecting to Freemius...";

  showCheckoutStatus(
    "Opening Freemius secure checkout. Please wait...",
    "loading"
  );

  try {
    const response = await fetch("/api/checkout/start", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify({
        plan: plan
      })
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data.success || !data.checkout_url) {
      throw new Error(
        data.message || "Could not open Freemius checkout. Please try again."
      );
    }

    // Redirect to the hosted checkout URL returned by the backend.
    window.location.assign(data.checkout_url);
  } catch (error) {
    showCheckoutStatus(
      error.message || "Unable to connect to Freemius checkout.",
      "error"
    );

    paymentButton.disabled = false;
    paymentButton.innerHTML = originalHTML;
  }
}

// =====================================================
// CHECKOUT STATUS MESSAGE
// =====================================================

function showCheckoutStatus(message, type) {
  const status = document.getElementById("checkoutStatus");

  if (!status) {
    return;
  }

  status.textContent = message;
  status.className = "checkout-status show";

  if (type) {
    status.classList.add(type);
  }
}
