# TODO: PDF Viewer Troubleshooting & Enhancements (Abbas)

**Date**: 2026-11-10  
**Author**: Ahmad Abbas  
**Status**: Pending Investigation & Fix Tomorrow  

---

## Issue Description
The in-app PDF document inspector in the Right Pane (`#panelViewer`) is currently not displaying certain PDF previews reliably.

## Current Setup
1. **Frontend**:
   - `openDocumentInInspector(docMeta, cardIdx)` in `static/app.js` creates an `<iframe>` pointing to:
     ```html
     <iframe class="pdf-iframe" src="/api/document/{doc_id}/preview#page={page}"></iframe>
     ```
2. **Backend**:
   - `api_serve_file()` in `web_app.py` resolves the `doc_id` from `UUMAssistant().doc_registry` and serves the file using Starlette's `FileResponse` with `media_type="application/pdf"` and `Content-Disposition="inline"`.

## Areas to Investigate & Fix Tomorrow
1. **File Path Resolution**:
   - Check if the document path stored in SQLite / `doc_registry` exists for all files in `circular_forms/` and `circular_forms/College_documents/`.
   - Verify case-sensitivity and relative vs absolute paths on Linux.
2. **Iframe / Content Security**:
   - Check if modern browser sandbox or headers (`X-Frame-Options: SAMEORIGIN`) interfere with the PDF viewer iframe when testing on different hosts/ports.
   - Consider integrating Mozilla's **PDF.js** (viewer.html) for guaranteed cross-browser rendering if native browser PDF plugins fail.
3. **Download vs Inline Preview**:
   - Verify that all headers send `inline` rather than triggering attachment downloads.
