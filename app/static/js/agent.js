document.addEventListener("submit", async (event) => {
  if (event.target.id !== "agent-preferences") return;
  event.preventDefault();

  const btn = event.target.querySelector("button[type=submit]");
  btn.disabled = true;
  btn.textContent = "Saving…";

  const data = Object.fromEntries(new FormData(event.target).entries());
  data.preferred_assets = [];

  try {
    const response = await fetch("/agent/preferences", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error?.message || "Save failed.");
    showAlert("Preferences saved.", "success");
  } catch (err) {
    showAlert(err.message || "Save failed.");
  } finally {
    btn.disabled = false;
    btn.textContent = "Save preferences";
  }
});

function skeletonCard() {
  return `<div class="suggestion-skeleton">
    <span class="skeleton-line sk-title"></span>
    <span class="skeleton-line sk-body"></span>
    <span class="skeleton-line sk-body2"></span>
    <span class="skeleton-line sk-meta"></span>
  </div>`;
}

function showSkeletons(count = 3) {
  const list = document.getElementById("suggestions-list");
  if (!list) return;
  list.innerHTML = `<div class="suggestion-list">${skeletonCard().repeat(count)}</div>`;
}

function removeCard(suggestionId) {
  const article = document.getElementById(`suggestion-${suggestionId}`);
  if (!article) return;
  article.style.transition = "opacity 0.25s, max-height 0.3s, margin 0.3s, padding 0.3s";
  article.style.overflow = "hidden";
  article.style.opacity = "0";
  article.style.maxHeight = article.offsetHeight + "px";
  requestAnimationFrame(() => {
    article.style.maxHeight = "0";
    article.style.marginTop = "0";
    article.style.marginBottom = "0";
    article.style.paddingTop = "0";
    article.style.paddingBottom = "0";
  });
  setTimeout(() => article.remove(), 320);
}

// Managed polling — a single interval that stops itself on connection error
let _pollInterval = null;
let _pollFailures = 0;
const MAX_POLL_FAILURES = 2;

function startPolling(intervalMs = 8000) {
  if (_pollInterval) return;
  _pollFailures = 0;
  _pollInterval = setInterval(() => {
    if (window.htmx) htmx.trigger(document.body, "refresh");
  }, intervalMs);
}

function stopPolling() {
  if (_pollInterval) {
    clearInterval(_pollInterval);
    _pollInterval = null;
  }
}

// Stop polling when HTMX can't reach the server
document.addEventListener("htmx:sendError", () => {
  _pollFailures++;
  if (_pollFailures >= MAX_POLL_FAILURES) stopPolling();
});

// Reset failure counter on any successful HTMX request
document.addEventListener("htmx:afterRequest", (event) => {
  if (event.detail.successful) _pollFailures = 0;
});

document.addEventListener("click", async (event) => {
  if (event.target.id === "generate-suggestions") {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = "Generating…";
    showSkeletons(3);

    try {
      const response = await fetch("/agent/suggestions/generate", { method: "POST" });
      const payload = await response.json();
      if (!payload.ok) throw new Error(payload.error?.message || "Generation failed.");

      // Show rule-based suggestions immediately
      if (window.htmx) htmx.trigger(document.body, "refresh");

      // Start background polling to pick up LLM suggestions when they arrive
      startPolling(payload.data.llm_pending ? 5000 : 8000);
    } catch (err) {
      if (window.htmx) htmx.trigger(document.body, "refresh");
      showAlert(err.message || "Suggestion generation failed.");
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate suggestions";
    }
    return;
  }

  // Approve / reject buttons
  const suggestionId = event.target.dataset.suggestionId;
  const action = event.target.dataset.action;
  if (!suggestionId || !action) return;

  const btn = event.target;
  btn.disabled = true;

  try {
    const response = await fetch(`/agent/suggestions/${suggestionId}/${action}`, { method: "POST" });
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error?.message || `${action} failed.`);

    if (action === "reject") {
      removeCard(suggestionId);
    } else {
      const article = document.getElementById(`suggestion-${suggestionId}`);
      if (article) {
        const badge = article.querySelector(".status-badge");
        if (badge) {
          badge.textContent = payload.data.status;
          badge.className = `status-badge status-${payload.data.status}`;
        }
        const actions = article.querySelector(".suggestion-actions");
        if (actions) actions.remove();
      }
    }
    showAlert(`Suggestion ${action}d.`, "success");
  } catch (err) {
    showAlert(err.message || `${action} failed.`);
    btn.disabled = false;
  }
});
