  const input = document.getElementById('pdfFile');
  const uploadSection = document.getElementById('uploadSection');
  const fileStatusArea = document.getElementById('fileStatusArea');
  const fileName = document.getElementById('pdfFileName');
  const fileSize = document.getElementById('pdfFileSize');
  const statusMessageContainer = document.getElementById('statusMessageContainer');
  const previewContainer = document.getElementById('previewContainer');
  const submitBtn = document.getElementById('submitBtn');
  const downloadBtn = document.getElementById('downloadBtn');
  const progressContainer = document.getElementById('progressContainer');
  const progressBar = document.getElementById('progressBar');
  const postDownloadSection = document.getElementById('post-download-section');

  let uploadedFile = null;
  let totalPages = 0;

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const truncateFileName = (name) => {
    const maxChars = 9;
    const parts = name.split('.');
    const baseName = parts.slice(0, -1).join('.');
    const extension = parts.pop();
    if (baseName.length > maxChars) {
      return `${baseName.slice(0, maxChars)}...${extension}`;
    }
    return name;
  };

  const updateStatus = (message, type = 'normal') => {
    statusMessageContainer.innerHTML = '';
    const span = document.createElement('span');
    span.className = 'status-text';
    span.textContent = message;
    if (type === 'error') span.style.color = 'red';
    statusMessageContainer.appendChild(span);
  };

  const showProgress = () => {
    progressContainer.style.display = 'block';
    progressBar.style.width = '0%';
  };

  const updateProgress = (percent, message) => {
    progressBar.style.width = percent + '%';
    updateStatus(`${message} ${percent}%`);
  };

  const hideProgress = () => {
    progressContainer.style.display = 'none';
    progressBar.style.width = '0%';
  };

  // Drag and drop
  ['dragenter','dragover','dragleave','drop'].forEach(eventName => {
    uploadSection.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); });
  });
  uploadSection.addEventListener('drop', (e) => {
    handlePDFUpload(e.dataTransfer.files[0]);
  });
  uploadSection.addEventListener('click', () => input.click());
  input.addEventListener('change', () => handlePDFUpload(input.files[0]));

  async function handlePDFUpload(file) {
    if (!file || file.type !== 'application/pdf') {
      updateStatus('Please upload a valid PDF file.', 'error');
      return;
    }
    if (file.size > 200 * 1024 * 1024) {
      updateStatus('File size exceeds 200MB.', 'error');
      return;
    }

    uploadedFile = file;
    uploadSection.style.display = 'none';
    fileStatusArea.style.display = 'flex';
    fileName.textContent = truncateFileName(file.name);
    fileSize.textContent = formatBytes(file.size);

    updateStatus('Generating page previews...');
    showProgress();

    const formData = new FormData();
    formData.append('pdf_file', file);

    let poll = null;
    try {
      const res = await fetch('/api/remove/previews', { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to start preview job.');
      const jobId = data.job_id;

      let progress = 0;
      poll = setInterval(async () => {
        progress = Math.min(progress + 10, 90);
        updateProgress(progress, 'Generating page previews...');

        const statusRes = await fetch(`/api/job/status/${jobId}`);
        const statusData = await statusRes.json();

        if (statusData.status === 'finished') {
          clearInterval(poll);
          hideProgress();
          if (!Array.isArray(statusData.result)) throw new Error('Invalid preview data.');
          totalPages = statusData.result.length;
          previewContainer.innerHTML = '';
          statusData.result.sort((a,b) => a.page-b.page).forEach(pageObj => {
            const div = document.createElement('div');
            div.className = 'page-preview';
            div.dataset.page = pageObj.page;

            const img = document.createElement('img');
            img.src = `/previews/${pageObj.filename}`;
            img.loading = 'lazy';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = pageObj.page;
            checkbox.style.display = 'none';

            const label = document.createElement('span');
            label.className = 'page-number-label';
            label.textContent = pageObj.page;

            div.addEventListener('click', () => {
              div.classList.toggle('selected');
              checkbox.checked = !checkbox.checked;
              const selected = document.querySelectorAll('.page-preview.selected').length;
              submitBtn.disabled = selected === 0 || selected === totalPages;
            });

            div.appendChild(img);
            div.appendChild(label);
            div.appendChild(checkbox);
            previewContainer.appendChild(div);
          });
          updateStatus('PDF loaded. Select pages to remove.', 'success');
          previewContainer.style.display = 'flex';
          submitBtn.style.display = 'inline-flex';
          submitBtn.disabled = true;
        }
        else if (statusData.status === 'failed') {
          clearInterval(poll);
          throw new Error('Preview generation failed.');
        }
      }, 1500);
    } catch (err) {
      if (poll) clearInterval(poll);
      updateStatus(err.message, 'error');
      uploadSection.style.display = 'flex';
      fileStatusArea.style.display = 'none';
    }
  }

  submitBtn.addEventListener("click", async () => {
    if (!uploadedFile) return updateStatus('No PDF loaded!', 'error');
    const selectedPages = Array.from(document.querySelectorAll('.page-preview.selected')).map(el => el.dataset.page);
    if (selectedPages.length === 0) return updateStatus('Please select at least one page.', 'error');
    if (selectedPages.length === totalPages) return updateStatus('Cannot remove all pages.', 'error');

    submitBtn.disabled = true;
    submitBtn.style.display = 'none';
    downloadBtn.style.display = 'none';

    updateStatus('Removing pages...');
    showProgress();

    const formData = new FormData();
    formData.append('pdf_file', uploadedFile);
    formData.append('selected_pages', selectedPages.join(','));

    let poll = null;
    try {
      const res = await fetch('/api/remove', { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to submit removal job.');
      const jobId = data.job_id;

      let progress = 0;
      poll = setInterval(async () => {
        progress = Math.min(progress + 15, 90);
        updateProgress(progress, 'Removing pages...');

        const statusRes = await fetch(`/api/job/status/${jobId}`);
        const statusData = await statusRes.json();

        if (statusData.status === 'finished') {
          clearInterval(poll);
          hideProgress();
          updateStatus('Removal complete!', 'success');

          // Hide previews after result is ready
          previewContainer.style.display = 'none';

          // Show download button
          downloadBtn.href = `/api/job/download/${statusData.result}`;
          downloadBtn.style.display = 'inline-flex';

          // Show post-download section
          postDownloadSection.classList.remove('d-none');
        }
        else if (statusData.status === 'failed') {
          clearInterval(poll);
          throw new Error('Removal failed.');
        }
      }, 1500);
    } catch (err) {
      if (poll) clearInterval(poll);
      updateStatus(err.message, 'error');
      submitBtn.style.display = 'inline-flex';
      submitBtn.disabled = false;
      hideProgress();
    }
  });
