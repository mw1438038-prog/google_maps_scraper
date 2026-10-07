document.addEventListener("DOMContentLoaded", function () {
  const paymentButton = document.getElementById("paymentButton");

  if (!paymentButton) {
    return;
  }

  paymentButton.addEventListener("click", processTestPayment);

  // =================================================
  // CARD NUMBER FORMATTING
  // =================================================

  const cardNumber = document.getElementById("cardNumber");

  if (cardNumber) {
    cardNumber.addEventListener("input", function () {
      let value = cardNumber.value.replace(/\D/g, "").substring(0, 16);

      value = value.match(/.{1,4}/g)?.join(" ") || "";

      cardNumber.value = value;
    });
  }

  // =================================================
  // EXPIRY FORMATTING
  // =================================================

  const expiry = document.getElementById("expiry");

  if (expiry) {
    expiry.addEventListener("input", function () {
      let value = expiry.value.replace(/\D/g, "").substring(0, 4);

      if (value.length >= 3) {
        value = value.substring(0, 2) + "/" + value.substring(2);
      }

      expiry.value = value;
    });
  }

  // =================================================
  // CVC
  // =================================================

  const cvc = document.getElementById("cvc");

  if (cvc) {
    cvc.addEventListener("input", function () {
      cvc.value = cvc.value.replace(/\D/g, "").substring(0, 3);
    });
  }
});

// =====================================================
// PROCESS TEST PAYMENT
// =====================================================

async function processTestPayment() {
  const paymentButton = document.getElementById("paymentButton");

  const cardName = document.getElementById("cardName").value.trim();

  const cardNumber = document.getElementById("cardNumber").value.trim();

  const expiry = document.getElementById("expiry").value.trim();

  const cvc = document.getElementById("cvc").value.trim();

  const plan = paymentButton.dataset.plan;

  // =================================================
  // BASIC VALIDATION
  // =================================================

  if (!cardName) {
    showCheckoutStatus("Please enter cardholder name.", "error");

    return;
  }

  if (!cardNumber) {
    showCheckoutStatus("Please enter card number.", "error");

    return;
  }

  if (!expiry) {
    showCheckoutStatus("Please enter card expiry.", "error");

    return;
  }

  if (!cvc) {
    showCheckoutStatus("Please enter CVC.", "error");

    return;
  }

  // =================================================
  // BUTTON STATE
  // =================================================

  const originalText = paymentButton.textContent;

  paymentButton.disabled = true;

  paymentButton.textContent = "Processing Payment...";

  showCheckoutStatus("Processing test payment...", "loading");

  // =================================================
  // SEND TO BACKEND
  // =================================================

  try {
    const response = await fetch("/api/payment/test", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        plan: plan,

        card_name: cardName,

        card_number: cardNumber,

        expiry: expiry,

        cvc: cvc,
      }),
    });

    const data = await response.json();

    // =================================================
    // PAYMENT FAILED
    // =================================================

    if (!response.ok || !data.success) {
      throw new Error(data.message || "Payment failed.");
    }

    // =================================================
    // PAYMENT SUCCESS
    // =================================================

    showCheckoutStatus(data.message, "success");

    paymentButton.textContent = "Payment Successful ✓";

    // =================================================
    // REDIRECT TO LEADS
    // =================================================

    setTimeout(function () {
      window.location.href = "/leads";
    }, 1200);
  } catch (error) {
    console.error("Test Payment Error:", error);

    showCheckoutStatus(error.message || "Payment failed.", "error");

    paymentButton.disabled = false;

    paymentButton.textContent = originalText;
  }
}

// =====================================================
// STATUS MESSAGE
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
