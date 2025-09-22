    const hamburger = document.getElementById('tpdf-hamburger-btn');
    const mobileMenu = document.getElementById('tpdf-mobile-menu');
    const closeBtn = document.getElementById('tpdf-close-btn');
    const mobileDropdownToggle = document.getElementById('tpdf-mobile-dropdown-toggle');
    const dropdownContent = document.getElementById('tpdf-mobile-dropdown-content');

    hamburger.addEventListener('click', () => {
      mobileMenu.classList.toggle('active');
    });


    closeBtn.addEventListener('click', () => {
      mobileMenu.classList.remove('active');
    });


    mobileDropdownToggle.addEventListener('click', (e) => {
      e.preventDefault();
      dropdownContent.classList.toggle('active');
    });


    window.addEventListener('resize', () => {
      if (window.innerWidth > 992) {
        mobileMenu.classList.remove('active');
      }
    });


    // Get all menu links
const menuLinks = document.querySelectorAll('.tpdf-nav-links > li > a');

// Loop through each link and add active class to the current one based on URL
menuLinks.forEach(link => {
  if (window.location.pathname === link.getAttribute('href')) {
    link.classList.add('active'); // Add active class to the current link
  } else {
    link.classList.remove('active'); // Remove active class from other links
  }
});

const fileInput = document.getElementById('file-input');
const uploadSection = document.getElementById('upload-section');
const filePreviewSection = document.getElementById('file-preview-section');
const fileList = document.getElementById('file-list');
const addMoreButton = document.getElementById('add-more-button');
const mergeButton = document.getElementById('merge-button');
const jobStatusSection = document.getElementById('job-status-section');
const statusMessage = document.getElementById('status-message');
const jobProgressBar = document.getElementById('job-progress-bar');
const jobProgress = document.getElementById('job-progress');
const downloadSection = document.getElementById('download-section');
const downloadLink = document.getElementById('download-link');
const messageContainer = document.getElementById('message-container');
const postDownloadSection = document.getElementById('post-download-section');

let uploadedFiles = [];
let jobPollingInterval;
let draggingItem = null;

function showMessage(message, type) {
    messageContainer.textContent = message;
    messageContainer.classList.remove('d-none', 'error-message', 'success-message');
    messageContainer.classList.add(type === 'success' ? 'success-message' : 'error-message');
    setTimeout(() => messageContainer.classList.add('d-none'), 5000);
}

function handleFiles(files) {
    [...files].forEach(file => {
        if (uploadedFiles.find(f => f.original_name === file.name)) {
            showMessage(`${file.name} already uploaded.`, 'error');
            return;
        }

        uploadedFiles.push({ original_name: file.name, status: 'uploading', progress: 0 });
        renderFiles();

        uploadFile(file);
    });

    if (uploadedFiles.length > 0) {
        uploadSection.classList.add('d-none');
        filePreviewSection.classList.remove('d-none');
    }
}

function uploadFile(file) {
    const formData = new FormData();
    formData.append('files', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload');

    xhr.upload.addEventListener('progress', e => {
        if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            const idx = uploadedFiles.findIndex(f => f.original_name === file.name);
            if (idx !== -1) uploadedFiles[idx].progress = percent;
            renderFiles();
        }
    });

    xhr.onreadystatechange = () => {
        if (xhr.readyState === 4) {
            const idx = uploadedFiles.findIndex(f => f.original_name === file.name);
            if (xhr.status === 200) {
                const data = JSON.parse(xhr.responseText);
                if (idx !== -1 && data.files && data.files[0]) {
                    uploadedFiles[idx] = { ...data.files[0], status: 'done', progress: 100 };
                }
                renderFiles();
            } else {
                if (idx !== -1) uploadedFiles.splice(idx, 1);
                renderFiles();
                showMessage(`Failed to upload ${file.name}`, 'error');
            }
        }
    };

    xhr.send(formData);
}

function renderFiles() {
    fileList.innerHTML = '';
    uploadedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item position-relative';
        fileItem.dataset.index = index;
        fileItem.draggable = file.status === 'done';

        let content = '';
        if (file.status === 'uploading') {
        content = `
            <div class="d-flex flex-column align-items-center w-100">
                <div class="spinner"></div>
                <div class="file-progress-bar">
                    <div class="file-progress" style="width:${file.progress}%;"></div>
                </div>
                <span class="small text-secondary mt-1">${file.progress}%</span>
            </div>`;
            }
        else {
            content = `
                <button class="remove-btn" title="Remove file">✖</button>
                <i class="fas fa-file-pdf file-icon"></i>
                <span class="hidden-name" title="${file.original_name}">${file.original_name}</span>
                <span class="file-pages">${file.pages || ''} pages</span>`;
        }

        fileItem.innerHTML = content;
        fileList.appendChild(fileItem);
    });

    addDragAndDropListeners();
    addRemoveListeners();
}

