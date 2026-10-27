document.querySelectorAll(".progress-bar[data-progress]").forEach((bar) => {
  const progress = Number.parseFloat(bar.dataset.progress);
  const percentage = Number.isFinite(progress)
    ? Math.min(100, Math.max(0, progress))
    : 0;

  bar.style.width = `${percentage}%`;
  bar.setAttribute("aria-valuenow", String(percentage));
});

document.querySelectorAll(".activity-bar[data-height]").forEach((bar) => {
  const height = Number.parseFloat(bar.dataset.height);
  const percentage = Number.isFinite(height)
    ? Math.min(100, Math.max(0, height))
    : 0;

  bar.style.height = `${percentage}%`;
});
