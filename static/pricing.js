document.addEventListener("DOMContentLoaded", function () {
  loadCurrentPlan();

  const buttons = document.querySelectorAll(".plan-button");

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      const plan = button.dataset.plan;

      selectPlan(plan, button);
    });
  });
});

// =====================================================
// LOAD CURRENT PLAN
// =====================================================

async function loadCurrentPlan() {
  try {
    const response = await fetch("/api/plans");

    if (!response.ok) {
      return;
    }

    const data = await response.json();

    if (!data.success) {
      return;
    }

    updatePlanUI(
      data.current_plan,
      data.subscription_status,
      data.free_trial_used,
    );
  } catch (error) {
    console.error("Plan Error:", error);
  }
}

// =====================================================
// SELECT PLAN
// =====================================================

async function selectPlan(plan, button) {
  if (!plan) {
    return;
  }

  // =================================================
  // PAID PLANS
  // =================================================

  if (plan === "pro" || plan === "business") {
    window.location.href = `/checkout?plan=${encodeURIComponent(plan)}`;

    return;
  }

  // =================================================
  // FREE PLAN
  // =================================================

  if (plan === "free") {
    const confirmed = window.confirm("Switch to the Free Plan?");

    if (!confirmed) {
      return;
    }

    const originalText = button.textContent;

    button.disabled = true;

    button.textContent = "Processing...";

    showStatus("Updating your plan...", "loading");

    try {
      const response = await fetch("/api/plans/select", {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          plan: "free",
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || "Unable to update plan.");
      }

      if (!data.success) {
        throw new Error(data.message || "Unable to update plan.");
      }

      updatePlanUI("free", "inactive", data.free_trial_used);

      showStatus(data.message, "success");

      setTimeout(function () {
        window.location.href = "/leads";
      }, 800);
    } catch (error) {
      console.error("Plan Selection Error:", error);

      showStatus(error.message, "error");

      button.disabled = false;

      button.textContent = originalText;
    }
  }
}

// =====================================================
// UPDATE PLAN UI
// =====================================================

function updatePlanUI(currentPlan, subscriptionStatus, freeTrialUsed) {
  currentPlan = String(currentPlan || "free").toLowerCase();

  subscriptionStatus = String(subscriptionStatus || "inactive").toLowerCase();

  freeTrialUsed = Boolean(freeTrialUsed);

  const cards = document.querySelectorAll(".pricing-card");

  cards.forEach(function (card) {
    const plan = card.dataset.plan;

    const button = card.querySelector(".plan-button");

    card.classList.remove("selected");

    card.classList.remove("expired");

    if (!button) {
      return;
    }

    // =================================================
    // FREE
    // =================================================

    if (plan === "free") {
      // Free trial already used
      if (freeTrialUsed) {
        button.textContent = "Free Trial Used";

        button.disabled = true;

        card.classList.add("selected");

        return;
      }

      // Free trial not used
      button.textContent = "Choose Free";

      button.disabled = false;

      return;
    }

    // =================================================
    // PRO
    // =================================================

    if (plan === "pro") {
      // -----------------------------------------------
      // PRO ACTIVE
      // -----------------------------------------------

      if (currentPlan === "pro" && subscriptionStatus === "active") {
        card.classList.add("selected");

        button.textContent = "Current Plan";

        button.disabled = true;

        return;
      }

      // -----------------------------------------------
      // PRO EXPIRED
      // -----------------------------------------------

      if (currentPlan === "pro" && subscriptionStatus === "expired") {
        card.classList.add("expired");

        button.textContent = "Renew Pro";

        button.disabled = false;

        return;
      }

      // -----------------------------------------------
      // PRO AVAILABLE
      // -----------------------------------------------

      button.textContent = "Upgrade to Pro";

      button.disabled = false;

      return;
    }

    // =================================================
    // BUSINESS
    // =================================================

    if (plan === "business") {
      // -----------------------------------------------
      // BUSINESS ACTIVE
      // -----------------------------------------------

      if (currentPlan === "business" && subscriptionStatus === "active") {
        card.classList.add("selected");

        button.textContent = "Current Plan";

        button.disabled = true;

        return;
      }

      // -----------------------------------------------
      // BUSINESS EXPIRED
      // -----------------------------------------------

      if (currentPlan === "business" && subscriptionStatus === "expired") {
        card.classList.add("expired");

        button.textContent = "Renew Business";

        button.disabled = false;

        return;
      }

      // -----------------------------------------------
      // BUSINESS AVAILABLE
      // -----------------------------------------------

      button.textContent = "Upgrade to Business";

      button.disabled = false;

      return;
    }
  });
}

// =====================================================
// STATUS
// =====================================================

function showStatus(message, type) {
  const status = document.getElementById("planStatus");

  if (!status) {
    return;
  }

  status.textContent = message;

  status.className = "plan-status";

  if (type) {
    status.classList.add(type);
  }
}