function addDragAndDropListeners() {
    const items = fileList.querySelectorAll('.file-item');
    items.forEach(item => {
        item.addEventListener('dragstart', e => {
            draggingItem = item;
            e.dataTransfer.effectAllowed = 'move';
            item.classList.add('dragging');
        });
        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            draggingItem = null;
            const newOrder = Array.from(fileList.children).map(el => uploadedFiles[el.dataset.index]);
            uploadedFiles = newOrder;
            renderFiles();
        });
        item.addEventListener('dragover', e => {
            e.preventDefault();
            if (draggingItem && draggingItem !== item) {
                const rect = item.getBoundingClientRect();
                const isBefore = e.clientY < rect.top + rect.height / 2;
                fileList.insertBefore(draggingItem, isBefore ? item : item.nextSibling);
            }
        });
    });
}

function addRemoveListeners() {
    const removeButtons = fileList.querySelectorAll('.remove-btn');
    removeButtons.forEach(btn => {
        btn.addEventListener('click', e => {
            const item = e.target.closest('.file-item');
            const index = parseInt(item.dataset.index, 10);
            uploadedFiles.splice(index, 1);
            renderFiles();
        });
    });
}

uploadSection.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => handleFiles(e.target.files));
addMoreButton.addEventListener('click', () => fileInput.click());
['dragenter','dragover','dragleave','drop'].forEach(ev =>
    uploadSection.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); })
);
['dragenter','dragover'].forEach(ev =>
    uploadSection.addEventListener(ev, () => uploadSection.classList.add('highlight'))
);
['dragleave','drop'].forEach(ev =>
    uploadSection.addEventListener(ev, () => uploadSection.classList.remove('highlight'))
);
uploadSection.addEventListener('drop', e => handleFiles(e.dataTransfer.files));

mergeButton.addEventListener('click', async () => {
    if (uploadedFiles.length < 2) {
        showMessage('Add at least 2 PDF files.', 'error');
        return;
    }

    const allFilesUploaded = uploadedFiles.every(file => file.status === 'done');
    if (!allFilesUploaded) {
        showMessage('Please wait for all files to finish uploading.', 'error');
        return;
    }

    filePreviewSection.classList.add('d-none');
    jobStatusSection.classList.remove('d-none');
    jobProgressBar.classList.remove('d-none');
    jobProgress.style.width = '0%';
    statusMessage.textContent = 'Submitting job...';
    downloadSection.classList.add('d-none');
    postDownloadSection.classList.add('d-none');

    try {
        const response = await fetch('/api/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: uploadedFiles })
        });
        const data = await response.json();
        if (!response.ok) {
            showMessage(data.error || 'Failed to submit job.', 'error');
            return;
        }

        const jobId = data.job_id;
        statusMessage.textContent = 'Job submitted. Waiting for processing...';
        jobPollingInterval = setInterval(() => pollJobStatus(jobId), 1000);

    } catch (error) {
        console.error(error);
        showMessage('Error during job submission.', 'error');
    }
});

async function pollJobStatus(jobId) {
    try {
        const response = await fetch(`/api/job/status/${jobId}`);
        const data = await response.json();

        if (data.status === 'finished') {
            clearInterval(jobPollingInterval);
            statusMessage.textContent = 'Merging complete!';
            jobProgress.style.width = '100%';
            jobStatusSection.classList.add('d-none');

            downloadLink.href = `/api/job/download/${data.result}`;
            downloadSection.classList.remove('d-none');
            postDownloadSection.classList.remove('d-none'); // Show the new section
            showMessage('Your PDF is ready for download!', 'success');

        } else if (data.status === 'failed') {
            clearInterval(jobPollingInterval);
            statusMessage.textContent = `Merging failed: ${data.result}`;
            jobStatusSection.classList.add('d-none');
            showMessage('An error occurred during the merge.', 'error');
        } else {
            statusMessage.textContent = `Status: ${data.status}...`;
            if (data.progress) jobProgress.style.width = data.progress + '%';
        }
    } catch (error) {
        clearInterval(jobPollingInterval);
        statusMessage.textContent = 'Failed to connect to the server.';
        jobStatusSection.classList.add('d-none');
        showMessage('Lost connection to the server.', 'error');
    }
}
