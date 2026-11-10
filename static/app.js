/**
 * LLM UUM — Academic & Circular Intelligence Frontend Engine
 * Handles 3-Pane Navigation, RAG Querying, Structured Academic Synthesis Rendering,
 * Inline Interactive Citation Pills, Reference Cards, and Live PDF/Document Inspector.
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
  ];

  const BENCHMARKS = [
    {
      role: "Student",
      title: "SOC IT Degree Curriculum",
      scope: "CAS",
      query: "What are the core course and credit requirements for Bachelor of Science in Information Technology with Honours at SOC?",
    },
    {
      role: "Student",
      title: "HEA Minor Course Registration",
      scope: "HEA",
      query: "Apakah prosedur dan borang yang diperlukan untuk permohonan pendaftaran kursus Minor di HEA?",
    },
    {
      role: "Postgrad",
      title: "Postgraduate Thesis Notice (SAPSP)",
      scope: "CAS",
      query: "Which form should a postgraduate student submit for Notice of Intention to Submit Research Proposal in SAPSP?",
    },
    {
      role: "Lecturer / GRA",
      title: "GRA Appointment & Allowances",
      scope: "RMC",
      query: "What are the requirements and allowance ceilings to appoint a Graduate Research Assistant (GRA)?",
    },
    {
      role: "Lecturer / Staff",
      title: "External Speaker Honorarium",
      scope: "Bendahari",
      query: "Berapakah kadar bayaran saguhati penceramah luar daripada sektor swasta mengikut Pekeliling Bendahari?",
    },
    {
      role: "Staff / PTJ",
      title: "University Asset Disposal",
      scope: "Bendahari",
      query: "Apakah proses dan borang yang diperlukan untuk pelupusan aset universiti yang rosak?",
    },
  ];

  // SVG Icon Templates
  const ICONS = {
    doc: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    starFilled: '<svg class="icon-svg-sm" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    starOutline: '<svg class="icon-svg-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    check: '<svg class="icon-svg" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>',
    copy: '<svg class="icon-svg" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    message: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    close: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    academic: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
    warning: '<svg class="icon-svg-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  };

  // ==================== Application State ====================
  const state = {
    activeScope: "All",
    filterActive: true,
    activeTheme: localStorage.getItem("uum_theme") || "dark",
    activeView: "search", // 'search', 'catalog', 'saved'
    threads: JSON.parse(localStorage.getItem("uum_threads") || "[]"),
    savedItems: JSON.parse(localStorage.getItem("uum_saved_items") || "[]"),
    catalogItems: [],
    catalogStats: {},
    currentSources: [],
    currentLinkedForms: [],
    currentDocInViewer: null,
    activeCardIndex: null,
    isSubmitting: false,
  };

  // ==================== DOM Selectors ====================
  const dom = {
    html: document.documentElement,
    themeLightBtn: document.getElementById("btnThemeLight"),
    themeDarkBtn: document.getElementById("btnThemeDark"),
    sidebar: document.getElementById("leftSidebar"),
    btnCollapseSidebar: document.getElementById("btnCollapseSidebar"),
    scenariosCollapse: document.getElementById("scenariosCollapse"),
    btnNewThread: document.getElementById("btnNewThread"),
    btnClearThreads: document.getElementById("btnClearThreads"),
    threadsList: document.getElementById("threadsList"),
    benchmarkList: document.getElementById("benchmarkList"),
    kbStatsFooter: document.getElementById("kbStatsFooter"),
    badgeTotalDocs: document.getElementById("badgeTotalDocs"),
    badgeSavedCount: document.getElementById("badgeSavedCount"),
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
    queryInput: document.getElementById("queryInput"),
    btnSubmitQuery: document.getElementById("btnSubmitQuery"),
    btnQuickPrompts: document.getElementById("btnQuickPrompts"),
    quickPromptsPopover: document.getElementById("quickPromptsPopover"),
    quickPromptsList: document.getElementById("quickPromptsList"),
    btnScopeMenu: document.getElementById("btnScopeMenu"),
    scopeBtnLabel: document.getElementById("scopeBtnLabel"),
    scopePopover: document.getElementById("scopePopover"),
    scopePopoverList: document.getElementById("scopePopoverList"),
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
    catalogCountBar: document.getElementById("catalogCountBar"),
    catalogList: document.getElementById("catalogList"),
    savedList: document.getElementById("savedList"),
  };

  // ==================== Security Utilities ====================
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // ==================== Theme Controller ====================
  function applyTheme(theme) {
    state.activeTheme = theme;
    dom.html.setAttribute("data-theme", theme);
    localStorage.setItem("uum_theme", theme);
    if (theme === "dark") {
      dom.themeDarkBtn.classList.add("active");
      dom.themeLightBtn.classList.remove("active");
    } else {
      dom.themeLightBtn.classList.add("active");
      dom.themeDarkBtn.classList.remove("active");
    }
  }

  // ==================== Markdown & Citation Pill Formatter ====================
  function renderLLMUUMMarkdown(rawText, sources) {
    if (!rawText) return "";

    // Step 1: Escape HTML to prevent injection
    let text = escapeHtml(rawText);

    // Step 2: Normalize single-line compressed lists like "1. Item 2. Item 3. Item"
    text = text.replace(/(\d+\.\s+[^\n]+?)(?=\s+\d+\.\s+)/g, "$1\n");

    // Step 3: Key Takeaway / Rumusan Utama highlight block
    text = text.replace(
      /(?:\*\*Key Takeaway:\*\*|\*\*Rumusan Utama:\*\*)\s*([^\n]+(?:\n[^\n#]+)?)/i,
      '<div class="key-takeaway-box"><strong>Key Takeaway</strong>$1</div>\n\n'
    );

    // Step 4: Transform Citation Markers like [Source 1], [Source 1 p.1], [Source 1, Page 4], [1]
    text = text.replace(
      /\[(?:Source\s*(\d+)(?:,?\s*(?:Page|p\.?)\s*(\d+))?|(\d+))\]/gi,
      (match, sNum, pNum, bareNum) => {
        const srcIdx = parseInt(sNum || bareNum, 10) - 1;
        const src = sources && sources[srcIdx] ? sources[srcIdx] : null;
        const page = pNum || (src ? src.page_number : 1);
        const docName = src ? (src.title || src.circular_ref_no || `Source ${srcIdx + 1}`) : `Source ${srcIdx + 1}`;
        const pillText = page ? `Source ${srcIdx + 1} · p.${page}` : `Source ${srcIdx + 1}`;
        const titleTooltip = escapeHtml(`${docName} (Page ${page}) — Click to inspect`);
        return `<button type="button" class="cite-pill" data-src-idx="${srcIdx}" data-page="${page}" title="${titleTooltip}">${ICONS.doc}<span>${escapeHtml(pillText)}</span></button>`;
      }
    );

    // Step 5: Code backticks `code`
    text = text.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // Step 6: Horizontal rules
    text = text.replace(/^(?:---|___|\*\*\*)$/gm, "<hr />");

    // Step 7: Markdown headings (#####, ####, ###, ##, #)
    text = text.replace(/^#####\s+(.*$)/gim, "<h4>$1</h4>");
    text = text.replace(/^####\s+(.*$)/gim, "<h4>$1</h4>");
    text = text.replace(/^###\s+(.*$)/gim, "<h3>$1</h3>");
    text = text.replace(/^##\s+(.*$)/gim, "<h2>$1</h2>");
    text = text.replace(/^#\s+(.*$)/gim, "<h2>$1</h2>");

    // Step 8: Bold and Italics
    text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // Step 9: Lists (unordered * / - and ordered 1.)
    text = text.replace(/^\s*[-*]\s+(.*$)/gim, "<li>$1</li>");
    text = text.replace(/^\s*(\d+)\.\s+(.*$)/gim, "<li>$2</li>");

    // Wrap consecutive <li> into <ul>
    text = text.replace(/(<li>[\s\S]*?<\/li>)/gm, "<ul>$1</ul>");
    text = text.replace(/<\/ul>\s*<ul>/g, "");

    // Step 10: Paragraphs (split by double newlines)
    const blocks = text.split(/\n{2,}/);
    const htmlBlocks = blocks.map((b) => {
      const trimmed = b.trim();
      if (!trimmed) return "";
      if (
        trimmed.startsWith("<h2") ||
        trimmed.startsWith("<h3") ||
        trimmed.startsWith("<h4") ||
        trimmed.startsWith("<ul") ||
        trimmed.startsWith("<ol") ||
        trimmed.startsWith("<div") ||
        trimmed.startsWith("<hr")
      ) {
        return trimmed;
      }
      return `<p>${trimmed.replace(/\n/g, "<br />")}</p>`;
    });

    return `<div class="llm-prose">${htmlBlocks.join("\n")}</div>`;
  }

  const renderConsensusMarkdown = renderLLMUUMMarkdown;

  // ==================== Scope & Popover Controllers ====================
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
        if (dom.scopeBtnLabel) dom.scopeBtnLabel.textContent = sc.id === "All" ? "Scope" : sc.id;
        if (dom.activeScopeBadge) dom.activeScopeBadge.textContent = sc.label;
        dom.scopePopover.classList.add("hidden");
        renderScopePopovers();
      });
      dom.scopePopoverList.appendChild(btn);
    });
  }

  function renderQuickPromptsPopover() {
    if (!dom.quickPromptsList) return;
    dom.quickPromptsList.replaceChildren();

    BENCHMARKS.forEach((bm) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "popover-item";
      btn.innerHTML = `
        <span class="popover-item-title">${escapeHtml(bm.title)}</span>
        <span class="popover-item-sub">${escapeHtml(bm.role)} &bull; ${escapeHtml(bm.scope)}</span>
      `;
      btn.addEventListener("click", () => {
        dom.quickPromptsPopover.classList.add("hidden");
        triggerSearch(bm.query, bm.scope);
      });
      dom.quickPromptsList.appendChild(btn);
    });
  }

  // ==================== Benchmarks & Hero Starters ====================
  function renderBenchmarks() {
    if (dom.benchmarkList) dom.benchmarkList.replaceChildren();
    if (dom.heroStartersGrid) dom.heroStartersGrid.replaceChildren();

    BENCHMARKS.forEach((bm) => {
      // Sidebar button inside the collapsed scenarios drawer
      if (dom.benchmarkList) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "benchmark-btn";
        btn.textContent = bm.title;
        btn.title = bm.query;
        btn.addEventListener("click", () => triggerSearch(bm.query, bm.scope));
        dom.benchmarkList.appendChild(btn);
      }

      // Center stacked scenario pills (mirrors the reference screenshot)
      if (dom.heroStartersGrid) {
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "stacked-scenario-pill";
        pill.innerHTML = `
          <div class="scenario-pill-left">
            <span class="scenario-role-tag">${escapeHtml(bm.role || "UUM")}</span>
            <span class="scenario-title-text">${escapeHtml(bm.title)}</span>
          </div>
          <div class="scenario-arrow-circle" aria-hidden="true">
            <svg class="icon-svg-sm" viewBox="0 0 24 24"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>
          </div>
        `;
        pill.addEventListener("click", () => triggerSearch(bm.query, bm.scope));
        dom.heroStartersGrid.appendChild(pill);
      }
    });
  }

  // ==================== References Panel Controller ====================
  function renderReferenceCards(sources) {
    state.currentSources = sources || [];
    const count = state.currentSources.length;
    if (dom.refsCountPill) dom.refsCountPill.textContent = count;
    if (dom.headerRefsCount) dom.headerRefsCount.textContent = count;
    if (dom.rightMetaLabel) dom.rightMetaLabel.textContent = `${count} Sources Cited`;
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

      const isSaved = state.savedItems.some((s) => s.chunk_id === src.chunk_id);
      const fmtClass = (src.file_format || "PDF").toLowerCase();

      card.innerHTML = `
        <div class="ref-card-header">
          <div class="ref-badge-num">${idx + 1}</div>
          <div class="ref-title-box">
            <h4 class="ref-title">${escapeHtml(src.title || src.circular_ref_no)}</h4>
            <div class="ref-dept">${escapeHtml(src.department || src.college)} &bull; ${escapeHtml(src.section_heading || "Official Clause")}</div>
          </div>
          <button type="button" class="ref-save-btn ${isSaved ? "saved" : ""}" data-idx="${idx}" title="${isSaved ? "Remove Bookmark" : "Save to My Library"}">
            ${isSaved ? ICONS.starFilled : ICONS.starOutline}
          </button>
        </div>

        <div class="ref-quote-box">
          "${escapeHtml(src.chunk_text ? src.chunk_text.slice(0, 240) : "")}..."
        </div>

        <div class="ref-card-footer">
          <div class="ref-footer-left">
            <span class="fmt-badge ${fmtClass}">${escapeHtml(src.file_format || "PDF")}</span>
            <span class="ref-pill-tag">Page ${escapeHtml(String(src.page_number || 1))}</span>
            ${src.required_forms && src.required_forms !== "-" ? `<span class="ref-pill-tag" title="${escapeHtml(src.required_forms)}">Form Attached</span>` : ""}
          </div>
          <button type="button" class="btn-inspect-doc" data-idx="${idx}">
            <span>Inspect &rarr;</span>
          </button>
        </div>
      `;

      // Save/Bookmark handler
      card.querySelector(".ref-save-btn").addEventListener("click", (e) => {
        e.stopPropagation();
        toggleSaveItem(src);
        renderReferenceCards(state.currentSources);
      });

      // Inspect document handler
      card.querySelector(".btn-inspect-doc").addEventListener("click", () => {
        openDocumentInInspector(src, idx);
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
  function openDocumentInInspector(docMeta, cardIdx = null) {
    if (!docMeta) return;
    state.currentDocInViewer = docMeta;
    state.activeCardIndex = cardIdx;

    if (cardIdx !== null) {
      highlightReferenceCard(cardIdx);
    }

    // Ensure right pane is expanded
    if (dom.rightPane) dom.rightPane.classList.remove("collapsed");

    // Switch right panel to Document Viewer tab
    switchRightTab("viewer");

    const docId = docMeta.doc_id || docMeta.circular_id;
    const title = docMeta.title || docMeta.circular_ref_no || "UUM Document";
    const fmt = (docMeta.file_format || "PDF").toUpperCase();
    const page = docMeta.page_number || 1;

    dom.viewerDocTitle.textContent = title;
    dom.viewerDocSub.textContent = `${docMeta.department || docMeta.college || "UUM"} • Format: ${fmt} • Page ${page}`;
    dom.viewerActions.replaceChildren();

    const isSaved = state.savedItems.some((s) => s.chunk_id === docMeta.chunk_id || s.doc_id === docId);
    const btnSave = document.createElement("button");
    btnSave.type = "button";
    btnSave.className = `btn-action-icon ${isSaved ? "saved" : ""}`;
    btnSave.title = isSaved ? "Remove Bookmark" : "Save to My Library";
    btnSave.innerHTML = isSaved ? ICONS.starFilled : ICONS.starOutline;
    btnSave.addEventListener("click", () => {
      toggleSaveItem(docMeta);
      openDocumentInInspector(docMeta, cardIdx);
    });
    dom.viewerActions.appendChild(btnSave);

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
            <p>${escapeHtml(fmt)} Document • ${escapeHtml(docMeta.department || "")}</p>
          </div>
          <a href="/api/document/${encodeURIComponent(docId)}/download" class="btn-download-primary" download>
            <span>Download ${escapeHtml(fmt)}</span>
          </a>
        </div>
        <div class="doc-sections-list">
          <div class="doc-section-card">
            <div class="doc-section-heading">Supporting Excerpt (Clause)</div>
            <div class="doc-section-body">${escapeHtml(docMeta.chunk_text || "No preview text available.")}</div>
          </div>
        </div>
      `;
      dom.viewerBody.appendChild(container);
    }
  }

  function switchRightTab(tabKey) {
    if (tabKey === "viewer") {
      dom.tabBtnViewer.classList.add("active");
      dom.tabBtnRefs.classList.remove("active");
      dom.panelViewer.classList.remove("hidden");
      dom.panelRefs.classList.add("hidden");
    } else {
      dom.tabBtnRefs.classList.add("active");
      dom.tabBtnViewer.classList.remove("active");
      dom.panelRefs.classList.remove("hidden");
      dom.panelViewer.classList.add("hidden");
    }
  }

  // ==================== Saved Items / Bookmarks Controller ====================
  function toggleSaveItem(item) {
    const key = item.chunk_id || item.doc_id;
    const existingIdx = state.savedItems.findIndex((s) => (s.chunk_id || s.doc_id) === key);
    if (existingIdx >= 0) {
      state.savedItems.splice(existingIdx, 1);
    } else {
      state.savedItems.push({
        ...item,
        saved_at: new Date().toISOString(),
      });
    }
    localStorage.setItem("uum_saved_items", JSON.stringify(state.savedItems));
    updateSavedBadge();
    renderSavedList();
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
          <p>Click the bookmark star on any Reference Card to save important clauses and forms here for quick access.</p>
        </div>
      `;
      return;
    }

    state.savedItems.forEach((item, idx) => {
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
        openDocumentInInspector(item);
      });

      dom.savedList.appendChild(card);
    });
  }

  // ==================== Catalog Library Controller ====================
  function loadCatalog() {
    fetch("/api/catalog")
      .then((res) => res.json())
      .then((data) => {
        state.catalogItems = data.items || [];
        state.catalogStats = data.stats || {};
        if (dom.badgeTotalDocs) dom.badgeTotalDocs.textContent = state.catalogStats.total_documents || state.catalogItems.length;
        if (dom.kbStatsFooter) {
          dom.kbStatsFooter.textContent = `Indexed: ${state.catalogItems.length} official documents • CAS, COB, COLGIS, Shared`;
        }
        renderCatalogItems();
      })
      .catch((err) => {
        console.error("Failed to load catalog:", err);
      });
  }

  function renderCatalogItems() {
    if (!dom.catalogList) return;
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

    if (dom.catalogCountBar) dom.catalogCountBar.textContent = `Showing ${filtered.length} of ${state.catalogItems.length} items`;
    dom.catalogList.replaceChildren();

    filtered.slice(0, 100).forEach((item) => {
      const row = document.createElement("div");
      row.className = "catalog-item-card";
      row.innerHTML = `
        <div class="cat-item-left">
          <div class="cat-item-title">${escapeHtml(item.title || item.circular_ref_no)}</div>
          <div class="cat-item-meta">
            <span>${escapeHtml(item.department || item.college || "UUM")}</span>
            <span>${escapeHtml(item.doc_type || "")}</span>
            ${item.page_count ? `<span>${escapeHtml(String(item.page_count))} pages</span>` : ""}
          </div>
        </div>
        <div class="cat-item-right">
          <span class="fmt-badge ${escapeHtml((item.file_format || "PDF").toLowerCase())}">${escapeHtml(item.file_format || "PDF")}</span>
        </div>
      `;
      row.addEventListener("click", () => {
        openDocumentInInspector(item);
      });
      dom.catalogList.appendChild(row);
    });
  }

  // ==================== Search & RAG Flow ====================
  function triggerSearch(queryText, scopeOverride = null) {
    if (!queryText || state.isSubmitting) return;

    const targetScope = scopeOverride || state.activeScope;
    state.activeScope = targetScope;
    if (dom.scopeBtnLabel) dom.scopeBtnLabel.textContent = targetScope === "All" ? "Scope" : targetScope;
    if (dom.activeScopeBadge) dom.activeScopeBadge.textContent = targetScope === "All" ? "All UUM" : targetScope;
    renderScopePopovers();

    // Switch view to search if on catalog
    switchView("search");

    dom.queryInput.value = queryText;
    dom.welcomeHero.classList.add("hidden");
    dom.currentThreadTitle.textContent = queryText.slice(0, 50) + (queryText.length > 50 ? "..." : "");

    // Append User Bubble
    const userTurn = document.createElement("div");
    userTurn.className = "turn-user";
    userTurn.innerHTML = `<div class="turn-user-bubble">${escapeHtml(queryText)}</div>`;
    dom.turnsContainer.appendChild(userTurn);

    // Append Assistant Loading Skeleton
    const assistantTurn = document.createElement("div");
    assistantTurn.className = "turn-assistant";
    assistantTurn.innerHTML = `
      <div class="turn-assistant-meta">
        <span class="assistant-identity">${ICONS.academic}<span>LLM UUM</span></span>
        <span class="assistant-engine-badge"><span class="spinner-inline"></span> Searching 689 documents...</span>
      </div>
      <div class="llm-prose">
        <p>Synthesizing verified rules across circulars, handbooks, and official forms...</p>
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
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        state.isSubmitting = false;
        dom.btnSubmitQuery.disabled = false;

        const answerHtml = renderLLMUUMMarkdown(data.answer, data.sources);
        const formsHtml = renderLinkedFormsChips(data.linked_forms);

        // Collapsible RAG retrieval trace (mirrors reference screenshot steps)
        const ragStepsHtml = `
          <details class="rag-steps-details" open>
            <summary class="rag-steps-summary">
              <div class="rag-summary-left">
                <span class="rag-step-badge">
                  ${ICONS.academic}
                  <span>Hybrid RAG</span>
                </span>
                <span>Retrieval &middot; <strong>${data.sources.length} sources</strong> retrieved</span>
              </div>
              <svg class="rag-steps-chevron" viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>
            </summary>
            <div class="rag-steps-list">
              <div class="rag-step-item">
                <div class="rag-step-query">
                  <svg class="icon-svg-sm" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                  <span>${escapeHtml(queryText)}</span>
                </div>
                <span class="rag-step-count">${data.sources.length} verified chunks</span>
              </div>
              <div class="rag-step-item">
                <div class="rag-step-query">
                  <svg class="icon-svg-sm" viewBox="0 0 24 24"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
                  <span>Scope: ${escapeHtml(targetScope)} &bull; ${state.filterActive ? "2024–2027 Handbooks" : "All Sessions"}</span>
                </div>
                <span class="rag-step-count">${escapeHtml(data.provider || "Gemini Flash")}</span>
              </div>
            </div>
          </details>
        `;

        assistantTurn.innerHTML = `
          <div class="turn-assistant-meta">
            <span class="assistant-identity">${ICONS.academic}<span>LLM UUM</span></span>
            <span class="assistant-engine-badge">Grounded in ${data.sources.length} sources &bull; ${escapeHtml(data.provider || "Gemini Flash")}</span>
          </div>
          ${ragStepsHtml}
          ${answerHtml}
          ${formsHtml}
        `;

        // Wire citation pills inside the assistant response
        assistantTurn.querySelectorAll(".cite-pill").forEach((pill) => {
          pill.addEventListener("click", () => {
            const idx = parseInt(pill.dataset.srcIdx, 10);
            if (data.sources && data.sources[idx]) {
              openDocumentInInspector(data.sources[idx], idx);
            }
          });
        });

        // Wire form chips
        assistantTurn.querySelectorAll(".form-chip-btn").forEach((chip) => {
          chip.addEventListener("click", () => {
            const fid = chip.dataset.formId;
            const targetForm = data.linked_forms.find((f) => f.doc_id === fid);
            if (targetForm) {
              openDocumentInInspector(targetForm);
            }
          });
        });

        // Update Right References Pane
        renderReferenceCards(data.sources);

        // Auto-open first cited source in Document Inspector if available
        if (data.sources && data.sources.length > 0) {
          openDocumentInInspector(data.sources[0], 0);
          switchRightTab("refs"); // Keep on references tab initially so user sees the cards
        }

        saveThreadHistory(queryText, data);
        dom.threadScrollArea.scrollTop = dom.threadScrollArea.scrollHeight;
      })
      .catch((err) => {
        state.isSubmitting = false;
        dom.btnSubmitQuery.disabled = false;
        assistantTurn.innerHTML = `
          <div class="turn-assistant-meta">
            <span class="assistant-identity">${ICONS.warning}<span>Error</span></span>
          </div>
          <div class="llm-prose">
            <p>Unable to retrieve answers: ${escapeHtml(err.message)}. Please check that the server is running on localhost:8000.</p>
          </div>
        `;
      });
  }

  function renderLinkedFormsChips(forms) {
    if (!forms || forms.length === 0) return "";
    const chips = forms
      .map(
        (f) => `
        <button type="button" class="form-chip-btn" data-form-id="${escapeHtml(f.doc_id)}" title="Inspect / Download Form">
          <span class="form-chip-icon">${ICONS.doc}</span>
          <span>${escapeHtml(f.code || f.title)}</span>
          <span class="fmt-badge ${escapeHtml((f.file_format || "PDF").toLowerCase())}">${escapeHtml(f.file_format || "PDF")}</span>
        </button>
      `
      )
      .join("");

    return `
      <div class="action-forms-bar">
        <div class="action-forms-header">Official Forms &amp; Action Templates Checklist:</div>
        <div class="forms-chips-grid">${chips}</div>
      </div>
    `;
  }

  function saveThreadHistory(query, resData) {
    const thread = {
      id: "th_" + Date.now(),
      title: query.slice(0, 45) + (query.length > 45 ? "..." : ""),
      query: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    state.threads.unshift(thread);
    if (state.threads.length > 25) state.threads.pop();
    localStorage.setItem("uum_threads", JSON.stringify(state.threads));
    renderThreadHistory();
  }

  function renderThreadHistory() {
    if (!dom.threadsList) return;
    dom.threadsList.replaceChildren();
    state.threads.forEach((th) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "thread-item-btn";
      btn.innerHTML = `${ICONS.message}<span>${escapeHtml(th.title)}</span>`;
      btn.title = th.query;
      btn.addEventListener("click", () => triggerSearch(th.query));
      dom.threadsList.appendChild(btn);
    });
  }

  // ==================== View Switcher (Search / Catalog / Saved) ====================
  function switchView(viewKey) {
    state.activeView = viewKey;
    [dom.navSearch, dom.navCatalog, dom.navSaved].forEach((b) => b && b.classList.remove("active"));
    [dom.viewSearch, dom.viewCatalog, dom.viewSaved].forEach((v) => v && v.classList.add("hidden"));

    if (viewKey === "catalog") {
      if (dom.navCatalog) dom.navCatalog.classList.add("active");
      if (dom.viewCatalog) dom.viewCatalog.classList.remove("hidden");
      renderCatalogItems();
    } else if (viewKey === "saved") {
      if (dom.navSaved) dom.navSaved.classList.add("active");
      if (dom.viewSaved) dom.viewSaved.classList.remove("hidden");
      renderSavedList();
    } else {
      if (dom.navSearch) dom.navSearch.classList.add("active");
      if (dom.viewSearch) dom.viewSearch.classList.remove("hidden");
    }
  }

  // ==================== Event Listeners ====================
  function bindEvents() {
    // Theme buttons
    if (dom.themeLightBtn) dom.themeLightBtn.addEventListener("click", () => applyTheme("light"));
    if (dom.themeDarkBtn) dom.themeDarkBtn.addEventListener("click", () => applyTheme("dark"));

    // Sidebar navigation
    if (dom.navSearch) dom.navSearch.addEventListener("click", () => switchView("search"));
    if (dom.navCatalog) dom.navCatalog.addEventListener("click", () => switchView("catalog"));
    if (dom.navSaved) dom.navSaved.addEventListener("click", () => switchView("saved"));

    // Toggle / Collapse Sidebar via Consensus-Style Rail Button
    if (dom.btnCollapseSidebar) {
      dom.btnCollapseSidebar.addEventListener("click", () => {
        dom.sidebar.classList.toggle("collapsed");
      });
    }

    // Toggle Right Pane
    if (dom.btnToggleRightPane) {
      dom.btnToggleRightPane.addEventListener("click", () => {
        dom.rightPane.classList.toggle("collapsed");
      });
    }

    // Close Right Pane
    if (dom.btnCloseRightPane) {
      dom.btnCloseRightPane.addEventListener("click", () => {
        dom.rightPane.classList.add("collapsed");
      });
    }

    // Right Pane Tab buttons
    if (dom.tabBtnRefs) dom.tabBtnRefs.addEventListener("click", () => switchRightTab("refs"));
    if (dom.tabBtnViewer) dom.tabBtnViewer.addEventListener("click", () => switchRightTab("viewer"));
    if (dom.btnBackToRefs) dom.btnBackToRefs.addEventListener("click", () => switchRightTab("refs"));

    // Quick Prompts Popover Toggle
    if (dom.btnQuickPrompts && dom.quickPromptsPopover) {
      dom.btnQuickPrompts.addEventListener("click", (e) => {
        e.stopPropagation();
        if (dom.scopePopover) dom.scopePopover.classList.add("hidden");
        dom.quickPromptsPopover.classList.toggle("hidden");
      });
    }

    // Scope Popover Toggle
    if (dom.btnScopeMenu && dom.scopePopover) {
      dom.btnScopeMenu.addEventListener("click", (e) => {
        e.stopPropagation();
        if (dom.quickPromptsPopover) dom.quickPromptsPopover.classList.add("hidden");
        dom.scopePopover.classList.toggle("hidden");
      });
    }

    // Close popovers on click outside
    document.addEventListener("click", (e) => {
      if (dom.quickPromptsPopover && !dom.quickPromptsPopover.contains(e.target) && dom.btnQuickPrompts && !dom.btnQuickPrompts.contains(e.target)) {
        dom.quickPromptsPopover.classList.add("hidden");
      }
      if (dom.scopePopover && !dom.scopePopover.contains(e.target) && dom.btnScopeMenu && !dom.btnScopeMenu.contains(e.target)) {
        dom.scopePopover.classList.add("hidden");
      }
    });

    // Active Sessions Filter Toggle Pill
    if (dom.btnActiveToggle) {
      dom.btnActiveToggle.addEventListener("click", () => {
        state.filterActive = !state.filterActive;
        dom.btnActiveToggle.classList.toggle("active", state.filterActive);
        if (dom.activeToggleLabel) {
          dom.activeToggleLabel.textContent = state.filterActive ? "Current Sessions (2024–2027)" : "All Sessions (incl. Historical)";
        }
      });
    }

    // New Thread button
    if (dom.btnNewThread) {
      dom.btnNewThread.addEventListener("click", () => {
        dom.turnsContainer.replaceChildren();
        dom.welcomeHero.classList.remove("hidden");
        dom.currentThreadTitle.textContent = "New Thread";
        dom.queryInput.value = "";
        renderReferenceCards([]);
        switchRightTab("refs");
        switchView("search");
      });
    }

    // Clear Threads
    if (dom.btnClearThreads) {
      dom.btnClearThreads.addEventListener("click", () => {
        state.threads = [];
        localStorage.removeItem("uum_threads");
        renderThreadHistory();
      });
    }

    // Bookmark / Save current thread
    if (dom.btnSaveThread) {
      dom.btnSaveThread.addEventListener("click", () => {
        const lastTurn = dom.turnsContainer.querySelector(".turn-assistant:last-child");
        if (lastTurn && state.currentSources && state.currentSources.length > 0) {
          state.currentSources.forEach((s) => toggleSaveItem(s));
          dom.btnSaveThread.style.color = "var(--accent-gold)";
          setTimeout(() => (dom.btnSaveThread.style.color = ""), 1500);
        }
      });
    }

    // Copy answer synthesis
    if (dom.btnCopyThread) {
      dom.btnCopyThread.addEventListener("click", () => {
        const lastAssistant = dom.turnsContainer.querySelector(".turn-assistant:last-child .llm-prose");
        if (lastAssistant) {
          navigator.clipboard.writeText(lastAssistant.innerText);
          if (dom.btnCopyLabel) dom.btnCopyLabel.textContent = "Copied!";
          setTimeout(() => {
            if (dom.btnCopyLabel) dom.btnCopyLabel.textContent = "Copy Answer";
          }, 2000);
        }
      });
    }

    // Search Form & Direct Submit Button Wiring
    function handleSearchSubmit() {
      const q = dom.queryInput ? dom.queryInput.value.trim() : "";
      if (q) {
        triggerSearch(q);
      } else if (BENCHMARKS && BENCHMARKS.length > 0) {
        // If empty, auto-populate with the first benchmark scenario and run immediately
        const topBm = BENCHMARKS[0];
        dom.queryInput.value = topBm.query;
        triggerSearch(topBm.query, topBm.scope);
      } else {
        dom.queryInput.focus();
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

    // Textarea Enter key handling (IME-safe)
    if (dom.queryInput) {
      dom.queryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          if (e.isComposing || e.keyCode === 229) return;
          e.preventDefault();
          handleSearchSubmit();
        }
      });
    }

    // Catalog filtering
    if (dom.catSearchInput) dom.catSearchInput.addEventListener("input", renderCatalogItems);
    if (dom.catTypeSelect) dom.catTypeSelect.addEventListener("change", renderCatalogItems);
    if (dom.catCollegeSelect) dom.catCollegeSelect.addEventListener("change", renderCatalogItems);
  }

  // ==================== Initialization ====================
  function init() {
    applyTheme(state.activeTheme);
    renderScopePopovers();
    renderQuickPromptsPopover();
    renderBenchmarks();
    renderThreadHistory();
    renderSavedList();
    updateSavedBadge();
    bindEvents();
    loadCatalog();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
