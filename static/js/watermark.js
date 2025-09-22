// watermark.js (full rewrite)
// - Only upload box visible initially
// - Upload shows centered spinner (replacement of upload box)
// - PDF preview rendered using PDF.js (first page only for preview)
// - Watermark centered using container sizes (offsetWidth/offsetHeight)
// - Force reflow + clamp after render so watermark doesn't overflow initially
// - Dragging & resizing support (mouse + touch)
// - Apply button swaps label for spinner while server job is in progress
// - Polls job status and reveals download button when done

document.addEventListener("DOMContentLoaded", () => {
  // ---- DOM references ----
  const uploadBox     = document.getElementById("upload-box");
  const fileInput     = document.getElementById("pdf-upload");
  const loading       = document.getElementById("loading"); // loading container placed where upload box is
  const workspace     = document.getElementById("workspace");
  const previewFrame  = document.getElementById("preview-frame");
  const canvas        = document.getElementById("pdf-canvas");
  const wmBox         = document.getElementById("watermark-box");
  const wmText        = document.getElementById("watermark");
  const resizeHandle  = wmBox ? wmBox.querySelector(".resize-handle") : null;

  const txtInput      = document.getElementById("wm-text");
  const opacityInput  = document.getElementById("wm-opacity");
  const rotationInput = document.getElementById("wm-rotation");
  const sizeInput     = document.getElementById("wm-size");
  const pageOption    = document.getElementById("page-option");
  const specificPages = document.getElementById("specific-pages");

  const applyBtn        = document.getElementById("apply-btn");
  const applyBtnText    = applyBtn.querySelector(".btn-text");
  const applyBtnSpinner = applyBtn.querySelector(".btn-spinner");
  const downloadBtn     = document.getElementById("download-btn");

  // ---- state ----
  let uploadedFile = null;
  let pdfDoc = null;
  let isDragging = false;
  let dragOffset = { x: 0, y: 0 };
  let isResizing = false;
  let resizeStartX = 0;
  let resizeStartFont = 0;

  // ---- small helpers to make sure things are truly hidden/shown ----
  function hardHide(el) {
    if (!el) return;
    el.classList.add("hidden");
    el.style.display = "none";
    el.setAttribute("aria-hidden", "true");
  }
  function hardShow(el, display = "block") {
    if (!el) return;
    el.classList.remove("hidden");
    el.style.display = display;
    el.removeAttribute("aria-hidden");
  }

  // ---- initial UI state: only upload box visible ----
  hardShow(uploadBox, "flex");
  hardHide(loading);
  hardHide(workspace);
  hardHide(previewFrame);
  hardHide(canvas);
  hardHide(wmBox);
  hardHide(downloadBtn);

  // ensure canvas cleared
  canvas.width = 0;
  canvas.height = 0;

  // ---- Upload handlers (click / drag / drop / file input) ----
  uploadBox.addEventListener("click", () => fileInput.click());

  uploadBox.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadBox.classList.add("dragging");
  });
  uploadBox.addEventListener("dragleave", () => uploadBox.classList.remove("dragging"));
  uploadBox.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadBox.classList.remove("dragging");
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) startLoad(f);
  });

  fileInput.addEventListener("change", (e) => {
    const f = e.target.files && e.target.files[0];
    if (f) startLoad(f);
  });

  // Put a small loading message inside the loading container (spinner already in CSS)
  function setLoadingMessage(msg) {
    loading.innerHTML = ""; // clear previous
    const wrap = document.createElement("div");
    wrap.style.display = "flex";
    wrap.style.flexDirection = "column";
    wrap.style.alignItems = "center";
    wrap.style.gap = "0.6rem";

    const ring = document.createElement("div");
    ring.className = "spinner"; // rely on existing CSS spinner style
    wrap.appendChild(ring);

    const span = document.createElement("div");
    span.className = "loading-text";
    span.textContent = msg || "Loading…";
    wrap.appendChild(span);

    loading.appendChild(wrap);
  }

  // start loading file: show spinner (in same place as upload box) and render preview
  async function startLoad(file) {
    if (!file) return;
    if (file.type !== "application/pdf") {
      alert("Please upload a valid PDF file (PDF only).");
      return;
    }
    uploadedFile = file;

    // show spinner in place of upload box
    hardHide(uploadBox);
    setLoadingMessage("Uploading your file...");
    hardShow(loading, "flex");

    try {
      // Read file to ArrayBuffer then load pdf.js document
      const buffer = await file.arrayBuffer();
      pdfDoc = await pdfjsLib.getDocument(new Uint8Array(buffer)).promise;

      // render preview first page and initialize watermark
      await renderFirstPageFromPdf(pdfDoc);

      // switch UI to workspace
      hardHide(loading);
      hardShow(workspace, "flex");
      hardShow(previewFrame, "block");
      hardShow(canvas, "block");
      hardShow(wmBox, "block");
      hardHide(downloadBtn);
    } catch (err) {
      console.error("PDF load/render error:", err);
      alert("Failed to load PDF. Please try another file.");
      hardHide(loading);
      hardHide(workspace);
      hardShow(uploadBox, "flex");
      uploadedFile = null;
    }
  }

  // ---- Render first page and center watermark properly ----
  async function renderFirstPageFromPdf(pdf) {
    // get first page
    const page = await pdf.getPage(1);
    const viewport = page.getViewport({ scale: 1.2 });

    // size canvas (we use pixel dimensions for mapping later)
    canvas.width = viewport.width;
    canvas.height = viewport.height;

    // render into canvas
    await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;

    // set default large watermark text & style
    wmText.style.fontSize = "48px";
    wmText.textContent = txtInput.value || "Watermark";
    wmText.style.opacity = opacityInput.value || "0.3";
    // Reset any transforms on box (rotation may later change it)
    wmBox.style.transform = `rotate(${rotationInput.value || 0}deg)`;

    // Now center using container offset sizes (not boundingClientRect)
    // Using offsetWidth/offsetHeight prevents viewport-relative inconsistencies.
    requestAnimationFrame(() => {
      const frameW = previewFrame.offsetWidth;
      const frameH = previewFrame.offsetHeight;
      const wmW = wmBox.offsetWidth;
      const wmH = wmBox.offsetHeight;

      // absolute positioning relative to preview frame
      wmBox.style.position = "absolute";
      wmBox.style.left = `${Math.max(0, (frameW - wmW) / 2)}px`;
      wmBox.style.top  = `${Math.max(0, (frameH - wmH) / 2)}px`;

      // Force another frame, then clamp. This makes sure the browser calculates final layout
      // and the watermark bounding box is stable — solves initial overflow issue.
      requestAnimationFrame(() => {
        clampWatermarkPosition();
        // Also ensure size input reflects actual font-size we set
        const fs = parseInt(window.getComputedStyle(wmText).fontSize, 10) || parseInt(sizeInput.value, 10);
        sizeInput.value = fs;
      });
    });
  }

  // ---- Controls wiring (text, opacity, rotation, size, page options) ----
  txtInput.addEventListener("input", () => {
    wmText.textContent = txtInput.value || " ";
    // Re-clamp because changing content may change width
    requestAnimationFrame(clampWatermarkPosition);
  });

  opacityInput.addEventListener("input", () => {
    wmText.style.opacity = opacityInput.value;
  });

  rotationInput.addEventListener("input", () => {
    // Apply rotation on the box (visual). Re-clamp afterwards to ensure bounding is correct.
    wmBox.style.transform = `rotate(${rotationInput.value}deg)`;
    // rotation can change how it visually fits; re-clamp after a frame
    requestAnimationFrame(clampWatermarkPosition);
  });

  sizeInput.addEventListener("input", () => {
    const val = parseInt(sizeInput.value, 10) || 16;
    wmText.style.fontSize = `${val}px`;
    // Changing font-size changes offsets/width — clamp after frame
    requestAnimationFrame(clampWatermarkPosition);
  });

  pageOption.addEventListener("change", () => {
    if (pageOption.value === "specific") hardShow(specificPages, "block");
    else hardHide(specificPages);
  });

  // ---- Dragging logic (mouse + touch) ----
  function clampWatermarkPosition() {
    // Use previewFrame offset sizes (local coords)
    const frameW = previewFrame.offsetWidth;
    const frameH = previewFrame.offsetHeight;
    const wmW = wmBox.offsetWidth;
    const wmH = wmBox.offsetHeight;

    let left = parseFloat(wmBox.style.left) || 0;
    let top  = parseFloat(wmBox.style.top) || 0;

    left = Math.max(0, Math.min(left, frameW - wmW));
    top  = Math.max(0, Math.min(top, frameH - wmH));

    wmBox.style.left = `${left}px`;
    wmBox.style.top  = `${top}px`;
  }

  // helper: get point from mouse or touch
  function pointFromEvent(e) {
    if (e.touches && e.touches.length) {
      return { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
    return { x: e.clientX, y: e.clientY };
  }

  // Start dragging
  function startDrag(e) {
    const p = pointFromEvent(e);
    // if the target is the resize handle we let resize handlers take over
    if (e.target === resizeHandle || (e.touches && e.touches[0] && e.touches[0].target === resizeHandle)) return;
    isDragging = true;
    const rect = wmBox.getBoundingClientRect();
    dragOffset.x = p.x - rect.left;
    dragOffset.y = p.y - rect.top;
    e.preventDefault();
  }

  // Move drag
  function moveDrag(e) {
    if (!isDragging) return;
    const p = pointFromEvent(e);
    const frameRect = previewFrame.getBoundingClientRect();
    // compute local coordinates relative to previewFrame
    let left = p.x - frameRect.left - dragOffset.x;
    let top  = p.y - frameRect.top  - dragOffset.y;

    // clamp to frame boundaries
    left = Math.max(0, Math.min(left, frameRect.width - wmBox.offsetWidth));
    top  = Math.max(0, Math.min(top, frameRect.height - wmBox.offsetHeight));

    wmBox.style.left = `${left}px`;
    wmBox.style.top  = `${top}px`;
  }

  // End drag
  function endDrag() {
    if (!isDragging) return;
    isDragging = false;
    clampWatermarkPosition();
  }

  // mouse
  wmBox.addEventListener("mousedown", startDrag);
  window.addEventListener("mousemove", moveDrag);
  window.addEventListener("mouseup", endDrag);

  // touch
  wmBox.addEventListener("touchstart", (e) => startDrag(e), { passive: false });
  window.addEventListener("touchmove", (e) => moveDrag(e), { passive: false });
  window.addEventListener("touchend", () => endDrag());

  // ---- Resizing watermark (mouse + touch) by changing font-size ----
  if (resizeHandle) {
    resizeHandle.addEventListener("mousedown", (e) => {
      e.stopPropagation();
      isResizing = true;
      resizeStartX = e.clientX;
      resizeStartFont = parseInt(window.getComputedStyle(wmText).fontSize, 10) || 48;
      document.body.style.cursor = "nwse-resize";
      e.preventDefault();
    });

    window.addEventListener("mousemove", (e) => {
      if (!isResizing) return;
      const delta = e.clientX - resizeStartX;
      let newSize = resizeStartFont + delta;
      newSize = Math.max(10, Math.min(300, newSize));
      wmText.style.fontSize = `${newSize}px`;
      sizeInput.value = newSize;
      requestAnimationFrame(clampWatermarkPosition);
    });

    window.addEventListener("mouseup", () => {
      if (isResizing) {
        isResizing = false;
        document.body.style.cursor = "";
        clampWatermarkPosition();
      }
    });

    // touch-resize
    resizeHandle.addEventListener("touchstart", (e) => {
      e.stopPropagation();
      isResizing = true;
      resizeStartX = e.touches[0].clientX;
      resizeStartFont = parseInt(window.getComputedStyle(wmText).fontSize, 10) || 48;
    }, { passive: false });

    window.addEventListener("touchmove", (e) => {
      if (!isResizing) return;
      const delta = e.touches[0].clientX - resizeStartX;
      let newSize = resizeStartFont + delta;
      newSize = Math.max(10, Math.min(300, newSize));
      wmText.style.fontSize = `${newSize}px`;
      sizeInput.value = newSize;
      requestAnimationFrame(clampWatermarkPosition);
    }, { passive: false });

    window.addEventListener("touchend", () => {
      if (isResizing) {
        isResizing = false;
        clampWatermarkPosition();
      }
    });
  }

  // Also re-clamp when window resizes (container dims change)
  window.addEventListener("resize", () => {
    requestAnimationFrame(clampWatermarkPosition);
  });

  // ---- Apply watermark: replace button label with spinner + text until job done ----
  function resetApplyBtn() {
    applyBtn.disabled = false;
    applyBtnText.classList.remove("hidden");
    applyBtnSpinner.classList.add("hidden");
    applyBtnSpinner.textContent = ""; // clear any previous text
  }

  applyBtn.addEventListener("click", async () => {
    if (!uploadedFile) {
      alert("Please upload a PDF first.");
      return;
    }

    // show inline spinner (keeps button in place)
    applyBtn.disabled = true;
    applyBtnText.classList.add("hidden");
    applyBtnSpinner.classList.remove("hidden");
    applyBtnSpinner.textContent = "Applying watermark…";

    // Build payload: position relative to PDF canvas
    try {
      // compute normalized coordinates (center point of watermark box)
      const canvasRect = canvas.getBoundingClientRect();
      const boxRect = wmBox.getBoundingClientRect();
      const centerX = (boxRect.left - canvasRect.left) + boxRect.width / 2;
      const centerY = (boxRect.top  - canvasRect.top)  + boxRect.height / 2;
      const normX = centerX / canvasRect.width;
      const normY = centerY / canvasRect.height;

      // convert to PDF canvas coordinates (pixel space)
      const pdfX = normX * canvas.width;
      const pdfY = (1 - normY) * canvas.height; // invert Y if server expects bottom-left origin

      const form = new FormData();
      form.append("pdf_file", uploadedFile);
      form.append("text", wmText.textContent);
      form.append("angle", rotationInput.value || 0);
      form.append("opacity", opacityInput.value || 0.3);
      form.append("size", sizeInput.value || parseInt(window.getComputedStyle(wmText).fontSize, 10));
      form.append("x", pdfX.toFixed(2));
      form.append("y", pdfY.toFixed(2));
      form.append("canvas_width", canvas.width);
      form.append("canvas_height", canvas.height);
      form.append("page_option", pageOption.value || "all");
      if (pageOption.value === "specific") form.append("specific_pages", specificPages.value || "");

      const res = await fetch("/api/add-text-watermark", { method: "POST", body: form });
      if (!res.ok) throw new Error("Server error while submitting job.");
      const data = await res.json();
      if (!data.job_id) throw new Error("No job id returned.");
      pollJob(data.job_id);
    } catch (err) {
      console.error("Apply submit error:", err);
      alert("Failed to submit watermark job.");
      resetApplyBtn();
    }
  });

  // ---- Poll job status and show download when ready ----
  function pollJob(jobId) {
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`/api/job/status/${encodeURIComponent(jobId)}`);
        if (!r.ok) throw new Error("Status fetch failed");
        const j = await r.json();

        if (j.status === "finished" && j.result) {
          clearInterval(interval);
          // hide apply, show download
          applyBtn.classList.add("hidden");
          hardShow(downloadBtn, "inline-flex");
          const filename = typeof j.result === "string" ? j.result : (j.result.output_filename || j.result);
          downloadBtn.onclick = () => {
            window.location.href = `/api/job/download/${encodeURIComponent(filename)}`;
          };
          resetApplyBtn();
        } else if (j.status === "failed") {
          clearInterval(interval);
          alert("Watermark job failed.");
          resetApplyBtn();
        } else {
          // update UI status if you have a job status element (optional)
          // e.g. jobStatusEl.textContent = `Status: ${j.status}`;
        }
      } catch (err) {
        clearInterval(interval);
        console.error("Polling error:", err);
        alert("Error checking job status.");
        resetApplyBtn();
      }
    }, 1500);
  }

  // Expose small utility for debugging (optional)
  window._watermark_debug = {
    clampWatermarkPosition,
  };
});
