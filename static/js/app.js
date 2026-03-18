const form = document.getElementById("incident-form");
const message = document.getElementById("form-message");
const template = document.getElementById("incident-template");
const search = document.getElementById("search");
const statusFilter = document.getElementById("status-filter");
const severityFilter = document.getElementById("severity-filter");
const refreshBtn = document.getElementById("refresh");
const importFeedBtn = document.getElementById("import-feed");
const importResetBtn = document.getElementById("import-reset");
const feedMeta = document.getElementById("feed-meta");
const splash = document.getElementById("splash");
const lanes = {
  new: document.getElementById("lane-new"),
  verified: document.getElementById("lane-verified"),
  ignored: document.getElementById("lane-ignored"),
  resolved: document.getElementById("lane-resolved"),
};

const detailState = {
  selectedId: null,
  incidents: [],
};

const emptyDetail = document.getElementById("empty-detail");
const detailContent = document.getElementById("detail-content");
const detailTitle = document.getElementById("detail-title");
const detailSummary = document.getElementById("detail-summary");
const detailDescription = document.getElementById("detail-description");
const detailLocation = document.getElementById("detail-location");
const detailChecklist = document.getElementById("detail-checklist");
const detailSeverityBadge = document.getElementById("detail-severity-badge");
const detailCategory = document.getElementById("detail-category");
const detailSource = document.getElementById("detail-source");
const detailEntryMode = document.getElementById("detail-entry-mode");
const detailStatus = document.getElementById("detail-status");
const detailSeverity = document.getElementById("detail-severity");
const detailSave = document.getElementById("detail-save");
const detailReanalyze = document.getElementById("detail-reanalyze");
const detailMessage = document.getElementById("detail-message");
const metricFeedEvents = document.getElementById("metric-feed-events");
const metricActive = document.getElementById("metric-active");
const metricHighRisk = document.getElementById("metric-high-risk");
const metricNextPriority = document.getElementById("metric-next-priority");

function withBusyState(button, busy, labelWhenBusy) {
  button.disabled = busy;
  button.dataset.originalLabel =
    button.dataset.originalLabel || button.textContent;
  button.textContent = busy ? labelWhenBusy : button.dataset.originalLabel;
}

function hideSplash() {
  splash.classList.add("hidden");
  setTimeout(() => splash.remove(), 700);
}

function updateTopMetrics(incidents) {
  const active = incidents.filter((i) =>
    ["new", "verified"].includes(i.status),
  );
  const highRisk = incidents.filter((i) =>
    ["high", "critical"].includes(i.severity),
  );

  metricActive.textContent = `${active.length}`;
  metricHighRisk.textContent = `${highRisk.length}`;

  const severityRank = { critical: 4, high: 3, medium: 2, low: 1 };
  const candidates = active.slice().sort((a, b) => {
    const bySeverity = severityRank[b.severity] - severityRank[a.severity];
    if (bySeverity !== 0) return bySeverity;
    return a.id - b.id;
  });

  if (!candidates.length) {
    metricNextPriority.textContent = "No pending incidents";
    return;
  }

  const top = candidates[0];
  metricNextPriority.textContent = `#${top.id} ${top.title}`;
}

async function fetchIncidents() {
  const params = new URLSearchParams();
  if (search.value.trim()) params.set("q", search.value.trim());
  if (statusFilter.value) params.set("status", statusFilter.value);
  if (severityFilter.value) params.set("severity", severityFilter.value);

  const response = await fetch(`/api/incidents?${params.toString()}`);
  if (!response.ok) {
    throw new Error("Failed to load incidents");
  }
  return response.json();
}

function renderDetail(incident) {
  if (!incident) {
    detailContent.classList.add("hidden");
    emptyDetail.classList.remove("hidden");
    return;
  }

  emptyDetail.classList.add("hidden");
  detailContent.classList.remove("hidden");
  detailTitle.textContent = `#${incident.id} ${incident.title}`;
  detailSummary.textContent = incident.summary;
  detailDescription.textContent = incident.description;
  detailLocation.textContent = `Location: ${incident.location}`;

  detailSeverityBadge.className = "badge severity";
  detailSeverityBadge.classList.add(`severity-${incident.severity}`);
  detailSeverityBadge.textContent = incident.severity;

  detailCategory.textContent = incident.category.replace("_", " ");
  detailSource.textContent = incident.source;
  detailEntryMode.textContent = incident.entry_mode;

  detailChecklist.innerHTML = "";
  incident.checklist.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    detailChecklist.appendChild(li);
  });

  detailStatus.value = incident.status;
  detailSeverity.value = incident.severity;
}

