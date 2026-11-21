/**
 * UUM Guide & Forms (LLM UUM) Frontend Engine
 * Handles 3-Pane Responsive Navigation, RAG Querying, Markdown/Table/Citation Rendering,
 * Multi-Turn Thread Persistence, Source Cards, and Live PDF/Document Inspector.
 */

(function () {
  "use strict";

  // ==================== Configuration & Constants ====================
  const SCOPES = [
    { id: "All", label: "All UUM" },
    { id: "CAS", label: "CAS (Arts & Sciences)" },
    { id: "COB", label: "COB (Business)" },
    { id: "COLGIS", label: "COLGIS (Law & Govt)" },
    { id: "HEA", label: "HEA Shared (Calendars & Forms)" },
    { id: "RMC", label: "RMC (Research Grants & GRA)" },
    { id: "Bendahari", label: "Bendahari (Finance & Claims)" },
    { id: "ICC", label: "ICC (Innovation & IP)" },
    { id: "JUU", label: "JUU (Legal & Statutes)" },
  ];

  const STARTERS = [
    {
      role: "Lecturer / Researcher",
      title: "How to Apply for a UUM Research Grant",
      scope: "RMC",
      query: "How do I apply for a UUM research grant and which official form is required?",
    },
    {
      role: "Student",
      title: "HEA Minor Course Registration",
      scope: "HEA",
      query: "Apakah prosedur dan borang yang diperlukan untuk permohonan pendaftaran kursus Minor di HEA?",
    },
    {
      role: "Postgrad",
      title: "Postgraduate Thesis Proposal Notice (SAPSP)",
      scope: "CAS",
      query: "Which form should a postgraduate student submit for Notice of Intention to Submit Research Proposal in SAPSP?",
    },
    {
      role: "Lecturer / GRA",
      title: "GRA Appointment & Allowance Ceilings",
      scope: "RMC",
      query: "What are the requirements and allowance ceilings to appoint a Graduate Research Assistant (GRA)?",
    },
    {
      role: "Lecturer / Staff",
      title: "External Speaker Honorarium Rates",
      scope: "Bendahari",
      query: "Berapakah kadar bayaran saguhati penceramah luar daripada sektor swasta mengikut Pekeliling Bendahari?",
    },
    {
      role: "Staff / PTJ",
      title: "University Asset Disposal Procedure",
      scope: "Bendahari",
      query: "Apakah proses dan borang yang diperlukan untuk pelupusan aset universiti yang rosak?",
    },
  ];

  const DOC_TYPE_LABELS = {
    circular: "Circular",
    admin_form: "PTJ Form",
    college_doc: "Academic Handbook",
    college_form: "Student Form",
  };

  const MAX_SAVED_THREADS = 25;
  const CATALOG_PAGE_SIZE = 100;
  const MOBILE_BREAKPOINT = 900;

  // SVG Icon Templates
  const ICONS = {
    doc: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    download: '<svg class="icon-svg-xs" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
    starFilled: '<svg class="icon-svg-sm" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    starOutline: '<svg class="icon-svg-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    message: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    close: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    academic: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
    warning: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  };

  // ==================== Storage Helpers & Legacy Migration ====================
  function safeReadStorage(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function compactSource(s) {
    if (!s || typeof s !== "object") return null;
    return {
      chunk_id: s.chunk_id || s.doc_id || "",
      doc_id: s.doc_id || s.circular_id || "",
      title: s.title || s.circular_ref_no || "UUM Document",
      circular_ref_no: s.circular_ref_no || "",
      department: s.department || s.college || "UUM",
      college: s.college || "",
      page_number: s.page_number || 1,
      section_heading: s.section_heading || "",
      chunk_text: String(s.chunk_text || "").slice(0, 500),
      file_format: s.file_format || "PDF",
      doc_type: s.doc_type || "circular",
      required_forms: s.required_forms || "",
    };
  }

  function compactForm(f) {
    if (!f || typeof f !== "object") return null;
    return {
      doc_id: f.doc_id || "",
      code: f.code || "",
      title: f.title || f.code || "Official Form",
      department: f.department || f.college || "UUM",
      file_format: f.file_format || "PDF",
      doc_type: f.doc_type || "admin_form",
    };
  }

  function normalizeStoredThreads(rawList) {
    const normalized = [];
    for (const entry of rawList) {
      if (!entry || typeof entry !== "object") continue;
      if (Array.isArray(entry.turns) && entry.turns.length > 0) {
        const cleanTurns = entry.turns
          .filter((t) => t && t.query && t.response)
          .map((t) => ({
            query: String(t.query),
            scope: String(t.scope || entry.scope || "All"),
            response: {
              answer: String(t.response.answer || ""),
              provider: String(t.response.provider || ""),
              language: t.response.language || "",
              sources: (t.response.sources || []).map(compactSource).filter(Boolean),
              linked_forms: (t.response.linked_forms || []).map(compactForm).filter(Boolean),
              follow_up_questions: Array.isArray(t.response.follow_up_questions)
                ? t.response.follow_up_questions.slice(0, 3)
                : [],
              scope: String(t.response.scope || t.scope || "All"),
            },
          }));
        if (cleanTurns.length > 0) {
          normalized.push({
            id: String(entry.id || `th_${Date.now()}_${normalized.length}`),
            title: String(entry.title || cleanTurns[0].query.slice(0, 45)),
            scope: String(entry.scope || cleanTurns[cleanTurns.length - 1].scope || "All"),
            updatedAt: String(entry.updatedAt || entry.timestamp || ""),
            turns: cleanTurns.slice(-12),
          });
        }
      } else if (entry.query && entry.cachedResponse) {
        // Migrate legacy single-turn thread entry
        normalized.push({
          id: String(entry.id || `th_legacy_${normalized.length}`),
          title: String(entry.title || entry.query.slice(0, 45)),
          scope: String(entry.scope || "All"),
          updatedAt: String(entry.timestamp || ""),
          turns: [
            {
              query: String(entry.query),
              scope: String(entry.scope || "All"),
              response: {
                answer: String(entry.cachedResponse.answer || ""),
                provider: String(entry.cachedResponse.provider || ""),
                language: entry.cachedResponse.language || "",
                sources: (entry.cachedResponse.sources || []).map(compactSource).filter(Boolean),
                linked_forms: (entry.cachedResponse.linked_forms || []).map(compactForm).filter(Boolean),
                follow_up_questions: Array.isArray(entry.cachedResponse.follow_up_questions)
                  ? entry.cachedResponse.follow_up_questions.slice(0, 3)
                  : [],
                scope: String(entry.cachedResponse.scope || entry.scope || "All"),
              },
            },
          ],
        });
      }
      if (normalized.length >= MAX_SAVED_THREADS) break;
    }
    return normalized;
  }

  // ==================== Application State ====================
  const state = {
    activeScope: "All",
    filterActive: true,
    activeTheme: localStorage.getItem("uum_theme") || "dark",
    activeView: "search", // 'search', 'catalog', 'saved'
    threads: normalizeStoredThreads(safeReadStorage("uum_threads", [])),
    activeThreadId: null,
    activeThreadTitle: "UUM Guide & Forms",
    savedItems: safeReadStorage("uum_saved_items", []),
    catalogItems: [],
    catalogStats: {},
    catalogVisibleLimit: CATALOG_PAGE_SIZE,
    currentSources: [],
    currentDocInViewer: null,
    activeCardIndex: null,
    isSubmitting: false,
    lastQuery: "",
    autoPredictItems: [],
    autoPredictIdx: -1,
  };

  // ==================== DOM Selectors ====================
  const dom = {
    html: document.documentElement,
    themeLightBtn: document.getElementById("btnThemeLight"),
    themeDarkBtn: document.getElementById("btnThemeDark"),
    sidebar: document.getElementById("leftSidebar"),
    sidebarBackdrop: document.getElementById("sidebarBackdrop"),
    btnMobileMenu: document.getElementById("btnMobileMenu"),
    btnCollapseSidebar: document.getElementById("btnCollapseSidebar"),
    btnNewThread: document.getElementById("btnNewThread"),
    btnClearThreads: document.getElementById("btnClearThreads"),
    threadsList: document.getElementById("threadsList"),
    kbStatsFooter: document.getElementById("kbStatsFooter"),
    badgeTotalDocs: document.getElementById("badgeTotalDocs"),
    badgeSavedCount: document.getElementById("badgeSavedCount"),
    heroDocCount: document.getElementById("heroDocCount"),
    navSearch: document.getElementById("navSearch"),
    navCatalog: document.getElementById("navCatalog"),
    navSaved: document.getElementById("navSaved"),
    viewSearch: document.getElementById("viewSearch"),
    viewCatalog: document.getElementById("viewCatalog"),
    viewSaved: document.getElementById("viewSaved"),
    currentThreadTitle: document.getElementById("currentThreadTitle"),
    activeScopeBadge: document.getElementById("activeScopeBadge"),
    btnCopyThread: document.getElementById("btnCopyThread"),
    btnCopyLabel: document.getElementById("btnCopyLabel"),
    btnSaveThread: document.getElementById("btnSaveThread"),
    btnToggleRightPane: document.getElementById("btnToggleRightPane"),
    headerRefsCount: document.getElementById("headerRefsCount"),
    welcomeHero: document.getElementById("welcomeHero"),
    heroStartersGrid: document.getElementById("heroStartersGrid"),
    turnsContainer: document.getElementById("turnsContainer"),
    threadScrollArea: document.getElementById("threadScrollArea"),
    searchForm: document.getElementById("searchForm"),
    autoPredictMenu: document.getElementById("autoPredictMenu"),
    queryInput: document.getElementById("queryInput"),
    btnSubmitQuery: document.getElementById("btnSubmitQuery"),
    btnScopeMenu: document.getElementById("btnScopeMenu"),
    scopeBtnLabel: document.getElementById("scopeBtnLabel"),
    scopePopover: document.getElementById("scopePopover"),
    scopePopoverList: document.getElementById("scopePopoverList"),
    btnClearScope: document.getElementById("btnClearScope"),
    clearScopeLabel: document.getElementById("clearScopeLabel"),
    btnActiveToggle: document.getElementById("btnActiveToggle"),
    activeToggleLabel: document.getElementById("activeToggleLabel"),
    rightPane: document.getElementById("rightPane"),
    btnCloseRightPane: document.getElementById("btnCloseRightPane"),
    tabBtnRefs: document.getElementById("tabBtnRefs"),
    tabBtnViewer: document.getElementById("tabBtnViewer"),
    panelRefs: document.getElementById("panelRefs"),
    panelViewer: document.getElementById("panelViewer"),
    refsCountPill: document.getElementById("refsCountPill"),
    refsEmptyState: document.getElementById("refsEmptyState"),
    refsCardsList: document.getElementById("refsCardsList"),
    rightMetaLabel: document.getElementById("rightMetaLabel"),
    btnBackToRefs: document.getElementById("btnBackToRefs"),
    viewerDocTitle: document.getElementById("viewerDocTitle"),
    viewerDocSub: document.getElementById("viewerDocSub"),
    viewerActions: document.getElementById("viewerActions"),
    viewerBody: document.getElementById("viewerBody"),
    catSearchInput: document.getElementById("catSearchInput"),
    catTypeSelect: document.getElementById("catTypeSelect"),
    catCollegeSelect: document.getElementById("catCollegeSelect"),
    optTypeAll: document.getElementById("optTypeAll"),
    optTypeCollegeDoc: document.getElementById("optTypeCollegeDoc"),
    optTypeCollegeForm: document.getElementById("optTypeCollegeForm"),
    optTypeCircular: document.getElementById("optTypeCircular"),
    optTypeAdminForm: document.getElementById("optTypeAdminForm"),
    catalogCountBar: document.getElementById("catalogCountBar"),
    catalogList: document.getElementById("catalogList"),
    catalogPagination: document.getElementById("catalogPagination"),
    btnCatalogLoadMore: document.getElementById("btnCatalogLoadMore"),
    savedList: document.getElementById("savedList"),
    toastContainer: document.getElementById("toastContainer"),
  };

  // ==================== Utilities ====================
  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function isDesktopViewport() {
    return window.innerWidth > MOBILE_BREAKPOINT;
  }

  function isMalayText(text, explicitLang) {
    if (explicitLang === "ms") return true;
    if (explicitLang === "en") return false;
    return /\b(apakah|bagaimana|berapakah|bilakah|syarat|borang|pekeliling|kursus|geran|pelupusan)\b/i.test(text || "");
  }

  function showToast(message) {
    if (!dom.toastContainer || !message) return;
    const toast = document.createElement("div");
    toast.className = "toast-msg";
    toast.textContent = message;
    dom.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 2400);
  }

  function closeMobileSidebar() {
    if (dom.sidebar) dom.sidebar.classList.remove("mobile-open");
    if (dom.sidebarBackdrop) dom.sidebarBackdrop.classList.add("hidden");
  }

  function toggleMobileSidebar() {
    if (!dom.sidebar) return;
    const willOpen = !dom.sidebar.classList.contains("mobile-open");
    dom.sidebar.classList.toggle("mobile-open", willOpen);
    if (dom.sidebarBackdrop) dom.sidebarBackdrop.classList.toggle("hidden", !willOpen);
  }

  // ==================== Theme Controller ====================
  function applyTheme(theme) {
    state.activeTheme = theme;
    dom.html.setAttribute("data-theme", theme);
    localStorage.setItem("uum_theme", theme);
    if (dom.themeDarkBtn && dom.themeLightBtn) {
      dom.themeDarkBtn.classList.toggle("active", theme === "dark");
      dom.themeLightBtn.classList.toggle("active", theme !== "dark");
    }
  }

  // ==================== Header Context Controller ====================
  function syncHeaderUI() {
    const hasTurns = Boolean(dom.turnsContainer && dom.turnsContainer.children.length > 0);
    const hasSources = state.currentSources.length > 0;
    const onSearch = state.activeView === "search";

    if (dom.currentThreadTitle) {
      if (state.activeView === "catalog") {
        dom.currentThreadTitle.textContent = "Documents & Forms";
      } else if (state.activeView === "saved") {
        dom.currentThreadTitle.textContent = "Saved";
      } else {
        dom.currentThreadTitle.textContent = hasTurns ? state.activeThreadTitle : "UUM Guide & Forms";
      }
    }

    if (dom.activeScopeBadge) {
      const showScope = onSearch && (hasTurns || state.activeScope !== "All");
      dom.activeScopeBadge.classList.toggle("hidden", !showScope);
      dom.activeScopeBadge.textContent = state.activeScope === "All" ? "All UUM" : state.activeScope;
    }

    if (dom.btnSaveThread) dom.btnSaveThread.classList.toggle("hidden", !(onSearch && hasSources));
    if (dom.btnCopyThread) dom.btnCopyThread.classList.toggle("hidden", !(onSearch && hasTurns));
    if (dom.btnToggleRightPane) {
      const showSourcesBtn = (onSearch && hasSources) || Boolean(state.currentDocInViewer);
      dom.btnToggleRightPane.classList.toggle("hidden", !showSourcesBtn);
    }
  }

  function syncScopeControls() {
    const scopeObj = SCOPES.find((s) => s.id === state.activeScope) || SCOPES[0];
    if (dom.scopeBtnLabel) dom.scopeBtnLabel.textContent = scopeObj.id === "All" ? "All UUM" : scopeObj.id;
    if (dom.btnScopeMenu) dom.btnScopeMenu.classList.toggle("active", state.activeScope !== "All");
    if (dom.btnClearScope) {
      const isScoped = state.activeScope !== "All";
      dom.btnClearScope.classList.toggle("hidden", !isScoped);
      if (dom.clearScopeLabel) dom.clearScopeLabel.textContent = `Filtering: ${scopeObj.id}`;
    }
    renderScopePopovers();
    syncHeaderUI();
  }

  // ==================== Markdown, Tables & Multi-Citation Formatter ====================
  function buildCitePillHtml(srcNum, pageNum, sources) {
    const srcIdx = parseInt(srcNum, 10) - 1;
    if (Number.isNaN(srcIdx) || srcIdx < 0) return `[Source ${srcNum}]`;
    const src = sources && sources[srcIdx] ? sources[srcIdx] : null;
    if (!src) return `[Source ${srcNum}]`;
    const page = pageNum || src.page_number || 1;
    const docName = src.title || src.circular_ref_no || `Source ${srcIdx + 1}`;
    const pillText = page ? `Source ${srcIdx + 1} · p.${page}` : `Source ${srcIdx + 1}`;
    const titleTooltip = escapeHtml(`${docName} (Page ${page}) — Click to inspect`);
    return `<button type="button" class="cite-pill" data-src-idx="${srcIdx}" data-page="${escapeHtml(String(page))}" title="${titleTooltip}">${ICONS.doc}<span>${escapeHtml(pillText)}</span></button>`;
  }

  function replaceCitationsInHtml(html, sources) {
    // 1. Multi-source & single-source brackets like [Source 2, Source 5, Source 6] or [Source 1, p.2; Source 3]
    let out = html.replace(/\[([^\]]*Source\s*\d+[^\]]*)\]/gi, (fullMatch, inner) => {
      const pills = [];
      const tokenRe = /Source\s*(\d+)(?:(?:\s*[,·]\s*|\s+)(?:Page|p\.?)\s*(\d+))?/gi;
      let m;
      while ((m = tokenRe.exec(inner)) !== null) {
        pills.push(buildCitePillHtml(m[1], m[2], sources));
      }
      return pills.length > 0 ? pills.join(" ") : fullMatch;
    });

    // 2. Bare numeric citations like [1] or [1, 2]
    out = out.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (fullMatch, nums) => {
      const parts = nums.split(",").map((n) => n.trim()).filter(Boolean);
      if (parts.length === 0) return fullMatch;
      const valid = parts.every((n) => {
        const idx = parseInt(n, 10) - 1;
        return sources && sources[idx];
      });
      if (!valid) return fullMatch;
      return parts.map((n) => buildCitePillHtml(n, null, sources)).join(" ");
    });

    return out;
  }

  function formatInlineMarkdown(escapedLine) {
    let s = escapedLine;
    s = s.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
    return s;
  }

  function isTableSeparatorLine(line) {
    return /^\s*\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$/.test(line);
  }

  function splitTableCells(line) {
    const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
    return trimmed.split("|").map((c) => c.trim());
  }

  function renderLLMUUMMarkdown(rawText, sources, language) {
    if (!rawText) return "";

    // Step 1: Escape ALL HTML first so table/list/citation rendering is XSS-safe
    let escaped = escapeHtml(rawText).replace(/\r\n/g, "\n");

    // Step 2: Normalize single-line compressed lists like "1. Item 2. Item 3. Item"
    escaped = escaped.replace(/(\d+\.\s+[^\n]+?)(?=\s+\d+\.\s+)/g, "$1\n");

    const isMs = language === "ms";
    const takeawayLabel = isMs ? "Rumusan Utama" : "Key Takeaway";

    const lines = escaped.split("\n");
    const htmlParts = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) {
        i += 1;
        continue;
      }

      // Key Takeaway / Rumusan Utama callout
      const takeawayMatch = trimmed.match(/^(?:\*\*Key Takeaway:\*\*|\*\*Rumusan Utama:\*\*)\s*(.*)$/i);
      if (takeawayMatch) {
        const bodyLines = [];
        if (takeawayMatch[1]) bodyLines.push(takeawayMatch[1]);
        i += 1;
        while (i < lines.length && lines[i].trim() && !/^(#{1,5}\s|[-*]\s|\d+\.\s|\|)/.test(lines[i].trim())) {
          bodyLines.push(lines[i].trim());
          i += 1;
        }
        const bodyHtml = formatInlineMarkdown(bodyLines.join(" "));
        htmlParts.push(`<div class="key-takeaway-box"><strong>${takeawayLabel}</strong>${bodyHtml}</div>`);
        continue;
      }

      // Horizontal rule
      if (/^(?:---|___|\*\*\*)$/.test(trimmed)) {
        htmlParts.push("<hr />");
        i += 1;
        continue;
      }

      // Blockquote (e.g. Extractive Index Mode note)
      if (trimmed.startsWith("&gt;")) {
        const quoteLines = [];
        while (i < lines.length && lines[i].trim().startsWith("&gt;")) {
          quoteLines.push(lines[i].trim().replace(/^&gt;\s?/, ""));
          i += 1;
        }
        htmlParts.push(`<div class="key-takeaway-box">${formatInlineMarkdown(quoteLines.join("<br />"))}</div>`);
        continue;
      }

      // Headings
      const headingMatch = trimmed.match(/^(#{1,5})\s+(.*)$/);
      if (headingMatch) {
        const level = headingMatch[1].length;
        const tag = level <= 2 ? "h2" : level === 3 ? "h3" : "h4";
        htmlParts.push(`<${tag}>${formatInlineMarkdown(headingMatch[2])}</${tag}>`);
        i += 1;
        continue;
      }

      // GFM Markdown Table
      if (trimmed.includes("|") && i + 1 < lines.length && isTableSeparatorLine(lines[i + 1])) {
        const headers = splitTableCells(trimmed);
        i += 2; // Skip header + separator
        const rows = [];
        while (i < lines.length && lines[i].trim().includes("|") && !/^(#{1,5}\s)/.test(lines[i].trim())) {
          rows.push(splitTableCells(lines[i]));
          i += 1;
        }
        const thHtml = headers.map((h) => `<th>${formatInlineMarkdown(h)}</th>`).join("");
        const bodyRowsHtml = rows
          .map((r) => {
            const cells = headers.map((_, idx) => `<td>${formatInlineMarkdown(r[idx] || "")}</td>`).join("");
            return `<tr>${cells}</tr>`;
          })
          .join("");
        htmlParts.push(
          `<div class="table-scroll"><table class="llm-table"><thead><tr>${thHtml}</tr></thead><tbody>${bodyRowsHtml}</tbody></table></div>`
        );
        continue;
      }

      // Ordered list (<ol>)
      if (/^\d+\.\s+/.test(trimmed)) {
        const items = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          const itemText = lines[i].replace(/^\s*\d+\.\s+/, "");
          items.push(`<li>${formatInlineMarkdown(itemText)}</li>`);
          i += 1;
        }
        htmlParts.push(`<ol>${items.join("")}</ol>`);
        continue;
      }

      // Unordered list (<ul>)
      if (/^[-*]\s+/.test(trimmed)) {
        const items = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          const itemText = lines[i].replace(/^\s*[-*]\s+/, "");
          items.push(`<li>${formatInlineMarkdown(itemText)}</li>`);
          i += 1;
        }
        htmlParts.push(`<ul>${items.join("")}</ul>`);
        continue;
      }

      // Regular paragraph
      const paraLines = [];
      while (
        i < lines.length &&
        lines[i].trim() &&
        !/^(#{1,5}\s|[-*]\s|\d+\.\s|&gt;|---|___|\*\*\*|\*\*Key Takeaway:\*\*|\*\*Rumusan Utama:\*\*)/i.test(lines[i].trim()) &&
        !(lines[i].trim().includes("|") && i + 1 < lines.length && isTableSeparatorLine(lines[i + 1]))
      ) {
        paraLines.push(lines[i].trim());
        i += 1;
      }
      if (paraLines.length > 0) {
        htmlParts.push(`<p>${formatInlineMarkdown(paraLines.join("<br />"))}</p>`);
      }
    }

    // Final step: Run multi-source & single-source citation pill replacement LAST (works safely inside tables & callouts!)
    const finalHtml = replaceCitationsInHtml(htmlParts.join("\n"), sources);
    return `<div class="llm-prose">${finalHtml}</div>`;
  }

  // ==================== Scope Popover & Welcome Starters ====================
  function renderScopePopovers() {
    if (!dom.scopePopoverList) return;
    dom.scopePopoverList.replaceChildren();

    SCOPES.forEach((sc) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `popover-item ${sc.id === state.activeScope ? "active" : ""}`;
      btn.innerHTML = `<span class="popover-item-title">${escapeHtml(sc.label)}</span>`;
      btn.addEventListener("click", () => {
        state.activeScope = sc.id;
        dom.scopePopover.classList.add("hidden");
        syncScopeControls();
      });
      dom.scopePopoverList.appendChild(btn);
    });
  }

  function renderWelcomeStarters() {
    if (!dom.heroStartersGrid) return;
    dom.heroStartersGrid.replaceChildren();

    STARTERS.forEach((bm) => {
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "stacked-scenario-pill";
      pill.title = bm.query;
      pill.innerHTML = `
        <div class="scenario-pill-left">
          <span class="scenario-role-tag">${escapeHtml(bm.role)}</span>
          <span class="scenario-title-text">${escapeHtml(bm.title)}</span>
        </div>
        <div class="scenario-arrow-circle" aria-hidden="true">
          <svg class="icon-svg-sm" viewBox="0 0 24 24"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
        </div>
      `;
      // Starter uses its domain scope for this query without locking future typed queries
      pill.addEventListener("click", () => triggerSearch(bm.query, bm.scope, { persistScope: false }));
      dom.heroStartersGrid.appendChild(pill);
    });
  }

  // ==================== Sources Panel Controller ====================
  function renderReferenceCards(sources) {
    state.currentSources = sources || [];
    const count = state.currentSources.length;
    if (dom.refsCountPill) dom.refsCountPill.textContent = count;
    if (dom.headerRefsCount) dom.headerRefsCount.textContent = count;
    if (dom.rightMetaLabel) dom.rightMetaLabel.textContent = `${count} Sources Cited`;
    syncHeaderUI();

    if (!dom.refsCardsList) return;
    dom.refsCardsList.replaceChildren();

    if (!sources || sources.length === 0) {
      if (dom.refsEmptyState) dom.refsEmptyState.classList.remove("hidden");
      return;
    }
    if (dom.refsEmptyState) dom.refsEmptyState.classList.add("hidden");

    sources.forEach((src, idx) => {
      const card = document.createElement("article");
      card.className = "ref-card";
      card.id = `refCard_${idx}`;

      const itemKey = src.chunk_id || src.doc_id;
      const isSaved = state.savedItems.some((s) => (s.chunk_id || s.doc_id) === itemKey);
      const fmtClass = (src.file_format || "PDF").toLowerCase();

      card.innerHTML = `
        <div class="ref-card-header">
          <div class="ref-badge-num">${idx + 1}</div>
          <div class="ref-title-box">
            <h4 class="ref-title">${escapeHtml(src.title || src.circular_ref_no)}</h4>
            <div class="ref-dept">${escapeHtml(src.department || src.college)} &bull; ${escapeHtml(src.section_heading || "Official Clause")}</div>
          </div>
          <button type="button" class="ref-save-btn ${isSaved ? "saved" : ""}" data-idx="${idx}" title="${isSaved ? "Remove Bookmark" : "Save"}">
            ${isSaved ? ICONS.starFilled : ICONS.starOutline}
          </button>
        </div>

        <div class="ref-quote-box">
          "${escapeHtml(src.chunk_text ? src.chunk_text.slice(0, 240) : "")}..."
        </div>

        <div class="ref-card-footer">
          <div class="ref-footer-left">
            <span class="fmt-badge ${escapeHtml(fmtClass)}">${escapeHtml(src.file_format || "PDF")}</span>
            <span class="ref-pill-tag">Page ${escapeHtml(String(src.page_number || 1))}</span>
            ${src.required_forms && src.required_forms !== "-" ? `<span class="ref-pill-tag" title="${escapeHtml(src.required_forms)}">Form Attached</span>` : ""}
          </div>
          <button type="button" class="btn-inspect-doc" data-idx="${idx}">
            <span>Inspect &rarr;</span>
          </button>
        </div>
      `;

      card.querySelector(".ref-save-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        toggleSaveItem(src);
        renderReferenceCards(state.currentSources);
      });

      card.querySelector(".btn-inspect-doc").addEventListener("click", () => {
        openDocumentInInspector(src, idx, true);
      });

      dom.refsCardsList.appendChild(card);
    });
  }

  function highlightReferenceCard(srcIdx) {
    document.querySelectorAll(".ref-card").forEach((c) => c.classList.remove("active-target"));
    const targetCard = document.getElementById(`refCard_${srcIdx}`);
    if (targetCard) {
      targetCard.classList.add("active-target");
      targetCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  // ==================== Document Inspector Viewer Controller ====================
  function openDocumentInInspector(docMeta, cardIdx = null, switchTab = true, forceOpenPane = true) {
    if (!docMeta) return;
    state.currentDocInViewer = docMeta;
    state.activeCardIndex = cardIdx;

    if (cardIdx !== null) {
      highlightReferenceCard(cardIdx);
    }

    if (forceOpenPane && dom.rightPane) {
      dom.rightPane.classList.remove("collapsed");
    }

    const title = docMeta.title || docMeta.circular_ref_no || "UUM Document";
    const fmt = (docMeta.file_format || "PDF").toUpperCase();
    const page = docMeta.page_number || 1;

    if (dom.viewerDocTitle) dom.viewerDocTitle.textContent = title;
    if (dom.viewerDocSub) {
      dom.viewerDocSub.textContent = `${docMeta.department || docMeta.college || "UUM"} • Format: ${fmt} • Page ${page}`;
    }

    syncHeaderUI();

    if (switchTab) {
      switchRightTab("viewer");
    }
  }

  function renderViewerContent() {
    const docMeta = state.currentDocInViewer;
    if (!docMeta) return;

    const docId = docMeta.doc_id || docMeta.circular_id;
    const title = docMeta.title || docMeta.circular_ref_no || "UUM Document";
    const fmt = (docMeta.file_format || "PDF").toUpperCase();
    const page = docMeta.page_number || 1;
    const isInlineViewable = fmt === "PDF" || fmt === "PNG" || fmt === "JPG" || fmt === "JPEG";

    if (dom.viewerDocTitle) dom.viewerDocTitle.textContent = title;
    if (dom.viewerDocSub) {
      dom.viewerDocSub.textContent = `${docMeta.department || docMeta.college || "UUM"} • Format: ${fmt} • Page ${page}`;
    }
    if (dom.viewerActions) dom.viewerActions.replaceChildren();

    // 1. Open in new tab button (ONLY for inline-viewable PDFs & images — avoid duplicate download on DOCX/XLSX)
    if (isInlineViewable) {
      const btnExternal = document.createElement("a");
      btnExternal.className = "btn-action-icon";
      btnExternal.href = `/api/document/${encodeURIComponent(docId)}/preview#page=${page}`;
      btnExternal.target = "_blank";
      btnExternal.rel = "noopener noreferrer";
      btnExternal.title = "Open Document in New Tab";
      btnExternal.innerHTML = '<svg class="icon-svg-sm" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>';
      if (dom.viewerActions) dom.viewerActions.appendChild(btnExternal);
    }

    // 2. Download button
    const btnDownload = document.createElement("a");
    btnDownload.className = "btn-action-icon";
    btnDownload.href = `/api/document/${encodeURIComponent(docId)}/download`;
    btnDownload.download = "";
    btnDownload.title = "Download File";
    btnDownload.innerHTML = '<svg class="icon-svg-sm" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
    if (dom.viewerActions) dom.viewerActions.appendChild(btnDownload);

    // 3. Save / Bookmark button
    const itemKey = docMeta.chunk_id || docId;
    const isSaved = state.savedItems.some((s) => (s.chunk_id || s.doc_id) === itemKey);
    const btnSave = document.createElement("button");
    btnSave.type = "button";
    btnSave.className = `btn-action-icon ${isSaved ? "saved" : ""}`;
    btnSave.title = isSaved ? "Remove Bookmark" : "Save";
    btnSave.innerHTML = isSaved ? ICONS.starFilled : ICONS.starOutline;
    btnSave.addEventListener("click", () => {
      toggleSaveItem(docMeta);
      renderViewerContent();
    });
    if (dom.viewerActions) dom.viewerActions.appendChild(btnSave);

    if (!dom.viewerBody) return;
    dom.viewerBody.replaceChildren();

    if (fmt === "PDF") {
      const iframe = document.createElement("iframe");
      iframe.className = "pdf-iframe";
      iframe.src = `/api/document/${encodeURIComponent(docId)}/preview#page=${page}`;
      iframe.title = `PDF Document Preview - ${title}`;
      dom.viewerBody.appendChild(iframe);
    } else if (fmt === "PNG" || fmt === "JPG" || fmt === "JPEG") {
      const container = document.createElement("div");
      container.className = "image-viewer-container";
      container.innerHTML = `
        <div class="image-preview-box">
          <img src="/api/document/${encodeURIComponent(docId)}/preview" alt="${escapeHtml(title)}" />
        </div>
      `;
      dom.viewerBody.appendChild(container);
    } else {
      const container = document.createElement("div");
      container.className = "doc-text-preview-container";
      container.innerHTML = `
        <div class="doc-download-card">
          <div class="doc-download-info">
            <h4>${escapeHtml(title)}</h4>
            <p>${escapeHtml(fmt)} Document • ${escapeHtml(docMeta.department || docMeta.college || "UUM")}</p>
          </div>
          <a href="/api/document/${encodeURIComponent(docId)}/download" class="btn-download-primary" download>
            ${ICONS.download}
            <span>Download ${escapeHtml(fmt)}</span>
          </a>
        </div>
        <div class="doc-sections-list">
          <div class="doc-section-card">
            <div class="doc-section-heading">Document Excerpt</div>
            <div class="doc-section-body">${escapeHtml(docMeta.chunk_text || "Loading preview sections...")}</div>
          </div>
        </div>
      `;
      dom.viewerBody.appendChild(container);

      if (!docMeta.chunk_text && docId) {
        fetch(`/api/doc/${encodeURIComponent(docId)}`)
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (!data || !data.sections || data.sections.length === 0) {
              const bodyElem = container.querySelector(".doc-section-body");
              if (bodyElem && !docMeta.chunk_text) bodyElem.textContent = "Use the Download button above to open this official form.";
              return;
            }
            const sectionsList = container.querySelector(".doc-sections-list");
            if (sectionsList) {
              sectionsList.replaceChildren();
              data.sections.slice(0, 15).forEach((sec) => {
                const card = document.createElement("div");
                card.className = "doc-section-card";
                card.innerHTML = `
                  <div class="doc-section-heading">${escapeHtml(sec.heading || `Page ${sec.page}`)}</div>
                  <div class="doc-section-body">${escapeHtml(sec.text || "")}</div>
                `;
                sectionsList.appendChild(card);
              });
            }
          })
          .catch(() => {});
      }
    }
  }

  function resetViewerPlaceholder() {
    state.currentDocInViewer = null;
    state.activeCardIndex = null;
    if (dom.viewerDocTitle) dom.viewerDocTitle.textContent = "Select a document to inspect";
    if (dom.viewerDocSub) dom.viewerDocSub.textContent = "No document loaded";
    if (dom.viewerActions) dom.viewerActions.replaceChildren();
    if (dom.viewerBody) {
      dom.viewerBody.innerHTML = `
        <div class="refs-empty-state">
          <div class="empty-icon-wrap">
            <svg class="icon-empty-svg" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </div>
          <h3>No Document Selected</h3>
          <p>Click any citation pill, source card, or document row to open its PDF, image, or form preview here.</p>
        </div>
      `;
    }
  }

  function switchRightTab(tabKey) {
    if (tabKey === "viewer") {
      dom.tabBtnViewer.classList.add("active");
      dom.tabBtnRefs.classList.remove("active");
      dom.tabBtnViewer.setAttribute("aria-selected", "true");
      dom.tabBtnRefs.setAttribute("aria-selected", "false");
      dom.panelViewer.classList.remove("hidden");
      dom.panelRefs.classList.add("hidden");
      if (state.currentDocInViewer) {
        renderViewerContent();
      }
    } else {
      dom.tabBtnRefs.classList.add("active");
      dom.tabBtnViewer.classList.remove("active");
      dom.tabBtnRefs.setAttribute("aria-selected", "true");
      dom.tabBtnViewer.setAttribute("aria-selected", "false");
      dom.panelRefs.classList.remove("hidden");
      dom.panelViewer.classList.add("hidden");
    }
  }

  // ==================== Saved Items / Bookmarks Controller ====================
  function persistSavedItems() {
    try {
      localStorage.setItem("uum_saved_items", JSON.stringify(state.savedItems));
    } catch (_) {}
    updateSavedBadge();
    renderSavedList();
  }

  function saveItemIfNew(item) {
    const key = item.chunk_id || item.doc_id;
    const exists = state.savedItems.some((s) => (s.chunk_id || s.doc_id) === key);
    if (exists) return false;
    state.savedItems.push({
      ...compactSource(item),
      saved_at: new Date().toISOString(),
    });
    return true;
  }

  function toggleSaveItem(item) {
    const key = item.chunk_id || item.doc_id;
    const existingIdx = state.savedItems.findIndex((s) => (s.chunk_id || s.doc_id) === key);
    if (existingIdx >= 0) {
      state.savedItems.splice(existingIdx, 1);
    } else {
      state.savedItems.push({
        ...compactSource(item),
        saved_at: new Date().toISOString(),
      });
    }
    persistSavedItems();
  }

  function updateSavedBadge() {
    if (dom.badgeSavedCount) dom.badgeSavedCount.textContent = state.savedItems.length;
  }

  function renderSavedList() {
    if (!dom.savedList) return;
    dom.savedList.replaceChildren();

    if (state.savedItems.length === 0) {
      dom.savedList.innerHTML = `
        <div class="refs-empty-state">
          <div class="empty-icon-wrap">
            <svg class="icon-empty-svg" viewBox="0 0 24 24"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
          </div>
          <h3>No Saved Items Yet</h3>
          <p>Click the star icon on any source card or document viewer to bookmark important circulars and forms here.</p>
        </div>
      `;
      return;
    }

    state.savedItems.forEach((item) => {
      const card = document.createElement("div");
      card.className = "catalog-item-card";
      card.innerHTML = `
        <div class="cat-item-left">
          <div class="cat-item-title">${escapeHtml(item.title || item.circular_ref_no)}</div>
          <div class="cat-item-meta">
            <span>${escapeHtml(item.department || item.college || "UUM")}</span>
            <span>Page ${escapeHtml(String(item.page_number || 1))}</span>
          </div>
        </div>
        <div class="cat-item-right">
          <span class="fmt-badge ${escapeHtml((item.file_format || "PDF").toLowerCase())}">${escapeHtml(item.file_format || "PDF")}</span>
          <button type="button" class="btn-action-icon btn-remove-saved" title="Remove Bookmark">
            ${ICONS.close}
          </button>
        </div>
      `;

      card.querySelector(".btn-remove-saved").addEventListener("click", (e) => {
        e.stopPropagation();
        toggleSaveItem(item);
      });

      card.addEventListener("click", () => {
        openDocumentInInspector(item, null, true, true);
      });

      dom.savedList.appendChild(card);
    });
  }

  // ==================== Documents & Forms Catalog Controller ====================
  function updateCatalogTypeCounts() {
    const st = state.catalogStats || {};
    const total = st.total_documents || state.catalogItems.length;
    if (dom.optTypeAll) dom.optTypeAll.textContent = `All Types (${total})`;
    if (dom.optTypeCollegeDoc) dom.optTypeCollegeDoc.textContent = `Academic Handbooks & Guides (${st.total_college_docs || 0})`;
    if (dom.optTypeCollegeForm) dom.optTypeCollegeForm.textContent = `Student & College Forms (${st.total_college_forms || 0})`;
    if (dom.optTypeCircular) dom.optTypeCircular.textContent = `Circulars & Statutes (${st.total_circulars || 0})`;
    if (dom.optTypeAdminForm) dom.optTypeAdminForm.textContent = `PTJ & Staff Forms (${st.total_admin_forms || 0})`;
  }

  function loadCatalog() {
    fetch("/api/catalog")
      .then((res) => res.json())
      .then((data) => {
        state.catalogItems = data.items || [];
        state.catalogStats = data.stats || {};
        const total = state.catalogStats.total_documents || state.catalogItems.length;
        if (dom.badgeTotalDocs) dom.badgeTotalDocs.textContent = total;
        if (dom.heroDocCount) dom.heroDocCount.textContent = `${total} official`;
        if (dom.kbStatsFooter) {
          dom.kbStatsFooter.textContent = `LLM UUM · ${total} official documents indexed`;
        }
        updateCatalogTypeCounts();
        renderCatalogItems();
      })
      .catch((err) => {
        console.error("Failed to load catalog:", err);
      });
  }

  function renderCatalogItems(resetLimit = false) {
    if (!dom.catalogList) return;
    if (resetLimit) {
      state.catalogVisibleLimit = CATALOG_PAGE_SIZE;
    }

    const query = (dom.catSearchInput ? dom.catSearchInput.value : "").trim().toLowerCase();
    const typeFilter = dom.catTypeSelect ? dom.catTypeSelect.value : "all";
    const collegeFilter = dom.catCollegeSelect ? dom.catCollegeSelect.value : "all";

    const filtered = state.catalogItems.filter((item) => {
      if (typeFilter !== "all" && item.doc_type !== typeFilter) return false;
      if (collegeFilter !== "all") {
        const itemCol = (item.college || item.department || "").toUpperCase();
        if (!itemCol.includes(collegeFilter.toUpperCase())) return false;
      }
      if (query) {
        const hay = `${item.title} ${item.circular_ref_no || ""} ${item.code || ""} ${item.department || ""} ${item.scope_keywords || ""}`.toLowerCase();
        if (!hay.includes(query)) return false;
      }
      return true;
    });

    const visibleSlice = filtered.slice(0, state.catalogVisibleLimit);
    if (dom.catalogCountBar) {
      dom.catalogCountBar.textContent =
        visibleSlice.length < filtered.length
          ? `Showing ${visibleSlice.length} of ${filtered.length} matching documents`
          : `Showing ${filtered.length} of ${state.catalogItems.length} documents`;
    }

    dom.catalogList.replaceChildren();

    if (visibleSlice.length === 0) {
      dom.catalogList.innerHTML = `
        <div class="refs-empty-state">
          <h3>No Matching Documents</h3>
          <p>Try a broader keyword or switch the type/department filters back to All.</p>
        </div>
      `;
    } else {
      visibleSlice.forEach((item) => {
        const row = document.createElement("div");
        row.className = "catalog-item-card";
        const typeLabel = DOC_TYPE_LABELS[item.doc_type] || item.doc_type || "Document";
        row.innerHTML = `
          <div class="cat-item-left">
            <div class="cat-item-title">${escapeHtml(item.title || item.circular_ref_no)}</div>
            <div class="cat-item-meta">
              <span>${escapeHtml(item.department || item.college || "UUM")}</span>
              <span>${escapeHtml(typeLabel)}</span>
              ${item.page_count ? `<span>${escapeHtml(String(item.page_count))} pages</span>` : ""}
            </div>
          </div>
          <div class="cat-item-right">
            <span class="fmt-badge ${escapeHtml((item.file_format || "PDF").toLowerCase())}">${escapeHtml(item.file_format || "PDF")}</span>
          </div>
        `;
        row.addEventListener("click", () => {
          openDocumentInInspector(item, null, true, true);
        });
        dom.catalogList.appendChild(row);
      });
    }

    if (dom.catalogPagination && dom.btnCatalogLoadMore) {
      const remaining = filtered.length - visibleSlice.length;
      dom.catalogPagination.classList.toggle("hidden", remaining <= 0);
      if (remaining > 0) {
        const nextBatch = Math.min(remaining, CATALOG_PAGE_SIZE);
        dom.btnCatalogLoadMore.textContent = `Show ${nextBatch} more (${remaining} remaining)`;
      }
    }
  }

  // ==================== Search & RAG Flow ====================
  function triggerSearch(queryText, scopeOverride = null, options = {}) {
    if (!queryText || state.isSubmitting) return;
    hideAutoPredict();
    closeMobileSidebar();

    const persistScope = options.persistScope !== false;
    const targetScope = scopeOverride || state.activeScope;
    if (persistScope && scopeOverride) {
      state.activeScope = scopeOverride;
      syncScopeControls();
    }

    switchView("search");

    // Clear composer input immediately after submitting
    if (dom.queryInput) dom.queryInput.value = "";
    if (dom.welcomeHero) dom.welcomeHero.classList.add("hidden");

    if (!state.activeThreadId) {
      state.activeThreadId = `th_${Date.now()}`;
      state.activeThreadTitle = queryText.slice(0, 50) + (queryText.length > 50 ? "..." : "");
    }
    syncHeaderUI();

    const userTurn = document.createElement("div");
    userTurn.className = "turn-user";
    userTurn.innerHTML = `<div class="turn-user-bubble">${escapeHtml(queryText)}</div>`;
    dom.turnsContainer.appendChild(userTurn);

    const totalDocs = state.catalogStats.total_documents || state.catalogItems.length || "official";
    const assistantTurn = document.createElement("div");
    assistantTurn.className = "turn-assistant";
    assistantTurn.innerHTML = `
      <div class="turn-assistant-meta">
        <span class="assistant-identity">${ICONS.academic}<span>UUM Guide</span></span>
        <span class="assistant-engine-badge"><span class="spinner-inline"></span> Searching ${escapeHtml(String(totalDocs))} documents...</span>
      </div>
      <div class="llm-prose">
        <p>Checking official UUM circulars, handbooks, and forms...</p>
      </div>
    `;
    dom.turnsContainer.appendChild(assistantTurn);
    dom.threadScrollArea.scrollTop = dom.threadScrollArea.scrollHeight;

    state.isSubmitting = true;
    dom.btnSubmitQuery.disabled = true;

    fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: queryText,
        scope: targetScope,
        filter_active: state.filterActive,
        previous_query: state.lastQuery || "",
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Request failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        state.isSubmitting = false;
        dom.btnSubmitQuery.disabled = false;
        state.lastQuery = queryText;

        renderAssistantTurn(assistantTurn, queryText, targetScope, data, { autoOpenDesktop: true });
        saveTurnToThreadHistory(queryText, targetScope, data);
        dom.threadScrollArea.scrollTop = dom.threadScrollArea.scrollHeight;
      })
      .catch(() => {
        state.isSubmitting = false;
        dom.btnSubmitQuery.disabled = false;
        assistantTurn.innerHTML = `
          <div class="turn-assistant-meta">
            <span class="assistant-identity">${ICONS.warning}<span>Connection Error</span></span>
          </div>
          <div class="llm-prose">
            <p>Unable to reach the UUM document service right now. Please try again in a moment.</p>
          </div>
          <div class="recovery-actions">
            <button type="button" class="btn-recovery btn-retry-query">Retry Question</button>
          </div>
        `;
        const retryBtn = assistantTurn.querySelector(".btn-retry-query");
        if (retryBtn) {
          retryBtn.addEventListener("click", () => {
            userTurn.remove();
            assistantTurn.remove();
            triggerSearch(queryText, targetScope, { persistScope });
          });
        }
      });
  }

  function renderLinkedFormsChips(forms, isMs) {
    if (!forms || forms.length === 0) return "";
    const header = isMs ? "Borang Rasmi & Templat Tindakan:" : "Official Forms & Downloadable Templates:";
    const downloadLabel = isMs ? "Muat Turun" : "Download";
    const chips = forms
      .map((f) => {
        const displayTitle = f.title || f.code || "Official Form";
        const fmt = (f.file_format || "PDF").toUpperCase();
        const fmtClass = fmt.toLowerCase();
        const dlUrl = `/api/document/${encodeURIComponent(f.doc_id)}/download`;
        return `
          <div class="form-chip-card">
            <button type="button" class="form-chip-preview" data-form-id="${escapeHtml(f.doc_id)}" title="${escapeHtml(displayTitle)} — Preview">
              <span class="form-chip-icon">${ICONS.doc}</span>
              <span class="form-chip-title">${escapeHtml(displayTitle)}</span>
              <span class="fmt-badge ${escapeHtml(fmtClass)}">${escapeHtml(fmt)}</span>
            </button>
            <a href="${dlUrl}" class="form-chip-download" download title="${escapeHtml(downloadLabel)} ${escapeHtml(displayTitle)}">
              ${ICONS.download}
              <span>${escapeHtml(downloadLabel)}</span>
            </a>
          </div>
        `;
      })
      .join("");

    return `
      <div class="action-forms-bar">
        <div class="action-forms-header">${header}</div>
        <div class="forms-chips-grid">${chips}</div>
      </div>
    `;
  }

  function renderZeroResultRecovery(targetScope, queryText, isMs) {
    const buttons = [];
    if (targetScope && targetScope !== "All") {
      buttons.push(
        `<button type="button" class="btn-recovery" data-recover="all">${
          isMs ? "Cari di Semua UUM (All UUM)" : "Search across All UUM"
        }</button>`
      );
    }
    if (state.filterActive) {
      buttons.push(
        `<button type="button" class="btn-recovery" data-recover="historical">${
          isMs ? "Sertakan Pekeliling Arkib / Terdahulu" : "Include Historical Circulars"
        }</button>`
      );
    }
    if (buttons.length === 0) return "";
    return `<div class="recovery-actions">${buttons.join("")}</div>`;
  }

  function renderFollowUpQuestions(followUps, isMs) {
    if (!followUps || followUps.length === 0) return "";
    const header = isMs ? "Cadangan Soalan Susulan:" : "Suggested Follow-Up Questions:";
    const items = followUps
      .map(
        (q) => `
        <button type="button" class="followup-btn" data-query="${escapeHtml(q)}">
          <span class="followup-arrow">&crarr;</span>
          <span>${escapeHtml(q)}</span>
        </button>
      `
      )
      .join("");

    return `
      <div class="followup-section">
        <div class="followup-label">${header}</div>
        <div class="followup-list">${items}</div>
      </div>
    `;
  }

  // ==================== Local Catalog Auto-Predict ====================
  function hideAutoPredict() {
    state.autoPredictItems = [];
    state.autoPredictIdx = -1;
    if (dom.autoPredictMenu) {
      dom.autoPredictMenu.classList.add("hidden");
      dom.autoPredictMenu.replaceChildren();
    }
  }

  function inferScopeBadge(item) {
    const col = (item.college || item.department || "").toUpperCase();
    if (col.includes("CAS")) return "CAS";
    if (col.includes("COB")) return "COB";
    if (col.includes("COLGIS")) return "COLGIS";
    if (col.includes("SHARED") || col.includes("HEA")) return "HEA";
    if (col.includes("RMC") || col.includes("RESEARCH")) return "RMC";
    if (col.includes("BENDAHARI")) return "Bendahari";
    if (col.includes("ICC") || col.includes("INNOVATION")) return "ICC";
    return "All";
  }

  function buildAutoPredictSuggestions(rawInput) {
    const q = (rawInput || "").trim();
    if (q.length < 2 || q.length > 90) return [];
    const qLower = q.toLowerCase();
    const tokens = qLower.split(/\s+/).filter((t) => t.length >= 2);
    if (tokens.length === 0) return [];

    const isMs = isMalayText(qLower);
    const results = [];
    const seenQueries = new Set();

    const addSuggestion = (queryText, scope, tag) => {
      const key = queryText.toLowerCase();
      if (key === qLower || seenQueries.has(key)) return;
      seenQueries.add(key);
      results.push({ query: queryText, scope: scope || state.activeScope, tag });
    };

    STARTERS.forEach((bm) => {
      const hay = `${bm.title} ${bm.query} ${bm.scope}`.toLowerCase();
      if (tokens.every((t) => hay.includes(t))) {
        addSuggestion(bm.query, bm.scope, bm.scope);
      }
    });

    if (state.catalogItems && state.catalogItems.length > 0) {
      const scored = [];
      for (let i = 0; i < state.catalogItems.length; i++) {
        const item = state.catalogItems[i];
        const title = (item.title || "").trim();
        const code = (item.code || "").trim();
        if (!title && !code) continue;
        const hay = `${title} ${code} ${item.department || ""} ${item.school || ""}`.toLowerCase();
        if (!tokens.every((t) => hay.includes(t))) continue;

        let rank = 0;
        if (code && code.toLowerCase().includes(qLower)) rank += 4;
        if (title.toLowerCase().startsWith(qLower)) rank += 3;
        if (item.doc_type === "college_form" || item.doc_type === "admin_form") rank += 1;
        scored.push({ rank, item });
      }
      scored.sort((a, b) => b.rank - a.rank);

      for (let i = 0; i < scored.length && results.length < 5; i++) {
        const it = scored[i].item;
        const label = it.title || it.code;
        const isForm = it.doc_type === "college_form" || it.doc_type === "admin_form";
        const predictedQuery = isForm
          ? (isMs ? `Apakah prosedur dan syarat bagi borang ${label}?` : `What are the requirements and submission steps for ${label}?`)
          : (isMs ? `Apakah maklumat dan syarat utama dalam ${label}?` : `What are the key rules and requirements in ${label}?`);
        addSuggestion(predictedQuery, inferScopeBadge(it), it.code || inferScopeBadge(it));
      }
    }

    return results.slice(0, 5);
  }

  function renderAutoPredict() {
    if (!dom.autoPredictMenu) return;
    dom.autoPredictMenu.replaceChildren();
    if (!state.autoPredictItems || state.autoPredictItems.length === 0) {
      dom.autoPredictMenu.classList.add("hidden");
      return;
    }

    state.autoPredictItems.forEach((item, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "autopredict-item" + (idx === state.autoPredictIdx ? " active" : "");
      btn.setAttribute("role", "option");
      btn.innerHTML = `
        <span class="autopredict-query">${escapeHtml(item.query)}</span>
        <span class="autopredict-scope">${escapeHtml(item.tag || item.scope)}</span>
      `;
      btn.addEventListener("mousedown", (e) => {
        e.preventDefault();
        hideAutoPredict();
        triggerSearch(item.query, item.scope !== "All" ? item.scope : state.activeScope, { persistScope: false });
      });
      dom.autoPredictMenu.appendChild(btn);
    });

    dom.autoPredictMenu.classList.remove("hidden");
  }

  function updateAutoPredict() {
    if (!dom.queryInput) return;
    state.autoPredictItems = buildAutoPredictSuggestions(dom.queryInput.value);
    state.autoPredictIdx = -1;
    renderAutoPredict();
  }

  function renderAssistantTurn(assistantTurn, queryText, targetScope, data, opts = {}) {
    const sources = data.sources || [];
    const linkedForms = data.linked_forms || [];
    const isMs = isMalayText(queryText, data.language);
    const lang = isMs ? "ms" : "en";
    const answerHtml = renderLLMUUMMarkdown(data.answer, sources, lang);
    const formsHtml = renderLinkedFormsChips(linkedForms, isMs);
    const recoveryHtml = sources.length === 0 ? renderZeroResultRecovery(targetScope, queryText, isMs) : "";
    const followUpsHtml = renderFollowUpQuestions(data.follow_up_questions, isMs);

    const checkedLabel = isMs
      ? `${sources.length} dokumen rasmi disemak`
      : `${sources.length} official documents checked`;
    const scopeLabel = targetScope === "All" ? "All UUM" : targetScope;
    const docsFilterLabel = state.filterActive ? "Active Docs Only" : "All Docs (incl. Historical)";

    // Collapsed by default — no noisy developer plumbing above the answer
    const traceHtml =
      sources.length > 0
        ? `
      <details class="rag-steps-details">
        <summary class="rag-steps-summary">
          <div class="rag-summary-left">
            <span class="rag-step-badge">
              ${ICONS.academic}
              <span>${escapeHtml(checkedLabel)}</span>
            </span>
            <span>Scope: <strong>${escapeHtml(scopeLabel)}</strong></span>
          </div>
          <svg class="rag-steps-chevron" viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>
        </summary>
        <div class="rag-steps-list">
          <div class="rag-step-item">
            <div class="rag-step-query">
              <svg class="icon-svg-sm" viewBox="0 0 24 24"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
              <span>${escapeHtml(scopeLabel)} &bull; ${escapeHtml(docsFilterLabel)}</span>
            </div>
            <span class="rag-step-count">${sources.length} sources</span>
          </div>
        </div>
      </details>
    `
        : "";

    assistantTurn.innerHTML = `
      <div class="turn-assistant-meta">
        <span class="assistant-identity">${ICONS.academic}<span>UUM Guide</span></span>
        ${sources.length > 0 ? `<span class="assistant-engine-badge">${escapeHtml(checkedLabel)}</span>` : ""}
      </div>
      ${traceHtml}
      ${answerHtml}
      ${recoveryHtml}
      ${formsHtml}
      ${followUpsHtml}
    `;

    // Bind inline citation pills strictly to THIS turn's sources (multi-turn safe!)
    assistantTurn.querySelectorAll(".cite-pill").forEach((pill) => {
      pill.addEventListener("click", () => {
        const idx = parseInt(pill.dataset.srcIdx, 10);
        const page = parseInt(pill.dataset.page, 10) || 1;
        if (sources[idx]) {
          renderReferenceCards(sources);
          openDocumentInInspector({ ...sources[idx], page_number: page }, idx, true, true);
        }
      });
    });

    assistantTurn.querySelectorAll(".form-chip-preview").forEach((chip) => {
      chip.addEventListener("click", () => {
        const fid = chip.dataset.formId;
        const targetForm = linkedForms.find((f) => f.doc_id === fid);
        if (targetForm) {
          openDocumentInInspector(targetForm, null, true, true);
        }
      });
    });

    assistantTurn.querySelectorAll(".followup-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const nextQuery = btn.dataset.query;
        if (nextQuery) {
          triggerSearch(nextQuery, targetScope, { persistScope: false });
        }
      });
    });

    assistantTurn.querySelectorAll("[data-recover]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.dataset.recover;
        if (mode === "all") {
          state.activeScope = "All";
          syncScopeControls();
          triggerSearch(queryText, "All", { persistScope: true });
        } else if (mode === "historical") {
          state.filterActive = false;
          if (dom.btnActiveToggle) dom.btnActiveToggle.classList.remove("active");
          if (dom.activeToggleLabel) dom.activeToggleLabel.textContent = "All Docs (incl. Historical)";
          triggerSearch(queryText, targetScope, { persistScope: false });
        }
      });
    });

    if (opts.updateSourcesPanel !== false) {
      renderReferenceCards(sources);
      if (sources.length > 0) {
        const shouldAutoOpen = Boolean(opts.autoOpenDesktop) && isDesktopViewport();
        openDocumentInInspector(sources[0], 0, false, shouldAutoOpen);
        switchRightTab("refs");
      }
    }
  }

  // ==================== Multi-Turn Thread Persistence ====================
  function persistThreads() {
    if (state.threads.length > MAX_SAVED_THREADS) {
      state.threads.length = MAX_SAVED_THREADS;
    }
    try {
      localStorage.setItem("uum_threads", JSON.stringify(state.threads));
    } catch (_) {
      state.threads.length = Math.min(state.threads.length, 8);
      try {
        localStorage.setItem("uum_threads", JSON.stringify(state.threads));
      } catch (__) {}
    }
    renderThreadHistory();
  }

  function saveTurnToThreadHistory(query, scope, resData) {
    const turnRecord = {
      query,
      scope: resData.scope || scope || "All",
      response: {
        answer: resData.answer || "",
        provider: resData.provider || "",
        language: resData.language || "",
        sources: (resData.sources || []).map(compactSource).filter(Boolean),
        linked_forms: (resData.linked_forms || []).map(compactForm).filter(Boolean),
        follow_up_questions: Array.isArray(resData.follow_up_questions) ? resData.follow_up_questions.slice(0, 3) : [],
        scope: resData.scope || scope || "All",
      },
    };

    const nowLabel = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const existingIdx = state.threads.findIndex((t) => t.id === state.activeThreadId);

    if (existingIdx >= 0) {
      const existing = state.threads[existingIdx];
      existing.turns.push(turnRecord);
      if (existing.turns.length > 12) existing.turns = existing.turns.slice(-12);
      existing.updatedAt = nowLabel;
      existing.scope = turnRecord.scope;
      state.threads.splice(existingIdx, 1);
      state.threads.unshift(existing);
    } else {
      const thread = {
        id: state.activeThreadId || `th_${Date.now()}`,
        title: query.slice(0, 45) + (query.length > 45 ? "..." : ""),
        scope: turnRecord.scope,
        updatedAt: nowLabel,
        turns: [turnRecord],
      };
      state.activeThreadId = thread.id;
      state.threads.unshift(thread);
    }

    persistThreads();
  }

  function restoreSavedThread(th) {
    if (!th || !Array.isArray(th.turns) || th.turns.length === 0) return;
    hideAutoPredict();
    closeMobileSidebar();

    state.activeThreadId = th.id;
    state.activeThreadTitle = th.title || th.turns[0].query.slice(0, 50);
    state.lastQuery = th.turns[th.turns.length - 1].query;
    switchView("search");

    if (dom.welcomeHero) dom.welcomeHero.classList.add("hidden");
    dom.turnsContainer.replaceChildren();
    if (dom.queryInput) dom.queryInput.value = "";

    th.turns.forEach((turn, idx) => {
      const isLast = idx === th.turns.length - 1;
      const userTurn = document.createElement("div");
      userTurn.className = "turn-user";
      userTurn.innerHTML = `<div class="turn-user-bubble">${escapeHtml(turn.query)}</div>`;
      dom.turnsContainer.appendChild(userTurn);

      const assistantTurn = document.createElement("div");
      assistantTurn.className = "turn-assistant";
      dom.turnsContainer.appendChild(assistantTurn);

      renderAssistantTurn(assistantTurn, turn.query, turn.scope || "All", turn.response, {
        updateSourcesPanel: isLast,
        autoOpenDesktop: isLast,
      });
    });

    syncHeaderUI();
    dom.threadScrollArea.scrollTop = 0;
  }

  function renderThreadHistory() {
    if (!dom.threadsList) return;
    dom.threadsList.replaceChildren();
    state.threads.forEach((th) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "thread-item-btn";
      btn.innerHTML = `${ICONS.message}<span>${escapeHtml(th.title)}</span>`;
      btn.title = th.turns && th.turns[0] ? th.turns[0].query : th.title;
      btn.addEventListener("click", () => restoreSavedThread(th));
      dom.threadsList.appendChild(btn);
    });
  }

  // ==================== View Switcher (Ask UUM / Documents & Forms / Saved) ====================
  function switchView(viewKey) {
    state.activeView = viewKey;
    closeMobileSidebar();
    [dom.navSearch, dom.navCatalog, dom.navSaved].forEach((b) => b && b.classList.remove("active"));
    [dom.viewSearch, dom.viewCatalog, dom.viewSaved].forEach((v) => v && v.classList.add("hidden"));

    if (viewKey === "catalog") {
      if (dom.navCatalog) dom.navCatalog.classList.add("active");
      if (dom.viewCatalog) dom.viewCatalog.classList.remove("hidden");
      renderCatalogItems(false);
    } else if (viewKey === "saved") {
      if (dom.navSaved) dom.navSaved.classList.add("active");
      if (dom.viewSaved) dom.viewSaved.classList.remove("hidden");
      renderSavedList();
    } else {
      if (dom.navSearch) dom.navSearch.classList.add("active");
      if (dom.viewSearch) dom.viewSearch.classList.remove("hidden");
    }

    syncHeaderUI();
  }

  // ==================== Event Listeners ====================
  function bindEvents() {
    if (dom.themeLightBtn) dom.themeLightBtn.addEventListener("click", () => applyTheme("light"));
    if (dom.themeDarkBtn) dom.themeDarkBtn.addEventListener("click", () => applyTheme("dark"));

    if (dom.navSearch) dom.navSearch.addEventListener("click", () => switchView("search"));
    if (dom.navCatalog) dom.navCatalog.addEventListener("click", () => switchView("catalog"));
    if (dom.navSaved) dom.navSaved.addEventListener("click", () => switchView("saved"));

    if (dom.btnMobileMenu) dom.btnMobileMenu.addEventListener("click", toggleMobileSidebar);
    if (dom.sidebarBackdrop) dom.sidebarBackdrop.addEventListener("click", closeMobileSidebar);

    if (dom.btnCollapseSidebar) {
      dom.btnCollapseSidebar.addEventListener("click", () => {
        dom.sidebar.classList.toggle("collapsed");
      });
    }

    if (dom.btnToggleRightPane) {
      dom.btnToggleRightPane.addEventListener("click", () => {
        dom.rightPane.classList.toggle("collapsed");
      });
    }

    if (dom.btnCloseRightPane) {
      dom.btnCloseRightPane.addEventListener("click", () => {
        dom.rightPane.classList.add("collapsed");
      });
    }

    if (dom.tabBtnRefs) dom.tabBtnRefs.addEventListener("click", () => switchRightTab("refs"));
    if (dom.tabBtnViewer) dom.tabBtnViewer.addEventListener("click", () => switchRightTab("viewer"));
    if (dom.btnBackToRefs) dom.btnBackToRefs.addEventListener("click", () => switchRightTab("refs"));

    if (dom.btnScopeMenu && dom.scopePopover) {
      dom.btnScopeMenu.addEventListener("click", (e) => {
        e.stopPropagation();
        dom.scopePopover.classList.toggle("hidden");
      });
    }

    if (dom.btnClearScope) {
      dom.btnClearScope.addEventListener("click", () => {
        state.activeScope = "All";
        syncScopeControls();
      });
    }

    document.addEventListener("click", (e) => {
      if (dom.scopePopover && !dom.scopePopover.contains(e.target) && dom.btnScopeMenu && !dom.btnScopeMenu.contains(e.target)) {
        dom.scopePopover.classList.add("hidden");
      }
      if (dom.autoPredictMenu && !dom.autoPredictMenu.contains(e.target) && dom.queryInput && e.target !== dom.queryInput) {
        hideAutoPredict();
      }
    });

    // '/' keyboard shortcut to focus search composer from anywhere
    document.addEventListener("keydown", (e) => {
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      const tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (state.activeView !== "search") switchView("search");
      if (dom.queryInput) {
        e.preventDefault();
        dom.queryInput.focus();
      }
    });

    if (dom.btnActiveToggle) {
      dom.btnActiveToggle.addEventListener("click", () => {
        state.filterActive = !state.filterActive;
        dom.btnActiveToggle.classList.toggle("active", state.filterActive);
        if (dom.activeToggleLabel) {
          dom.activeToggleLabel.textContent = state.filterActive ? "Active Docs Only" : "All Docs (incl. Historical)";
        }
      });
    }

    if (dom.btnNewThread) {
      dom.btnNewThread.addEventListener("click", () => {
        state.activeThreadId = null;
        state.activeThreadTitle = "UUM Guide & Forms";
        state.lastQuery = "";
        state.activeScope = "All";
        dom.turnsContainer.replaceChildren();
        if (dom.welcomeHero) dom.welcomeHero.classList.remove("hidden");
        if (dom.queryInput) dom.queryInput.value = "";
        resetViewerPlaceholder();
        renderReferenceCards([]);
        switchRightTab("refs");
        if (dom.rightPane) dom.rightPane.classList.add("collapsed");
        syncScopeControls();
        switchView("search");
      });
    }

    if (dom.btnClearThreads) {
      dom.btnClearThreads.addEventListener("click", () => {
        state.threads = [];
        localStorage.removeItem("uum_threads");
        renderThreadHistory();
      });
    }

    // Add-only bookmark save for current turn's cited sources (never deletes existing bookmarks)
    if (dom.btnSaveThread) {
      dom.btnSaveThread.addEventListener("click", () => {
        if (!state.currentSources || state.currentSources.length === 0) return;
        let addedCount = 0;
        state.currentSources.forEach((s) => {
          if (saveItemIfNew(s)) addedCount += 1;
        });
        if (addedCount > 0) {
          persistSavedItems();
          renderReferenceCards(state.currentSources);
          showToast(`Saved ${addedCount} cited document${addedCount > 1 ? "s" : ""} to Saved`);
        } else {
          showToast("All cited sources are already in Saved");
        }
        dom.btnSaveThread.style.color = "var(--accent-gold)";
        setTimeout(() => (dom.btnSaveThread.style.color = ""), 1500);
      });
    }

    if (dom.btnCopyThread) {
      dom.btnCopyThread.addEventListener("click", () => {
        const lastAssistant = dom.turnsContainer.querySelector(".turn-assistant:last-child .llm-prose");
        if (lastAssistant && navigator.clipboard) {
          navigator.clipboard.writeText(lastAssistant.innerText).then(() => {
            if (dom.btnCopyLabel) dom.btnCopyLabel.textContent = "Copied!";
            showToast("Answer copied to clipboard");
            setTimeout(() => {
              if (dom.btnCopyLabel) dom.btnCopyLabel.textContent = "Copy Answer";
            }, 2000);
          }).catch(() => {});
        }
      });
    }

    function handleSearchSubmit() {
      const q = dom.queryInput ? dom.queryInput.value.trim() : "";
      if (q) {
        triggerSearch(q, state.activeScope, { persistScope: true });
      } else if (dom.queryInput) {
        dom.queryInput.focus();
        if (dom.searchForm) {
          dom.searchForm.classList.remove("shake");
          void dom.searchForm.offsetWidth;
          dom.searchForm.classList.add("shake");
        }
      }
    }

    if (dom.btnSubmitQuery) {
      dom.btnSubmitQuery.addEventListener("click", (e) => {
        e.preventDefault();
        handleSearchSubmit();
      });
    }

    if (dom.searchForm) {
      dom.searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        handleSearchSubmit();
      });
    }

    if (dom.queryInput) {
      dom.queryInput.addEventListener("input", updateAutoPredict);
      dom.queryInput.addEventListener("keydown", (e) => {
        const hasSuggestions = state.autoPredictItems && state.autoPredictItems.length > 0;
        if (hasSuggestions && e.key === "ArrowDown") {
          e.preventDefault();
          state.autoPredictIdx = (state.autoPredictIdx + 1) % state.autoPredictItems.length;
          renderAutoPredict();
          return;
        }
        if (hasSuggestions && e.key === "ArrowUp") {
          e.preventDefault();
          state.autoPredictIdx = (state.autoPredictIdx - 1 + state.autoPredictItems.length) % state.autoPredictItems.length;
          renderAutoPredict();
          return;
        }
        if (hasSuggestions && e.key === "Tab") {
          const picked = state.autoPredictItems[state.autoPredictIdx >= 0 ? state.autoPredictIdx : 0];
          if (picked) {
            e.preventDefault();
            dom.queryInput.value = picked.query;
            hideAutoPredict();
          }
          return;
        }
        if (hasSuggestions && e.key === "Escape") {
          hideAutoPredict();
          return;
        }
        if (e.key === "Enter" && !e.shiftKey) {
          if (e.isComposing || e.keyCode === 229) return;
          e.preventDefault();
          if (hasSuggestions && state.autoPredictIdx >= 0) {
            const picked = state.autoPredictItems[state.autoPredictIdx];
            hideAutoPredict();
            triggerSearch(picked.query, picked.scope !== "All" ? picked.scope : state.activeScope, { persistScope: false });
            return;
          }
          hideAutoPredict();
          handleSearchSubmit();
        }
      });
    }

    if (dom.catSearchInput) dom.catSearchInput.addEventListener("input", () => renderCatalogItems(true));
    if (dom.catTypeSelect) dom.catTypeSelect.addEventListener("change", () => renderCatalogItems(true));
    if (dom.catCollegeSelect) dom.catCollegeSelect.addEventListener("change", () => renderCatalogItems(true));
    if (dom.btnCatalogLoadMore) {
      dom.btnCatalogLoadMore.addEventListener("click", () => {
        state.catalogVisibleLimit += CATALOG_PAGE_SIZE;
        renderCatalogItems(false);
      });
    }
  }

  // ==================== Initialization ====================
  function init() {
    applyTheme(state.activeTheme);
    renderWelcomeStarters();
    renderThreadHistory();
    renderSavedList();
    updateSavedBadge();
    syncScopeControls();
    bindEvents();
    loadCatalog();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
