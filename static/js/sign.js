// A self-contained script for the PDF signing application logic.
// This script handles file uploads, PDF rendering, signature placement,
// and the finalization of the signed document.

(() => {
    // Helper function for selecting elements.
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // Main UI elements
    const fileInput = $("#fileInput");
    const dropZone = $("#dropZone");
    const viewer = $(".viewer");
    const pagesContainer = $("#pagesContainer");
    
    // Controls that exist in both desktop header and mobile sidebar
    const sigEnableEls = $$('#enableSigText');
    const sigFontEls = $$('#sigFont');
    const sigSizeEls = $$('#sigSize');
    const sigColorEls = $$('#sigColor');
    const btnFinalizeEls = $$('#btnFinalize, #btnFinalizeMobile');


    // Status and download elements. Note the use of $$ to get all elements with the IDs.
    const jobStatusEls = $$("#jobStatus, #jobStatusMobile");
    const downloadAreaEls = $$("#downloadArea, #downloadAreaMobile");

    // State variables
    let uploadedFilename = null;
    let pdfDoc = null;
    const placements = [];
    let selectedPlacement = null;
    let fontsInjected = false;


    // Small UI helpers
function showFileUploadSpinner() {
    const uploadContent = document.getElementById('fileUploadContent');
    const spinner = document.getElementById('fileUploadSpinner');
    if (uploadContent && spinner) {
        uploadContent.style.display = 'none';
        spinner.style.display = 'flex';
    }
}

function hideFileUploadSpinner() {
    const uploadContent = document.getElementById('fileUploadContent');
    const spinner = document.getElementById('fileUploadSpinner');
    if (uploadContent && spinner) {
        uploadContent.style.display = 'flex';
        spinner.style.display = 'none';
    }
}

function startFinalizingSpinner() {
    const btnFinalize = document.getElementById('btnFinalize');
    const btnFinalizeMobile = document.getElementById('btnFinalizeMobile');
    
    if (btnFinalize) {
        btnFinalize.disabled = true;
        btnFinalize.querySelector('.button-text').style.display = 'none';
        btnFinalize.querySelector('.spinner-container').style.display = 'flex';
    }
    if (btnFinalizeMobile) {
        btnFinalizeMobile.disabled = true;
        btnFinalizeMobile.querySelector('.button-text').style.display = 'none';
        btnFinalizeMobile.querySelector('.spinner-container').style.display = 'flex';
    }
}

function stopFinalizingSpinner() {
    const btnFinalize = document.getElementById('btnFinalize');
    const btnFinalizeMobile = document.getElementById('btnFinalizeMobile');
    
    if (btnFinalize) {
        btnFinalize.disabled = false;
        btnFinalize.querySelector('.button-text').style.display = 'inline';
        btnFinalize.querySelector('.spinner-container').style.display = 'none';
    }
    if (btnFinalizeMobile) {
        btnFinalizeMobile.disabled = false;
        btnFinalizeMobile.querySelector('.button-text').style.display = 'inline';
        btnFinalizeMobile.querySelector('.spinner-container').style.display = 'none';
    }
}
    // --- Core Logic Functions ---

    /**
     * Injects the custom signature fonts once.
     */
    function injectPreviewFontsOnce() {
        if (fontsInjected) return;
        const style = document.createElement("style");
        style.textContent = `
            @font-face { font-family: 'DancingScript'; src: url('/static/fonts/DancingScript-Regular.ttf') format('truetype'); font-display: swap; }
            @font-face { font-family: 'GreatVibes'; src: url('/static/fonts/GreatVibes-Regular.ttf') format('truetype'); font-display: swap; }
            @font-face { font-family: 'Pacifico'; src: url('/static/fonts/Pacifico-Regular.ttf') format('truetype'); font-display: swap; }
            @font-face { font-family: 'Satisfy'; src: url('/static/fonts/Satisfy-Regular.ttf') format('truetype'); font-display: swap; }
        `;
        document.head.appendChild(style);
        fontsInjected = true;
    }

    /**
     * Uploads the selected file and triggers the PDF loading process.
     * @param {File} file The file to upload.
     */
    async function handleFile(file) {
        if (!file || file.type !== "application/pdf") {
            // Use a custom message box instead of alert()
            showStatus("Please select a valid PDF file.");
            return;
        }

        // Show a loading message
        showStatus("Uploading file...", true);
        showFileUploadSpinner();
        
        const fd = new FormData();
        // The server expects the form data key to be "files" based on the previous working code
        fd.append("files", file);

        try {
            const res = await fetch("/api/upload", { method: "POST", body: fd });
            if (!res.ok) {
                const error = await res.json();
                throw new Error(`Upload failed: ${error.error}`);
            }

            const data = await res.json();
            if (!data.files || data.files.length === 0) {
                throw new Error("Unexpected upload response.");
            }

            // Store the uploaded filename and load the PDF
            uploadedFilename = data.files[0].unique_name;
            
            // Hide the upload area and show the viewer
            dropZone.style.display = 'none';
            viewer.style.display = 'block';

            injectPreviewFontsOnce();
            await loadPdf(`/api/pdf/${uploadedFilename}`);
            hideFileUploadSpinner();
            showStatus("PDF loaded. Click to add a signature.");

        } catch (err) {
                hideFileUploadSpinner();

            console.error(err);
            // Use a custom message box instead of alert()
            showStatus(`Upload failed. ${err.message}. Please try again.`);
            // Re-enable the upload UI on error
            dropZone.style.display = 'flex';
            viewer.style.display = 'none';
        }
    }

    /**
     * Loads and renders a PDF from a given URL into the viewer.
     * @param {string} url The URL of the PDF to load.
     */
    async function loadPdf(url) {
    placements.length = 0;
    selectedPlacement = null;
    pagesContainer.innerHTML = "";
    downloadAreaEls.forEach(el => el.innerHTML = "");
    jobStatusEls.forEach(el => el.textContent = "");

    const loadingTask = pdfjsLib.getDocument(url);
    pdfDoc = await loadingTask.promise;

    for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
        const page = await pdfDoc.getPage(pageNum);
        const rotation = page.rotate || 0;

        // --- Container width ---
        const containerWidth = pagesContainer.clientWidth || window.innerWidth;
        const unscaledViewport = page.getViewport({ scale: 1, rotation });

        // Scale so it fits, but never upscale beyond 100%
        let scale = containerWidth / unscaledViewport.width;
        if (scale > 1) scale = 1;

        const vpRender = page.getViewport({ scale, rotation });
        const vpPts = page.getViewport({ scale: 1, rotation });

        // --- HiDPI Canvas for sharp text ---
        const canvas = document.createElement("canvas");
        canvas.className = "pdf-canvas";
        const ctx = canvas.getContext("2d");

        const dpr = window.devicePixelRatio || 1;
        canvas.width = vpRender.width * dpr;
        canvas.height = vpRender.height * dpr;
        canvas.style.width = `${vpRender.width}px`;
        canvas.style.height = `${vpRender.height}px`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        await page.render({ canvasContext: ctx, viewport: vpRender }).promise;

        // --- Wrapper ---
        const wrap = document.createElement("div");
        wrap.className = "page-wrap";
        wrap.style.display = "flex";
        wrap.style.justifyContent = "center";
        wrap.style.margin = "0 auto";
        wrap.style.width = "100%";

        const innerWrap = document.createElement("div");
        innerWrap.style.width = `${vpRender.width}px`;
        innerWrap.style.height = `${vpRender.height}px`;
        innerWrap.style.position = "relative";
        innerWrap.style.maxWidth = "100%"; // Prevent overflow
        innerWrap.style.margin = "0 auto"; // Center when smaller than container

        // --- Overlay for interactions ---
        const overlay = document.createElement("div");
        overlay.className = "overlay";
        overlay.style.position = "absolute";
        overlay.style.inset = "0";
        overlay.dataset.pageIndex0 = String(pageNum - 1);
        overlay.dataset.renderW = String(vpRender.width);
        overlay.dataset.renderH = String(vpRender.height);
        overlay.dataset.pdfWpt = String(vpPts.width);
        overlay.dataset.pdfHpt = String(vpPts.height);
        overlay.dataset.rotation = String(rotation);
        overlay.dataset.pxPerPtX = String(vpRender.width / vpPts.width);
        overlay.dataset.pxPerPtY = String(vpRender.height / vpPts.height);

        overlay.addEventListener("click", (e) => {
            const isEnabled = Array.from(sigEnableEls).some(el => el.checked);
            if (!isEnabled) return;
            const rect = overlay.getBoundingClientRect();
            createPlacement(overlay, e.clientX - rect.left, e.clientY - rect.top);
        });

        innerWrap.appendChild(canvas);
        innerWrap.appendChild(overlay);
        wrap.appendChild(innerWrap);
        pagesContainer.appendChild(wrap);
    }
}


    /**
     * Creates a new signature placement element on the PDF overlay.
     * @param {HTMLElement} overlayEl The overlay element for the PDF page.
     * @param {number} xPx The raw X-coordinate in pixels from the click.
     * @param {number} yPx The raw Y-coordinate in pixels from the click.
     */
    function createPlacement(overlayEl, xPx, yPx) {
    const page0 = parseInt(overlayEl.dataset.pageIndex0, 10);
    const pxPerPtX = parseFloat(overlayEl.dataset.pxPerPtX);
    const pxPerPtY = parseFloat(overlayEl.dataset.pxPerPtY);
    const pdfHpt = parseFloat(overlayEl.dataset.pdfHpt);

    const el = document.createElement("div");
    el.className = "sig-preview";
    el.style.position = "absolute";

    // Signature properties
    const fontEl = sigFontEls.item(0);
    const sizeEl = sigSizeEls.item(0);
    const colorEl = sigColorEls.item(0);

    const font = fontEl.value;
    const sizePt = parseInt(sizeEl.value, 10);
    const color = colorEl.value;
    const pxFont = Math.max(8, Math.round(sizePt * pxPerPtX));

    el.textContent = "Your Signature";
    el.style.fontFamily = `'${font}', cursive, sans-serif`;
    el.style.fontSize = `${pxFont}px`;
    el.style.color = color;

    // --- Editable behavior ---
    el.contentEditable = false;
    el.tabIndex = 0; // allow focus on mobile

    function enterEditMode() {
        if (el.isContentEditable) return;
        el.contentEditable = true;
        el.focus();
        el.dataset.editing = "true"; // disable dragging

        try {
            const range = document.createRange();
            range.selectNodeContents(el);
            range.collapse(false);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        } catch (e) { /* ignore selection errors */ }
    }

    el.addEventListener("click", (ev) => { ev.stopPropagation(); enterEditMode(); });
    el.addEventListener("touchstart", (ev) => { ev.stopPropagation(); enterEditMode(); });

    // Exit edit mode on blur or Enter
    el.addEventListener("blur", () => {
        el.contentEditable = false;
        el.dataset.editing = "false";
        const pl = placements.find(pp => pp.el === el);
        if (pl) pl.text = el.textContent.trim();
    });
    el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") {
            ev.preventDefault();
            el.blur();
        }
    });

    // Rendered position
    const yRenderPx = yPx - (pxFont / 2);
    el.style.left = `${xPx}px`;
    el.style.top = `${yRenderPx}px`;

    overlayEl.appendChild(el);

    const id = `sig_${Date.now()}`;
    const placement = { id, page0, xPx, yPx, yRenderPx, pdfHpt, pxPerPtX, pxPerPtY, text: el.textContent, font, color, sizePt, overlayEl, el };
    placements.push(placement);

    selectPlacement(placement);
    enableDraggingForPlacement(placement);

    // Click/tap to select
    el.addEventListener("click", (ev) => { ev.stopPropagation(); selectPlacement(placement); });
    el.addEventListener("touchstart", (ev) => { ev.stopPropagation(); selectPlacement(placement); });

    // Add delete button
    const deleteBtn = document.createElement("div");
    deleteBtn.className = "sig-delete-btn";
    deleteBtn.innerHTML = '<i class="fas fa-times-circle"></i>';
    deleteBtn.addEventListener("mousedown", e => e.stopPropagation());
    deleteBtn.addEventListener("touchstart", e => e.stopPropagation());
    deleteBtn.addEventListener("click", () => deleteSelectedPlacement(el));
    deleteBtn.addEventListener("touchstart", () => deleteSelectedPlacement(el), { passive: false });
    el.appendChild(deleteBtn);
}


    
    /**
     * Selects a signature placement to enable modification and deletion.
     * @param {object} p The placement object to select.
     */
    function selectPlacement(p) {
        if (selectedPlacement && selectedPlacement.el) {
            selectedPlacement.el.classList.remove("selected");
            const oldBtn = selectedPlacement.el.querySelector(".sig-delete-btn");
            if (oldBtn) oldBtn.remove();
        }
        selectedPlacement = p;
        if (!p) return;

        p.el.classList.add("selected");
        const deleteBtn = document.createElement("div");
        deleteBtn.className = "sig-delete-btn";
        deleteBtn.innerHTML = '<i class="fas fa-times-circle"></i>';

        const handleDelete = (e) => {
            e.stopPropagation();
            deleteSelectedPlacement(p.el);
        };

        // Prevent drag from starting on the delete button
        deleteBtn.addEventListener("mousedown", (e) => e.stopPropagation());
        deleteBtn.addEventListener("touchstart", (e) => e.stopPropagation());

        deleteBtn.addEventListener("click", handleDelete);
        deleteBtn.addEventListener("touchstart", handleDelete, { passive: false });

        p.el.appendChild(deleteBtn);

        // Update control panel UI with selected placement's properties
        const fontEl = sigFontEls.item(0);
        const sizeEl = sigSizeEls.item(0);
        const colorEl = sigColorEls.item(0);
        
        if (fontEl) fontEl.value = p.font;
        if (sizeEl) sizeEl.value = p.sizePt;
        if (colorEl) colorEl.value = p.color;
    }

    /**
     * Deletes the currently selected signature placement.
     * @param {HTMLElement} targetEl The element to delete.
     */
    function deleteSelectedPlacement(targetEl = null) {
        const target = targetEl || selectedPlacement?.el;
        if (!target) return;
        const idx = placements.findIndex(p => p.el === target);
        if (idx >= 0) {
            placements[idx].el.remove();
            placements.splice(idx, 1);
            if (selectedPlacement?.el === target) selectedPlacement = null;
        }
    }
    
    /**
     * Enables dragging functionality for a signature placement.
     * @param {object} p The placement object.
     */
    function enableDraggingForPlacement(p) {
        let dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;
        function start(ev) {
            // if the element is currently in edit mode, don't start dragging
            if (p.el && p.el.isContentEditable) return;
            ev.preventDefault();
            dragging = true;
            const pt = ev.type.includes("touch") ? ev.touches[0] : ev;
            sx = pt.clientX; sy = pt.clientY;
            // Use the element's current rendered position as the starting point for dragging
            ox = p.el.offsetLeft;
            oy = p.el.offsetTop;
            selectPlacement(p);
        }
        function move(ev) {
            if (!dragging) return;
            ev.preventDefault();
            const pt = ev.type.includes("touch") ? ev.touches[0] : ev;
            const dx = pt.clientX - sx, dy = pt.clientY - sy;
            const rect = p.overlayEl.getBoundingClientRect();
            // Calculate new rendered position
            let nxRender = Math.max(0, Math.min(ox + dx, rect.width - p.el.offsetWidth));
            let nyRender = Math.max(0, Math.min(oy + dy, rect.height - p.el.offsetHeight));
            
            p.el.style.left = `${nxRender}px`;
            p.el.style.top = `${nyRender}px`;
            
            // Update the placement object's raw coordinates based on the new rendered position
            p.xPx = nxRender;
            p.yPx = nyRender + (p.el.offsetHeight / 2);
        }
        function end() { dragging = false; }

        p.el.addEventListener("mousedown", start);
        p.el.addEventListener("touchstart", start, { passive: false });
        document.addEventListener("mousemove", move);
        document.addEventListener("touchmove", move, { passive: false });
        document.addEventListener("mouseup", end);
        document.addEventListener("touchend", end);
    }
    
    /**
     * Displays a status message to the user on all relevant elements.
     * @param {string} message The message to display.
     * @param {boolean} isLoading If true, show a loading indicator.
     */
    function showStatus(message, isLoading = false) {
        jobStatusEls.forEach(el => {
            el.textContent = message;
        });
        // No loading indicator in this simplified version, but this is where it would go
    }

    // --- Event Listeners ---

    // File input listener
    fileInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) handleFile(file);
    });

    // Drag-and-drop listeners
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('highlight');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('highlight');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('highlight');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });

    // Synchronize the checkboxes
    sigEnableEls.forEach(el => el.addEventListener('change', (event) => {
        const isChecked = event.target.checked;
        sigEnableEls.forEach(checkbox => {
            if (checkbox !== event.target) {
                checkbox.checked = isChecked;
            }
        });
        if (isChecked && !selectedPlacement && placements.length === 0) {
            const firstPageOverlay = pagesContainer.querySelector('.overlay');
            if (firstPageOverlay) {
                const renderW = parseFloat(firstPageOverlay.dataset.renderW);
                const renderH = parseFloat(firstPageOverlay.dataset.renderH);
                createPlacement(firstPageOverlay, Math.round(renderW / 2), Math.round(renderH / 2));
            }
        }
    }));

    // Update signature styling from controls
    sigFontEls.forEach(el => el.addEventListener("change", () => {
        if (!selectedPlacement) return;
        selectedPlacement.font = el.value;
        selectedPlacement.el.style.fontFamily = `'${el.value}', cursive, sans-serif`;
    }));
    

    function updateSelectedPlacementFromControls() {
    if (!selectedPlacement) return;
    const fontEl = sigFontEls.item(0);
    const sizeEl = sigSizeEls.item(0);
    const colorEl = sigColorEls.item(0);

    if (fontEl) {
        selectedPlacement.font = fontEl.value;
        selectedPlacement.el.style.fontFamily = `'${fontEl.value}', cursive, sans-serif`;
    }
    if (sizeEl) {
        selectedPlacement.sizePt = parseInt(sizeEl.value, 10);
        const pxFont = Math.max(8, Math.round(selectedPlacement.sizePt * selectedPlacement.pxPerPtX));
        selectedPlacement.el.style.fontSize = `${pxFont}px`;
    }
    if (colorEl) {
        selectedPlacement.color = colorEl.value;
        selectedPlacement.el.style.color = colorEl.value;
    }
}

    sigSizeEls.forEach(el => el.addEventListener("input", () => {
        if (!selectedPlacement) return;
        selectedPlacement.sizePt = parseInt(el.value, 10);
        const pxFont = Math.max(8, Math.round(selectedPlacement.sizePt * selectedPlacement.pxPerPtX));
        selectedPlacement.el.style.fontSize = `${pxFont}px`;
    }));
    
    sigColorEls.forEach(el => el.addEventListener("change", () => {
        if (!selectedPlacement) return;
        selectedPlacement.color = el.value;
        selectedPlacement.el.style.color = el.value;
    }));

    // Finalize button listener
    btnFinalizeEls.forEach(el => el.addEventListener("click", async () => {
        if (!uploadedFilename) {
            // Use a custom message box
            showStatus("Please upload a PDF first.");
            return;
        }
        if (!placements.length) {
            // Use a custom message box
            showStatus("Add at least one signature.");
            return;
        }
        startFinalizingSpinner();
    
        const payload = {
            pdf_filename: uploadedFilename,
            placements: placements.map(p => {
                const y_adjustment_pixels = -12; // Increased to push signature down more
                return {
                    page_number: p.page0,
                    x: p.xPx / p.pxPerPtX,
                    y: p.pdfHpt - ((p.yPx - y_adjustment_pixels) / p.pxPerPtY),
                    text: p.text,
                    font: p.font,
                    color: p.color,
                    size_pt: p.sizePt
                };
            })
        };
    
        try {
            showStatus("Submitting signature job...");
            downloadAreaEls.forEach(el => el.innerHTML = ""); // Clear any old download buttons
            
            const res = await fetch("/api/pdf/sign-merge", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!res.ok) {
                const error = await res.json();
                throw new Error("Failed to submit signature job: " + error.error);
            }
            const data = await res.json();
            
            showStatus("Job submitted. Processing...");
    
            const jobId = data.job_id;
            const poll = setInterval(async () => {
                const r = await fetch(`/api/job/status/${encodeURIComponent(jobId)}`);
                if (!r.ok) return;
                const js = await r.json();
                
                showStatus(`Status: ${js.status}`);
                if (js.status === "finished") {
                    clearInterval(poll);
                    const filename = js.result;
                    downloadAreaEls.forEach(el => {
                        el.innerHTML = `<button onclick="window.location.href='/api/pdf/${encodeURIComponent(filename)}'">Download Signed PDF</button>`;
                    });
                    showStatus("Job finished! Ready to download.");
                    stopFinalizingSpinner();
                } else if (js.status === "failed") {
                    clearInterval(poll);
                    showStatus("Failed: " + (js.result || "Unknown error"));
                    stopFinalizingSpinner();
                }
            }, 1000);
        } catch (err) {
                stopFinalizingSpinner();

            console.error(err);
            showStatus("Error submitting job: " + err.message);
        }
    }));
})();