function renderIncidents(incidents) {
  updateTopMetrics(incidents);

  Object.values(lanes).forEach((lane) => {
    lane.innerHTML = "";
  });

  if (!incidents.length) {
    lanes.new.innerHTML = "<p>No incidents found.</p>";
    detailState.selectedId = null;
    renderDetail(null);
    return;
  }

  for (const incident of incidents) {
    const clone = template.content.firstElementChild.cloneNode(true);
    clone.querySelector(".title").textContent =
      `#${incident.id} ${incident.title}`;
    clone.querySelector(".summary").textContent = incident.summary;
    clone.querySelector(".location").textContent =
      `Location: ${incident.location}`;

    const severity = clone.querySelector(".severity");
    severity.textContent = incident.severity;
    severity.classList.add(`severity-${incident.severity}`);

    clone.querySelector(".category").textContent = incident.category.replace(
      "_",
      " ",
    );
    clone.querySelector(".source").textContent = incident.entry_mode;

    clone.querySelector(".open-detail").addEventListener("click", () => {
      detailState.selectedId = incident.id;
      renderDetail(incident);
    });

    const lane = lanes[incident.status] || lanes.new;
    lane.appendChild(clone);
  }

  const selectedIncident = incidents.find(
    (i) => i.id === detailState.selectedId,
  );
  if (selectedIncident) {
    renderDetail(selectedIncident);
  } else {
    detailState.selectedId = incidents[0].id;
    renderDetail(incidents[0]);
  }
}

async function loadAndRender() {
  try {
    const incidents = await fetchIncidents();
    detailState.incidents = incidents;
    renderIncidents(incidents);
  } catch (err) {
    lanes.new.innerHTML = `<p>${err.message}</p>`;
    Object.values(lanes)
      .filter((lane) => lane !== lanes.new)
      .forEach((lane) => {
        lane.innerHTML = "";
      });
  }
}

async function loadFeedPreview() {
  try {
    const response = await fetch("/api/feed/preview");
    if (!response.ok) {
      feedMeta.textContent = "Feed unavailable.";
      metricFeedEvents.textContent = "Unavailable";
      return;
    }
    const info = await response.json();
    feedMeta.textContent = `${info.events_available} feed events ready for ingestion.`;
    metricFeedEvents.textContent = `${info.events_available}`;
  } catch {
    feedMeta.textContent = "Feed unavailable.";
    metricFeedEvents.textContent = "Unavailable";
  }
}

async function importFeed(resetExisting = false) {
  const targetButton = resetExisting ? importResetBtn : importFeedBtn;
  withBusyState(targetButton, true, "Importing...");
  feedMeta.textContent = "Analyzing feed events...";

  try {
    const response = await fetch("/api/feed/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reset_existing: resetExisting }),
    });

    const result = await response.json();
    if (!response.ok) {
      feedMeta.textContent = result.detail || "Feed import failed.";
      return;
    }

    feedMeta.textContent = `Imported ${result.imported} events. Total incidents: ${result.total_incidents}.`;
    await loadAndRender();
  } catch {
    feedMeta.textContent = "Feed import failed.";
  } finally {
    withBusyState(targetButton, false, "Importing...");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.textContent = "Submitting...";

  const payload = {
    title: document.getElementById("title").value,
    description: document.getElementById("description").value,
    location: document.getElementById("location").value,
  };

  const response = await fetch("/api/incidents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    message.textContent =
      error.detail?.[0]?.msg || error.detail || "Failed to save";
    return;
  }

  message.textContent = "Incident created and analyzed.";
  form.reset();
  await loadAndRender();
});

detailSave.addEventListener("click", async () => {
  if (!detailState.selectedId) return;
  withBusyState(detailSave, true, "Saving...");
  detailMessage.textContent = "Updating incident...";

  try {
    const response = await fetch(`/api/incidents/${detailState.selectedId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: detailStatus.value,
        severity: detailSeverity.value,
      }),
    });
    const result = await response.json();

    if (!response.ok) {
      detailMessage.textContent = result.detail || "Update failed.";
      return;
    }

    detailMessage.textContent = "Status and severity updated.";
    await loadAndRender();
  } catch {
    detailMessage.textContent = "Update failed.";
  } finally {
    withBusyState(detailSave, false, "Saving...");
  }
});

detailReanalyze.addEventListener("click", async () => {
  if (!detailState.selectedId) return;
  withBusyState(detailReanalyze, true, "Reanalyzing...");
  detailMessage.textContent = "Running analysis...";

  try {
    const response = await fetch(
      `/api/incidents/${detailState.selectedId}/reanalyze`,
      {
        method: "POST",
      },
    );

    if (!response.ok) {
      detailMessage.textContent = "Reanalysis failed.";
      return;
    }

    detailMessage.textContent = "Incident reanalyzed.";
    await loadAndRender();
  } catch {
    detailMessage.textContent = "Reanalysis failed.";
  } finally {
    withBusyState(detailReanalyze, false, "Reanalyzing...");
  }
});

[search, statusFilter, severityFilter].forEach((node) => {
  node.addEventListener("input", loadAndRender);
  node.addEventListener("change", loadAndRender);
});

refreshBtn.addEventListener("click", loadAndRender);
importFeedBtn.addEventListener("click", () => importFeed(false));
importResetBtn.addEventListener("click", () => importFeed(true));

async function bootstrap() {
  await Promise.all([loadAndRender(), loadFeedPreview()]);
  setTimeout(hideSplash, 800);
}

bootstrap();
