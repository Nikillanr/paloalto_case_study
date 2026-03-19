/* ── Community Guardian — Dashboard Logic ────────────────────────────── */

(function () {
  "use strict";

  // ── State ──────────────────────────────────────────────────────────
  let incidents = [];
  let selectedId = null;
  let keyboardIdx = -1;
  let debounceTimer = null;

  // ── DOM refs ───────────────────────────────────────────────────────
  const $ = (sel) => document.querySelector(sel);

  // ── Helpers ────────────────────────────────────────────────────────
  function esc(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function confidenceColor(conf) {
    if (conf >= 0.8) return "#4ADE80";
    if (conf >= 0.6) return "#FACC15";
    if (conf >= 0.4) return "#FB923C";
    return "#F87171";
  }

  function formatCategory(cat) {
    return cat.replace(/_/g, " ");
  }

  function formatDate(iso) {
    if (!iso) return "--";
    const d = new Date(iso);
    return d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  }

  // ── Global Engine Setting ────────────────────────────────────────
  function getUseAi() {
    const val = $("#engine-select").value;
    if (val === "ai") return true;
    if (val === "fallback") return false;
    return null; // auto
  }

  // ── Toast System ─────────────────────────────────────────────────
  function toast(text, type = "info") {
    const container = $("#toast-container");
    if (!container) return;

    const el = document.createElement("div");
    el.className = "toast " + type;
    el.innerHTML = `<span class="toast-dot"></span>${esc(text)}`;
    container.appendChild(el);

    setTimeout(() => {
      el.classList.add("dismissing");
      setTimeout(() => el.remove(), 250);
    }, 4000);
  }

  function showMsg(el, text, type) {
    // Still update inline message for context, but also show toast
    el.textContent = text;
    el.className = "message " + type;
    toast(text, type);
    if (type === "success" || type === "info") {
      setTimeout(() => { el.textContent = ""; el.className = "message"; }, 4000);
    }
  }

  // ── Count-up Animation (Stripe technique) ────────────────────────
  function animateCountUp(el, target) {
    const duration = 1200;
    const start = performance.now();
    const from = parseInt(el.textContent) || 0;
    const diff = target - from;

    if (diff === 0) { el.textContent = target; return; }

    function frame(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(from + diff * eased);
      if (progress < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // ── API calls ──────────────────────────────────────────────────────
  async function api(path, opts = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    try {
      const res = await fetch("/api" + path, {
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        ...opts,
      });
      clearTimeout(timeoutId);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json();
    } catch (e) {
      clearTimeout(timeoutId);
      if (e.name === "AbortError") throw new Error("Request timed out — try again or switch to Fallback mode");
      throw e;
    }
  }

  // ── Load & Render Stats ────────────────────────────────────────────
  async function loadStats() {
    try {
      const stats = await api("/stats");

      // Count-up animation on stat numbers
      animateCountUp($("#stat-total"), stats.total);
      const critHigh = (stats.by_severity.critical || 0) + (stats.by_severity.high || 0);
      animateCountUp($("#stat-critical"), critHigh);

      // Category bars — render at 0 width, then animate
      const catEl = $("#stat-categories");
      const maxCat = Math.max(1, ...Object.values(stats.by_category));
      const entries = Object.entries(stats.by_category)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

      catEl.innerHTML = entries
        .map(([cat, count]) => `
          <div class="stat-bar-row">
            <span class="stat-bar-label">${esc(formatCategory(cat))}</span>
            <div class="stat-bar-track">
              <div class="stat-bar-fill" data-width="${(count / maxCat * 100)}"></div>
            </div>
            <span class="stat-bar-count">${count}</span>
          </div>
        `).join("");

      // Trigger bar animation after a frame (so 0→target transition plays)
      requestAnimationFrame(() => {
        catEl.querySelectorAll(".stat-bar-fill").forEach((bar) => {
          bar.style.width = bar.dataset.width + "%";
        });
      });

      // Confidence
      const conf = stats.avg_confidence;
      $(".confidence-value").textContent = conf > 0 ? (conf * 100).toFixed(0) + "%" : "--";
      $(".confidence-value").style.color = conf > 0 ? confidenceColor(conf) : "";

    } catch (e) {
      console.error("Stats load failed:", e);
    }
  }

  // ── Load & Render Incidents ────────────────────────────────────────
  async function loadIncidents() {
    const search = $("#filter-search").value;
    const status = $("#filter-status").value;
    const severity = $("#filter-severity").value;
    const category = $("#filter-category").value;

    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (severity) params.set("severity", severity);
    if (category) params.set("category", category);

    try {
      const data = await api("/incidents?" + params.toString());
      incidents = data.incidents;
      renderIncidentList();
    } catch (e) {
      console.error("Incidents load failed:", e);
    }
  }

  function renderIncidentList() {
    const list = $("#incident-list");

    if (incidents.length === 0) {
      list.innerHTML = '<p class="empty-state">No incidents found. Import feed events or submit a manual report to begin triage.</p>';
      keyboardIdx = -1;
      return;
    }

    // Staggered card animation: set --card-delay per card (30ms each)
    list.innerHTML = incidents.map((inc, i) => `
      <div class="incident-card severity-${esc(inc.severity)} ${inc.id === selectedId ? 'active' : ''}"
           data-id="${inc.id}" data-index="${i}" style="--card-delay: ${i * 30}ms">
        <div class="card-header">
          <span class="badge badge-${esc(inc.severity)}">${esc(inc.severity)}</span>
          <span class="badge badge-category">${esc(formatCategory(inc.category))}</span>
          <span class="badge badge-${esc(inc.source)}">${esc(inc.source)}</span>
          <span class="badge badge-status">${esc(inc.status)}</span>
        </div>
        <div class="card-title">${esc(inc.title)}</div>
        <div class="card-summary">${esc(inc.summary)}</div>
        <div class="card-footer">
          <span class="card-location">${esc(inc.location)}</span>
          <span class="card-confidence">${(inc.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>
    `).join("");

    // Click handlers
    list.querySelectorAll(".incident-card").forEach((card) => {
      card.addEventListener("click", () => {
        selectedId = parseInt(card.dataset.id);
        keyboardIdx = parseInt(card.dataset.index);
        highlightCards();
        renderDetail();
      });
    });
  }

  // ── Keyboard focus highlight (without full re-render) ─────────────
  function highlightCards() {
    const list = $("#incident-list");
    list.querySelectorAll(".incident-card").forEach((card) => {
      const id = parseInt(card.dataset.id);
      const idx = parseInt(card.dataset.index);
      card.classList.toggle("active", id === selectedId);
      card.classList.toggle("keyboard-focus", idx === keyboardIdx && id !== selectedId);
    });
  }

  // ── Render Detail Panel ────────────────────────────────────────────
  function renderDetail() {
    const inc = incidents.find((i) => i.id === selectedId);
    if (!inc) {
      $("#detail-empty").classList.remove("hidden");
      $("#detail-content").classList.add("hidden");
      return;
    }

    $("#detail-empty").classList.add("hidden");
    $("#detail-content").classList.remove("hidden");

    // Badges
    $("#detail-badges").innerHTML = `
      <span class="badge badge-${esc(inc.severity)}">${esc(inc.severity)}</span>
      <span class="badge badge-category">${esc(formatCategory(inc.category))}</span>
      <span class="badge badge-${esc(inc.source)}">${esc(inc.source)} analysis</span>
      <span class="badge badge-status">${esc(inc.status)}</span>
      <span class="badge badge-status">${esc(inc.entry_mode)}</span>
    `;

    $("#detail-title").textContent = inc.title;

    // Confidence bar
    const confPct = (inc.confidence * 100).toFixed(0);
    const confBar = $("#detail-confidence-bar");
    confBar.style.width = confPct + "%";
    confBar.style.background = confidenceColor(inc.confidence);
    $("#detail-confidence-text").textContent = confPct + "%";
    $("#detail-confidence-text").style.color = confidenceColor(inc.confidence);

    // Content
    $("#detail-summary").textContent = inc.summary;
    $("#detail-description").textContent = inc.description;
    $("#detail-location").textContent = inc.location;
    $("#detail-reasoning").textContent = inc.reasoning;
    $("#detail-timestamps").textContent =
      `Created: ${formatDate(inc.created_at)}  \u00B7  Updated: ${formatDate(inc.updated_at)}`;

    // Checklist — clickable items
    const cl = $("#detail-checklist");
    cl.innerHTML = inc.checklist.map((item) => `<li>${esc(item)}</li>`).join("");
    cl.querySelectorAll("li").forEach((li) => {
      li.addEventListener("click", () => li.classList.toggle("checked"));
    });

    // Controls
    $("#detail-status").value = inc.status;
    $("#detail-severity").value = inc.severity;
  }

  // ── Keyboard Navigation (Linear technique) ───────────────────────
  function initKeyboardNav() {
    document.addEventListener("keydown", (e) => {
      // Don't intercept when typing in inputs/textareas
      const tag = e.target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        if (incidents.length === 0) return;
        keyboardIdx = Math.min(keyboardIdx + 1, incidents.length - 1);
        selectedId = incidents[keyboardIdx].id;
        highlightCards();
        renderDetail();
        scrollCardIntoView(keyboardIdx);
      }

      if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        if (incidents.length === 0) return;
        keyboardIdx = Math.max(keyboardIdx - 1, 0);
        selectedId = incidents[keyboardIdx].id;
        highlightCards();
        renderDetail();
        scrollCardIntoView(keyboardIdx);
      }

      if (e.key === "Escape") {
        selectedId = null;
        keyboardIdx = -1;
        highlightCards();
        renderDetail();
      }
    });
  }

  function scrollCardIntoView(idx) {
    const card = $(`[data-index="${idx}"]`);
    if (card) card.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  // ── Actions ────────────────────────────────────────────────────────

  async function createIncident(e) {
    e.preventDefault();
    const btn = e.target.querySelector("button[type=submit]");
    const msg = $("#form-message");
    btn.disabled = true;
    btn.textContent = "Analyzing...";

    try {
      const body = {
        title: $("#field-title").value.trim(),
        description: $("#field-desc").value.trim(),
        location: $("#field-location").value.trim(),
      };

      // Global engine setting
      const useAi = getUseAi();
      if (useAi !== null) body.use_ai = useAi;

      const inc = await api("/incidents", { method: "POST", body: JSON.stringify(body) });
      showMsg(msg, `Incident #${inc.id} created (${inc.source} analysis, ${inc.category})`, "success");
      e.target.reset();
      await refresh();
    } catch (err) {
      showMsg(msg, err.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Analyze & Submit";
    }
  }

  async function importFeed(reset = false) {
    const btn = reset ? $("#btn-reset-import") : $("#btn-import");
    const msg = $("#feed-message");
    btn.disabled = true;
    const useAi = getUseAi();
    const aiActive = useAi !== false && $("#ai-status").classList.contains("online");
    btn.innerHTML = aiActive
      ? 'AI Analyzing...<span class="spinner"></span>'
      : 'Importing...<span class="spinner"></span>';

    try {
      const body = { max_items: 50, reset_existing: reset };
      if (useAi !== null) body.use_ai = useAi;

      const data = await api("/feed/import", {
        method: "POST",
        body: JSON.stringify(body),
      });
      showMsg(msg, `Imported ${data.imported} events${data.reanalyzed ? `, reanalyzed ${data.reanalyzed} manual` : ''} (${data.total_incidents} total)`, "success");
      await refresh();
    } catch (err) {
      showMsg(msg, err.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = reset ? "Reset & Reimport" : "Import Feed Events";
    }
  }

  async function updateIncident() {
    if (!selectedId) return;
    const msg = $("#detail-message");
    const btn = $("#btn-save");
    btn.disabled = true;

    try {
      const body = {
        status: $("#detail-status").value,
        severity: $("#detail-severity").value,
      };
      await api(`/incidents/${selectedId}`, { method: "PUT", body: JSON.stringify(body) });
      showMsg(msg, "Updated successfully", "success");
      await refresh();
    } catch (err) {
      showMsg(msg, err.message, "error");
    } finally {
      btn.disabled = false;
    }
  }

  async function reanalyze() {
    if (!selectedId) return;
    const msg = $("#detail-message");
    const btn = $("#btn-reanalyze");
    btn.disabled = true;
    btn.innerHTML = 'Analyzing...<span class="spinner"></span>';

    try {
      const body = {};
      const useAi = getUseAi();
      if (useAi !== null) body.use_ai = useAi;

      await api(`/incidents/${selectedId}/reanalyze`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      showMsg(msg, "Reanalysis complete", "success");
      await refresh();
    } catch (err) {
      showMsg(msg, err.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Reanalyze";
    }
  }

  async function loadFeedPreview() {
    try {
      const data = await api("/feed/preview");
      $("#feed-count").textContent = `${data.total} events available`;
    } catch {
      $("#feed-count").textContent = "Feed unavailable";
    }
  }

  async function checkAiStatus() {
    try {
      const data = await fetch("/health").then((r) => r.json());
      const el = $("#ai-status");
      if (data.daily_limit_hit) {
        el.textContent = "AI Quota Exhausted";
        el.className = "ai-status offline";
      } else if (data.ai_available) {
        el.textContent = "AI Online";
        el.className = "ai-status online";
      } else {
        el.textContent = "Fallback Mode";
        el.className = "ai-status offline";
      }
    } catch {
      const el = $("#ai-status");
      el.textContent = "Offline";
      el.className = "ai-status offline";
    }
  }

  async function refresh() {
    await Promise.all([loadStats(), loadIncidents(), checkAiStatus()]);
    renderDetail();
  }

  // ── Splash screen ──────────────────────────────────────────────────
  function dismissSplash() {
    const splash = $("#splash");
    if (!splash) return;
    splash.classList.add("fade-out");
    setTimeout(() => {
      splash.remove();
      // First data load happens AFTER splash is gone so animations are visible
      refresh();
    }, 600);
  }

  // ── Init ───────────────────────────────────────────────────────────
  function init() {
    // Dismiss splash after data loads (or timeout as safety net)
    const splashTimeout = setTimeout(dismissSplash, 5000);

    // Event bindings
    $("#incident-form").addEventListener("submit", createIncident);
    $("#btn-import").addEventListener("click", () => importFeed(false));
    $("#btn-reset-import").addEventListener("click", () => importFeed(true));
    $("#btn-refresh").addEventListener("click", refresh);
    $("#btn-save").addEventListener("click", updateIncident);
    $("#btn-reanalyze").addEventListener("click", reanalyze);

    // Keyboard navigation
    initKeyboardNav();

    // Filters with debounce
    const filterHandler = () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(loadIncidents, 250);
    };
    $("#filter-search").addEventListener("input", filterHandler);
    $("#filter-status").addEventListener("change", loadIncidents);
    $("#filter-severity").addEventListener("change", loadIncidents);
    $("#filter-category").addEventListener("change", loadIncidents);

    // Initial load — only lightweight checks during splash, data loads after
    Promise.all([checkAiStatus(), loadFeedPreview()]).then(() => {
      clearTimeout(splashTimeout);
      // Let the scan animation play, then dismiss
      setTimeout(dismissSplash, 2000);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
