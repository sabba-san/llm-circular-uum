import { always, eventually, next } from "@antithesishq/bombadil";
import {
  actions,
  extract,
  registerCustomAction,
} from "@antithesishq/bombadil/browser";
export {
  defaultActions,
  noUncaughtExceptions,
  noUnhandledPromiseRejections,
  noConsoleErrors,
} from "@antithesishq/bombadil/browser/defaults";

// ---------------------------------------------------------------------------
// Custom Domain Query Generator (alongside defaultActions)
// ---------------------------------------------------------------------------

const canSubmitDomainQuery = extract((state) => {
  const doc = state.document;
  if (doc.readyState !== "complete" && doc.readyState !== "interactive") {
    return false;
  }
  const hasSpinner = doc.querySelector(".spinner-inline") !== null;
  const submitBtn = doc.getElementById("btnSubmitQuery") as HTMLButtonElement | null;
  const queryInput = doc.getElementById("queryInput");
  return !hasSpinner && Boolean(queryInput) && Boolean(submitBtn && !submitBtn.disabled);
});

const runDomainQuery = registerCustomAction(
  "submitDomainQuery",
  async (document: Document, _window: Window, query: string) => {
    const viewSearch = document.getElementById("viewSearch");
    const navSearch = document.getElementById("navSearch") as HTMLElement | null;
    if (viewSearch?.classList.contains("hidden") && navSearch) {
      navSearch.click();
    }
    const input = document.getElementById("queryInput") as HTMLTextAreaElement | null;
    const submitBtn = document.getElementById("btnSubmitQuery") as HTMLButtonElement | null;
    if (input && submitBtn && !submitBtn.disabled) {
      input.value = query;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      submitBtn.click();
    }
  }
);

export const domainQueryActions = actions(() => {
  if (!canSubmitDomainQuery.current) return [];
  return [
    runDomainQuery("RMC 008"),
    runDomainQuery("cuti"),
    runDomainQuery("yuran"),
  ];
});

// ---------------------------------------------------------------------------
// State Extractors (mapped from FEATURE_MAP.md & static/app.js)
// ---------------------------------------------------------------------------

// Invariant 1 extractor: HTTP 5xx server errors across navigation & fetch resources
const httpServerErrorsCount = extract((state) => {
  const perf = state.window.performance;
  if (!perf || typeof perf.getEntriesByType !== "function") return 0;

  let count5xx = 0;
  const navEntries = perf.getEntriesByType("navigation") as PerformanceNavigationTiming[];
  for (const entry of navEntries) {
    if (typeof entry.responseStatus === "number" && entry.responseStatus >= 500) {
      count5xx += 1;
    }
  }
  const resEntries = perf.getEntriesByType("resource") as PerformanceResourceTiming[];
  for (const entry of resEntries) {
    const status = (entry as PerformanceResourceTiming & { responseStatus?: number }).responseStatus;
    if (typeof status === "number" && status >= 500) {
      count5xx += 1;
    }
  }
  return count5xx;
});

// Invariant 2 extractor: true while search / follow-up pill request is in flight
const isSearchInFlight = extract((state) => {
  const doc = state.document;
  const hasSpinner = doc.querySelector(".spinner-inline") !== null;
  const submitBtn = doc.getElementById("btnSubmitQuery") as HTMLButtonElement | null;
  const isBtnDisabled = Boolean(submitBtn?.disabled);
  return hasSpinner || isBtnDisabled;
});

// Invariant 3 extractors: clicking .btn-inspect-doc on a reference card populates #rightPane
const inspectClicked = extract((state) => {
  const act = state.lastAction;
  if (!act || typeof act !== "object" || !("Click" in act)) return false;
  const fp = act.Click.fingerprint;
  const text = (fp.textContent || "").trim();
  const hasRefCards = state.document.querySelectorAll("#refsCardsList .ref-card").length > 0;
  return hasRefCards && fp.tag === "button" && text.startsWith("Inspect");
});

const rightPaneViewerPopulated = extract((state) => {
  const doc = state.document;
  const rightPane = doc.getElementById("rightPane");
  const panelViewer = doc.getElementById("panelViewer");
  const viewerTitle = (doc.getElementById("viewerDocTitle")?.textContent || "").trim();
  const viewerBody = doc.getElementById("viewerBody");

  if (!rightPane || !panelViewer || !viewerBody) return false;
  const isExpanded = !rightPane.classList.contains("collapsed");
  const isViewerVisible = !panelViewer.classList.contains("hidden");
  const hasTitle = viewerTitle.length > 0 && viewerTitle !== "Select a Reference Card";
  const hasBodyContent = viewerBody.childElementCount > 0;

  return isExpanded && isViewerVisible && hasTitle && hasBodyContent;
});

// Invariant 4 extractor: #viewSaved DOM vs localStorage["uum_saved_items"]
const savedStateConsistent = extract((state) => {
  const doc = state.document;
  const win = state.window;
  if (doc.readyState !== "complete" && doc.readyState !== "interactive") {
    return true;
  }

  let savedItems: unknown[] = [];
  try {
    const raw = win.localStorage.getItem("uum_saved_items");
    savedItems = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(savedItems)) return false;
  } catch {
    return false;
  }

  const badgeEl = doc.getElementById("badgeSavedCount");
  if (!badgeEl) return true;

  const badgeCount = Number((badgeEl.textContent || "0").trim());
  if (badgeCount !== savedItems.length) return false;

  const viewSaved = doc.getElementById("viewSaved");
  const savedListEl = doc.getElementById("savedList");
  const isViewSavedVisible = Boolean(viewSaved && !viewSaved.classList.contains("hidden"));

  if (isViewSavedVisible && savedListEl) {
    const domCardsCount = savedListEl.querySelectorAll(".catalog-item-card").length;
    const hasEmptyState = savedListEl.querySelector(".refs-empty-state") !== null;
    if (domCardsCount !== savedItems.length) return false;
    if (savedItems.length === 0 && !hasEmptyState) return false;
  }

  return true;
});

// ---------------------------------------------------------------------------
// 4 Core LTL Invariants
// ---------------------------------------------------------------------------

// Invariant 1: Zero uncaught JS console errors or HTTP 500s
// (Combined with re-exported noUncaughtExceptions, noUnhandledPromiseRejections, noConsoleErrors)
export const noHttpServerErrors = always(() => httpServerErrorsCount.current === 0);

// Invariant 2: Search and follow-up pills always settle (no stuck spinner)
export const searchAlwaysSettles = always(() =>
  isSearchInFlight.current
    ? eventually(() => !isSearchInFlight.current).within(20, "seconds")
    : true
);

// Invariant 3: Clicking a reference card (.btn-inspect-doc) populates #rightPane
export const clickingRefPopulatesRightPane = always(() =>
  inspectClicked.current
    ? next(eventually(() => rightPaneViewerPopulated.current).within(3, "seconds"))
    : true
);

// Invariant 4: Toggling Save keeps #viewSaved & localStorage["uum_saved_items"] consistent
export const savedLibraryConsistent = always(() => savedStateConsistent.current);
