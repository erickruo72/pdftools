(() => {
  const $ = (sel, el = document) => el.querySelector(sel);




  // --- Image Upload ---
const imageUploadEl = document.getElementById("imageUpload");
imageUploadEl?.addEventListener("change", async () => {
  const f = imageUploadEl.files?.[0];
  if (!f) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    const imgUrl = e.target.result;
    const firstOverlay = document.querySelector(".overlay");
    if (firstOverlay) {
      // Place at top-left default position
      createImagePlacement(firstOverlay, 50, 50, imgUrl);
    }
  };
  reader.readAsDataURL(f);

  // Reset input
  imageUploadEl.value = "";
});
function createImagePlacement(overlayEl, xPx, yPx, imgUrl) {
  const { boxEl, contentEl, delEl, handles } = buildPlacementBox(xPx, yPx);

  const img = document.createElement("img");
  img.src = imgUrl;
  img.style.width  = "150px";
  img.style.height = "150px";
  img.style.display = "block";
  contentEl.appendChild(img);

  overlayEl.appendChild(boxEl);

  const id = `img_${Date.now()}`;
  const placement = {
    id,
    type: "image",
    page0: parseInt(overlayEl.dataset.pageIndex0, 10),
    overlayEl,
    boxEl,
    contentEl,
    delEl,
    handles,
    imgUrl,
    xPx,
    yPx,
    width: 150,
    height: 150
  };

  placements.push(placement);

  wirePlacementInteractions(placement); // drag, delete
  wireImageResize(placement);           // resizing
  selectPlacement(placement);
}


// --- Function to create image placement ---
function wireImageResize(p) {
  const { contentEl, handles } = p;

  Object.entries(handles).forEach(([pos, handleEl]) => {
    let resizing = false, startX = 0, startY = 0, startW = 0, startH = 0;
    handleEl.style.display = "block";

    handleEl.addEventListener("mousedown", (ev) => {
      ev.stopPropagation();
      resizing = true;
      startX = ev.clientX;
      startY = ev.clientY;
      startW = contentEl.offsetWidth;
      startH = contentEl.offsetHeight;
      document.body.style.userSelect = "none";
    });

    document.addEventListener("mousemove", (ev) => {
      if (!resizing) return;

      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;

      let newW = startW;
      let newH = startH;

      if (pos.includes("r")) newW = startW + dx;
      if (pos.includes("l")) newW = startW - dx;
      if (pos.includes("b")) newH = startH + dy;
      if (pos.includes("t")) newH = startH - dy;

      newW = Math.max(20, newW);
      newH = Math.max(20, newH);

      contentEl.style.width  = newW + "px";
      contentEl.style.height = newH + "px";

      const img = contentEl.querySelector("img");
      if (img) {
        img.style.width  = newW + "px";
        img.style.height = newH + "px";
      }

      // Update placement object
      p.xPx = parseFloat(p.boxEl.style.left);
      p.yPx = parseFloat(p.boxEl.style.top);
      p.width = newW;
      p.height = newH;
    });

    document.addEventListener("mouseup", () => {
      resizing = false;
      document.body.style.userSelect = "";
    });
  });
}


  // --- References ---
  const pagesContainer   = $("#pagesContainer");
  const fileInput        = $("#fileInput");
  const btnUpload        = $("#btnUpload");
  const sigTextEl        = $("#sigText");
  const sigFontEl        = $("#sigFont");
  const sigSizeEl        = $("#sigSize");
  const jobStatusEl      = $("#jobStatus");
  const downloadArea     = $("#downloadArea");
  const uploadInfo       = $("#uploadInfo");
  const btnFinalize      = $("#btnFinalize");
  const sigEnableEl      = $("#sigEnable") || $("#enableSigText") || $("#addSignature");
  const colorRadioNode   = () => document.querySelector('input[name="sigColor"]:checked');
  const shapeToolEl      = $("#shapeTool");

  // --- State ---
  let uploadedFilename = null;
  let pdfDoc = null;
  const renderScale = 1.5;
  const placements = [];
  let selectedPlacement = null;
  let selectedTool = null; // "text" | "shape" | null
  let selectedShapeType = "";

  // --- Fonts for on-canvas preview ---
  let fontsInjected = false;
  function injectPreviewFontsOnce() {
    if (fontsInjected) return;
    const style = document.createElement("style");
    style.textContent = `
      @font-face { font-family: 'DancingScript'; src: url('/static/fonts/DancingScript-Regular.ttf') format('truetype'); }
      @font-face { font-family: 'GreatVibes'; src: url('/static/fonts/GreatVibes-Regular.ttf') format('truetype'); }
      @font-face { font-family: 'Pacifico'; src: url('/static/fonts/Pacifico-Regular.ttf') format('truetype'); }
      @font-face { font-family: 'Satisfy'; src: url('/static/fonts/Satisfy-Regular.ttf') format('truetype'); }
      .placement-box { position:absolute; display:inline-block; }
      .placement-content { display:inline-block; white-space:pre; }
      .placement-selected { outline:1px dashed #1e90ff; outline-offset:2px; }
      .resize-handle { position:absolute; width:8px; height:8px; background:#1e90ff; border-radius:2px; display:none; }
      .handle-tl { left:-6px; top:-6px; cursor:nwse-resize; }
      .handle-tr { right:-6px; top:-6px; cursor:nesw-resize; }
      .handle-bl { left:-6px; bottom:-6px; cursor:nesw-resize; }
      .handle-br { right:-6px; bottom:-6px; cursor:nwse-resize; }
      .handle-t  { left:50%; top:-6px; transform:translateX(-50%); cursor:ns-resize; }
      .handle-b  { left:50%; bottom:-6px; transform:translateX(-50%); cursor:ns-resize; }
      .handle-l  { left:-6px; top:50%; transform:translateY(-50%); cursor:ew-resize; }
      .handle-r  { right:-6px; top:50%; transform:translateY(-50%); cursor:ew-resize; }
      .delete-btn { position:absolute; right:-14px; top:-14px; width:22px; height:22px; border-radius:50%; background:#e11d48; color:#fff; font:700 14px/22px system-ui, -apple-system, Segoe UI, Roboto, sans-serif; text-align:center; cursor:pointer; display:none; }
      .placement-box[contenteditable="true"] { caret-color:auto; }
    `;
    document.head.appendChild(style);
    fontsInjected = true;
  }

  // --- Helpers ---
  const getColor = () => colorRadioNode()?.value || "black";
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  function getShapeSymbol(type) {
    switch(type) {
      case "check": return "✔";
      case "cross": return "✖";
      case "circle": return "○";
      case "square": return "□";
      default: return "?";
    }
  }

  // --- Tool selectors ---
  shapeToolEl?.addEventListener("change", () => {
    selectedTool = "shape";
    selectedShapeType = shapeToolEl.value;
  });
  sigEnableEl?.addEventListener("change", () => {
    selectedTool = sigEnableEl.checked ? "text" : null;
  });

  // --- Toolbar -> Selection sync ---
  sigTextEl?.addEventListener("input", () => {
    if (!selectedPlacement || selectedPlacement.type !== "text") return;
    selectedPlacement.text = sigTextEl.value;
    selectedPlacement.contentEl.textContent = selectedPlacement.text || " ";
    // Keep box size natural; font size controls scaling
  });

  sigFontEl?.addEventListener("change", () => {
    if (!selectedPlacement) return;
    selectedPlacement.font = sigFontEl.value || "Helvetica";
    selectedPlacement.contentEl.style.fontFamily = `'${selectedPlacement.font}', sans-serif`;
  });

  sigSizeEl?.addEventListener("input", () => {
    if (!selectedPlacement) return;
    const newPt = parseInt(sigSizeEl.value || "24", 10);
    applyFontSize(selectedPlacement, newPt);
  });

  document.querySelectorAll('input[name="sigColor"]').forEach(radio => {
    radio.addEventListener("change", () => {
      if (!selectedPlacement) return;
      selectedPlacement.color = getColor();
      selectedPlacement.contentEl.style.color = selectedPlacement.color;
    });
  });

  function applyFontSize(p, sizePt) {
    p.sizePt = clamp(sizePt, 6, 400);
    const px = Math.max(8, Math.round(p.sizePt * p.pxPerPtX));
    p.contentEl.style.fontSize = `${px}px`;
    if (p === selectedPlacement) sigSizeEl.value = String(p.sizePt);
  }

  // --- PDF Upload ---
  btnUpload.addEventListener("click", async () => {
    const f = fileInput.files?.[0];
    if (!f) { alert("Choose a PDF file first."); return; }

    const fd = new FormData();
    fd.append("files", f);

    const res = await fetch("/api/upload", { method: "POST", body: fd });
    if (!res.ok) { alert("Upload failed"); return; }

    const data = await res.json();
    if (!data.files || !data.files.length) { alert("Unexpected upload response."); return; }

    uploadedFilename = data.files[0].unique_name;
    uploadInfo.textContent = `Uploaded: ${data.files[0].original_name}`;
    injectPreviewFontsOnce();
    await loadPdf(`/api/pdf/${encodeURIComponent(uploadedFilename)}`);
  });

  // --- Load PDF ---
  async function loadPdf(url) {
    placements.length = 0;
    selectedPlacement = null;
    pagesContainer.innerHTML = "";
    downloadArea.innerHTML = "";
    jobStatusEl.textContent = "";

    const loadingTask = pdfjsLib.getDocument(url);
    pdfDoc = await loadingTask.promise;

    for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
      const page = await pdfDoc.getPage(pageNum);
      const rotation = page.rotate || 0;
      const vpRender = page.getViewport({ scale: renderScale, rotation });
      const vpPts = page.getViewport({ scale: 1, rotation });

      const canvas = document.createElement("canvas");
      canvas.className = "pdf-canvas";
      canvas.width = vpRender.width;
      canvas.height = vpRender.height;
      const ctx = canvas.getContext("2d");
      await page.render({ canvasContext: ctx, viewport: vpRender }).promise;

      const wrap = document.createElement("div");
      wrap.className = "page-wrap";
      wrap.style.width = `${vpRender.width}px`;
      wrap.style.height = `${vpRender.height}px`;
      wrap.style.position = "relative";

      const overlay = document.createElement("div");
      overlay.className = "overlay";
      overlay.style.position = "absolute";
      overlay.style.inset = "0";
      overlay.style.zIndex = "2";
      overlay.dataset.pageIndex0 = String(pageNum - 1);
      overlay.dataset.renderW = String(vpRender.width);
      overlay.dataset.renderH = String(vpRender.height);
      overlay.dataset.pdfWpt = String(vpPts.width);
      overlay.dataset.pdfHpt = String(vpPts.height);
      overlay.dataset.rotation = String(rotation);
      overlay.dataset.pxPerPtX = String(vpRender.width / vpPts.width);
      overlay.dataset.pxPerPtY = String(vpRender.height / vpPts.height);

      // click-to-place
      overlay.addEventListener("click", (e) => {
        const rect = overlay.getBoundingClientRect();
        const xPx = e.clientX - rect.left;
        const yPx = e.clientY - rect.top;

        if (selectedTool === "text") {
          createTextPlacement(overlay, xPx, yPx);
        } else if (selectedTool === "shape") {
          createShapePlacement(overlay, xPx, yPx);
        }
      });

      wrap.appendChild(canvas);
      wrap.appendChild(overlay);
      pagesContainer.appendChild(wrap);
    }
  }

  // --- Placements creation ---
  function createTextPlacement(overlayEl, xPx, yPx) {
    const page0    = parseInt(overlayEl.dataset.pageIndex0, 10);
    const pxPerPtX = parseFloat(overlayEl.dataset.pxPerPtX);
    const pxPerPtY = parseFloat(overlayEl.dataset.pxPerPtY);
    const color    = getColor();
    const fontName = sigFontEl?.value || "Helvetica";
    const sizePt   = parseInt(sigSizeEl?.value || "24", 10);
    const initialText = (sigTextEl?.value?.trim()) || "Your text here";

    const { boxEl, contentEl, delEl, handles } = buildPlacementBox(xPx, yPx);
    contentEl.textContent = initialText || " ";
    contentEl.style.fontFamily = `'${fontName}', sans-serif`;
    contentEl.style.color = color;

    overlayEl.appendChild(boxEl);
    boxEl.style.top = `${yPx *0.3}px`;


    const id = `sig_${Date.now()}`;
    const placement = {
      id, type:"text", page0,
      xPx, yPx, pxPerPtX, pxPerPtY,
      overlayEl, boxEl, contentEl, delEl, handles,
      text: initialText, font: fontName, sizePt, color
    };
    placements.push(placement);

    wirePlacementInteractions(placement);
    applyFontSize(placement, sizePt);
    selectPlacement(placement);
  }

  function createShapePlacement(overlayEl, xPx, yPx) {
    if (!selectedShapeType) return;
    const page0    = parseInt(overlayEl.dataset.pageIndex0, 10);
    const pxPerPtX = parseFloat(overlayEl.dataset.pxPerPtX);
    const pxPerPtY = parseFloat(overlayEl.dataset.pxPerPtY);
    const color    = getColor();
    const sizePt   = parseInt(sigSizeEl?.value || "24", 10);

    const { boxEl, contentEl, delEl, handles } = buildPlacementBox(xPx, yPx);
    contentEl.textContent = getShapeSymbol(selectedShapeType);
    contentEl.style.color = color;

    overlayEl.appendChild(boxEl);
    boxEl.style.top = `${yPx * 0.3}px`;


    const id = `shape_${Date.now()}`;
    const placement = {
      id, type:"shape", page0,
      xPx, yPx, pxPerPtX, pxPerPtY,
      overlayEl, boxEl, contentEl, delEl, handles,
      shapeType: selectedShapeType, sizePt, color, font: "Helvetica" // font irrelevant for shapes
    };
    placements.push(placement);

    wirePlacementInteractions(placement);
    applyFontSize(placement, sizePt);
    selectPlacement(placement);
  }

  function buildPlacementBox(xPx, yPx) {
    const boxEl = document.createElement("div");
    boxEl.className = "placement-box";
    boxEl.style.left = `${xPx}px`;
    boxEl.style.top  = `${yPx}px`;

    const contentEl = document.createElement("div");
    contentEl.className = "placement-content";
    boxEl.appendChild(contentEl);

    // Delete button (fixed size, never scales)
    const delEl = document.createElement("div");
    delEl.className = "delete-btn";
    delEl.textContent = "✖";
    boxEl.appendChild(delEl);

    // 8 handles
    const handlePositions = ["tl","tr","bl","br","t","b","l","r"];
    const handles = {};
    handlePositions.forEach(pos => {
      const h = document.createElement("div");
      h.className = `resize-handle handle-${pos}`;
      boxEl.appendChild(h);
      handles[pos] = h;
    });

    return { boxEl, contentEl, delEl, handles };
  }

  // --- Interactions (select, drag, resize, delete, edit) ---
  function wirePlacementInteractions(p) {
    const { boxEl, contentEl, delEl, handles } = p;

    // Select
    function onSelect(ev) {
      if (ev) ev.stopPropagation();
      selectPlacement(p);
    }
    boxEl.addEventListener("mousedown", (ev) => {
      if ((ev.target && ev.target.classList.contains("resize-handle")) || ev.target === delEl) return;

      onSelect(ev);
    });

    // Dragging
    let dragging = false, sx=0, sy=0, sl=0, st=0;
    boxEl.addEventListener("mousedown", (ev) => {
      if ((ev.target && ev.target.classList.contains("resize-handle")) || ev.target === delEl) return;

      dragging = true; sx = ev.clientX; sy = ev.clientY;
      sl = parseFloat(boxEl.style.left); st = parseFloat(boxEl.style.top);
      document.body.style.userSelect = "none";
    });
    document.addEventListener("mousemove", (ev) => {
      if (!dragging) return;
      const nx = sl + (ev.clientX - sx);
      const ny = st + (ev.clientY - sy);
      boxEl.style.left = `${nx}px`;
      boxEl.style.top  = `${ny}px`;
      p.xPx = nx; p.yPx = ny;
    });
    document.addEventListener("mouseup", () => {
      dragging = false;
      document.body.style.userSelect = "";
    });

    // Delete
    delEl.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const idx = placements.findIndex(x => x.id === p.id);
      if (idx >= 0) placements.splice(idx, 1);
      boxEl.remove();
      if (selectedPlacement?.id === p.id) selectedPlacement = null;
    });

    // Inline edit for text
    if (p.type === "text") {
      contentEl.addEventListener("dblclick", (ev) => {
        ev.stopPropagation();
        contentEl.contentEditable = "true";
        contentEl.focus();
        // place cursor at end
        const range = document.createRange();
        range.selectNodeContents(contentEl);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      });
      contentEl.addEventListener("blur", () => {
        contentEl.contentEditable = "false";
        p.text = contentEl.textContent || "";
        if (p === selectedPlacement) sigTextEl.value = p.text;
      });
      // Stop dragging while editing
      contentEl.addEventListener("keydown", (e) => e.stopPropagation());
      contentEl.addEventListener("keyup", (e) => e.stopPropagation());
      contentEl.addEventListener("mousedown", (e) => {
        if (contentEl.isContentEditable) e.stopPropagation();
      });
    }

    // Resizing -> changes FONT SIZE (all 8 handles)
    Object.entries(handles).forEach(([pos, handleEl]) => {
      let resizing = false, startX=0, startY=0, startPt=0;
      handleEl.addEventListener("mousedown", (ev) => {
        ev.stopPropagation();
        resizing = true;
        startX = ev.clientX; startY = ev.clientY;
        startPt = p.sizePt;
        document.body.style.userSelect = "none";
      });
      document.addEventListener("mousemove", (ev) => {
        if (!resizing) return;
        // Outward movement should increase font size for that handle
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;

        // Map movement to "outward" sign based on handle
        const outward =
          (pos.includes("r") ? dx : 0) +
          (pos.includes("l") ? -dx : 0) +
          (pos.includes("b") ? dy : 0) +
          (pos.includes("t") ? -dy : 0);

        // Sensitivity: 1 px ≈ 0.6 pt (tweakable)
        const deltaPt = outward * 0.6;
        const newPt = clamp(startPt + deltaPt, 6, 400);
        applyFontSize(p, newPt);
      });
      document.addEventListener("mouseup", () => {
        resizing = false;
        document.body.style.userSelect = "";
      });
    });
  }

  // --- Selection UI ---
  function selectPlacement(p) {
    if (selectedPlacement?.boxEl) {
      selectedPlacement.boxEl.classList.remove("placement-selected");
      selectedPlacement.delEl.style.display = "none";
      Object.values(selectedPlacement.handles).forEach(h => h.style.display = "none");
    }
    selectedPlacement = p;
    if (!p) return;

    p.boxEl.classList.add("placement-selected");
    p.delEl.style.display = "block";
    Object.values(p.handles).forEach(h => h.style.display = "block");

    // Sync toolbar
    if (p.type === "text") {
      sigTextEl.value  = p.text;
      sigFontEl.value  = p.font;
    } else {
      // For shapes, keep text box as-is but don't overwrite it
    }
    sigSizeEl.value = String(p.sizePt);
    const radios = document.querySelectorAll('input[name="sigColor"]');
    radios.forEach(r => r.checked = (r.value === p.color));
  }

  function wireImageResize(p) {
  const { boxEl, contentEl, handles } = p;

  // Show handles for images
  Object.values(handles).forEach(h => h.style.display = "block");

  // --- Dragging for images ---
  let dragging = false, sx = 0, sy = 0, sl = 0, st = 0;
  boxEl.addEventListener("mousedown", (ev) => {
    if (ev.target.classList.contains("resize-handle")) return;
    dragging = true;
    sx = ev.clientX;
    sy = ev.clientY;
    sl = parseFloat(boxEl.style.left);
    st = parseFloat(boxEl.style.top);
    document.body.style.userSelect = "none";
  });

  document.addEventListener("mousemove", (ev) => {
    if (dragging) {
      const nx = sl + (ev.clientX - sx);
      const ny = st + (ev.clientY - sy);
      boxEl.style.left = nx + "px";
      boxEl.style.top  = ny + "px";
      p.xPx = nx;
      p.yPx = ny;
    }
  });

  document.addEventListener("mouseup", () => {
    dragging = false;
    document.body.style.userSelect = "";
  });

  // --- Resizing for images ---
  Object.entries(handles).forEach(([pos, handleEl]) => {
    let resizing = false, startX = 0, startY = 0, startW = 0, startH = 0;
    handleEl.addEventListener("mousedown", (ev) => {
      ev.stopPropagation();
      resizing = true;
      startX = ev.clientX;
      startY = ev.clientY;
      startW = contentEl.offsetWidth;
      startH = contentEl.offsetHeight;
      document.body.style.userSelect = "none";
    });
    document.addEventListener("mousemove", (ev) => {
  if (!resizing) return;

  const dx = ev.clientX - startX;
  const dy = ev.clientY - startY;

  let newW = startW;
  let newH = startH;

  if (pos.includes("r")) newW = startW + dx;
  if (pos.includes("l")) newW = startW - dx;
  if (pos.includes("b")) newH = startH + dy;
  if (pos.includes("t")) newH = startH - dy;

  // Minimum size
  newW = Math.max(20, newW);
  newH = Math.max(20, newH);

  // Resize the container
  contentEl.style.width  = newW + "px";
  contentEl.style.height = newH + "px";

  // Resize the image inside (if it exists)
  const img = contentEl.querySelector("img");
  if (img) {
    img.style.width  = newW + "px";
    img.style.height = newH + "px";
  }

  // Update placement object so final PDF uses new size
  p.width  = newW;
  p.height = newH;
});


    document.addEventListener("mouseup", () => {
      resizing = false;
      document.body.style.userSelect = "";
    });
  });

  // Set initial width/height in placement object
  p.width  = contentEl.offsetWidth;
  p.height = contentEl.offsetHeight;
}


  // --- Finalize / Merge ---
 btnFinalize?.addEventListener("click", async () => {
  if (!uploadedFilename) { alert("No PDF uploaded"); return; }
  if (!placements.length) { alert("No items added"); return; }

  const payload = {
    pdf_filename: uploadedFilename,
    placements: placements.map(p => {
      const pdfHpt = parseFloat(p.overlayEl.dataset.pdfHpt);
      const common = {
        page_number: p.page0,
        x: p.xPx / (p.pxPerPtX || 1),
        y: pdfHpt - (p.yPx / (p.pxPerPtY || 1)), // invert Y
        type: p.type,
      };

      if (p.type === "text") {
        return { 
          ...common,
          text: p.text,
          font: p.font,
          color: p.color,
          size_pt: p.sizePt
        };
      } else if (p.type === "shape") {
        return {
          ...common,
          shapeType: p.shapeType,
          color: p.color,
          size_pt: p.sizePt
        };
      } 
      if (p.type === "image") {
  const pdfHpt = parseFloat(p.overlayEl.dataset.pdfHpt);
  const pdfWpt = parseFloat(p.overlayEl.dataset.pdfWpt);

  return {
    ...common,
    imgSrc: p.imgUrl,
    x: p.xPx / (p.pxPerPtX || 1),
    y: pdfHpt - (p.yPx / (p.pxPerPtY || 1)) - (p.height / (p.pxPerPtY || 1)), // account for height
    width: p.width / (p.pxPerPtX || 1),
    height: p.height / (p.pxPerPtY || 1)
  };
}



      return common;
    })
  };

  try {
    const res = await fetch("/api/pdf/sign/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed");

    const jobId = data.job_id;
    jobStatusEl.textContent = "Processing...";

    const poll = async () => {
      const statusRes = await fetch(`/api/job/status/${jobId}`);
      const s = await statusRes.json();

      if (s.status === "finished") {
        jobStatusEl.textContent = "PDF ready!";
        const a = document.createElement("a");
        a.href = `/api/pdf/${encodeURIComponent(s.result)}`;
        a.download = s.result;
        a.textContent = "Download PDF";
        downloadArea.innerHTML = "";
        downloadArea.appendChild(a);
      } else if (s.status === "failed") {
        jobStatusEl.textContent = "Failed: " + s.result;
      } else {
        setTimeout(poll, 1000);
      }
    };

    poll();

  } catch (err) {
    alert("Error: " + err.message);
  }
});

})();
