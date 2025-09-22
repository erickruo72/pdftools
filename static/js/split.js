
    const fileInput = document.getElementById('file-input');
    const filePreview = document.getElementById('file-preview');
    const fileName = document.getElementById('file-name');
    const removeFileBtn = document.getElementById('remove-file');
    const uploadSection = document.getElementById('upload-section');
    const splitOptionsContainer = document.getElementById('split-options');
    const splitOption = document.getElementById('split-option');
    const rangeInputs = document.getElementById('range-inputs');
    const splitButton = document.getElementById('split-button');
    const jobStatusSection = document.getElementById('job-status-section');
    const statusMessage = document.getElementById('status-message');
    const downloadLink = document.getElementById('download-link');
    const messageContainer = document.getElementById('message-container');

    const fileSizeElem = document.getElementById('file-size');
    
    const fileUploadStatus = document.getElementById('file-upload-status');
    const fileUploadProgressBar = document.getElementById('file-upload-progress-bar');
    const fileUploadPercentage = document.getElementById('file-upload-percentage');

    const processingProgressBarContainer = document.getElementById('processing-progress-container');
    const processingProgressBar = document.getElementById('processing-progress-bar');

    let uploadedFilePath = null;
    let fakeProgressInterval = null; // New interval for the fake progress bar
    let realProgressReceived = false; // Flag to stop the fake progress

    function showMessage(message, type) {
        messageContainer.textContent = message;
        messageContainer.classList.remove('hidden', 'error', 'success');
        if (type === 'error') {
            messageContainer.classList.add('error');
        } else if (type === 'success') {
            messageContainer.classList.add('success');
        }
        setTimeout(() => messageContainer.classList.add('hidden'), 5000);
    }

    function resetUI() {
        fileInput.value = '';
        filePreview.classList.add('hidden');
        uploadSection.classList.remove('hidden');
        splitOptionsContainer.classList.add('hidden');
        splitButton.classList.add('hidden');
        jobStatusSection.classList.add('hidden');
        downloadLink.classList.add('hidden');
        messageContainer.classList.add('hidden');
        splitOption.value = '';
        rangeInputs.classList.add('hidden');
        document.getElementById('start-page').value = '';
        document.getElementById('end-page').value = '';
        uploadedFilePath = null;
        fileUploadStatus.classList.add('hidden');
        removeFileBtn.classList.add('hidden');
        fileUploadProgressBar.style.width = '0%';
        fileUploadPercentage.textContent = '0%';
        processingProgressBar.style.width = '0%';
        processingProgressBar.classList.remove('pulsing-progress');
        
        // Clear the fake progress interval on reset
        if (fakeProgressInterval) {
            clearInterval(fakeProgressInterval);
            fakeProgressInterval = null;
        }
    }

    function uploadFile(file) {
        uploadSection.classList.add('hidden');
        filePreview.classList.remove('hidden');
        fileUploadStatus.classList.remove('hidden');
        removeFileBtn.classList.add('hidden');
        
        fileName.textContent = file.name;
        fileSizeElem.textContent = `(${ (file.size / 1024 / 1024).toFixed(2) } MB)`;

        const formData = new FormData();
        formData.append('files', file); 
        
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/upload');

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                fileUploadProgressBar.style.width = `${percent}%`;
                fileUploadPercentage.textContent = `${percent}%`;
            }
        });

        xhr.onreadystatechange = () => {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        const fileData = data.files && data.files[0] ? data.files[0] : null;

                        if (fileData && fileData.path) {
                            uploadedFilePath = fileData.path;
                            fileUploadStatus.classList.add('hidden');
                            removeFileBtn.classList.remove('hidden');
                            showMessage('File uploaded successfully. Please select your split options.', 'success');
                            
                            const reader = new FileReader();
                            reader.onload = async (e) => {
                                const arrayBuffer = e.target.result;
                                try {
                                    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
                                    const pageCount = pdf.numPages;
                                    splitButton.dataset.pageCount = pageCount;
                                    splitOptionsContainer.classList.remove('hidden');
                                    splitButton.classList.remove('hidden');
                                } catch (error) {
                                    showMessage('Failed to read PDF. Please try a different file.', 'error');
                                    console.error("PDF reading error:", error);
                                    resetUI();
                                }
                            };
                            reader.readAsArrayBuffer(file);
                        } else {
                            throw new Error('Server response missing expected file data.');
                        }
                    } catch (e) {
                        showMessage('Failed to process server response. Please try again.', 'error');
                        console.error(e);
                        resetUI();
                    }
                } else {
                    showMessage(`Failed to upload ${file.name}.`, 'error');
                    resetUI();
                }
            }
        };

        xhr.send(formData);
    }
    
    function handleFile(file) {
        if (!file || file.type !== 'application/pdf') {
            showMessage('Please upload a valid PDF file.', 'error');
            resetUI();
            return;
        }

        if (file.size > 200 * 1024 * 1024) {
            showMessage('File size exceeds the 200MB limit.', 'error');
            resetUI();
            return;
        }
        
        uploadFile(file);
    }

    // --- Event Listeners ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadSection.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadSection.addEventListener(eventName, () => uploadSection.classList.add('highlight'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadSection.addEventListener(eventName, () => uploadSection.classList.remove('highlight'), false);
    });

    uploadSection.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const file = dt.files[0];
        handleFile(file);
    }, false);
    
    uploadSection.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFile(file);
        }
    });

    removeFileBtn.addEventListener('click', resetUI);

    splitOption.addEventListener('change', () => {
        if (splitOption.value === 'range') {
            rangeInputs.classList.remove('hidden');
        } else {
            rangeInputs.classList.add('hidden');
        }
    });

    splitButton.addEventListener('click', async () => {
        if (!uploadedFilePath) {
            showMessage('File not uploaded. Please upload a PDF file first.', 'error');
            return;
        }

        if (!splitOption.value) {
            showMessage('Please select a split option.', 'error');
            return;
        }

        splitOptionsContainer.classList.add('hidden');
        splitButton.classList.add('hidden');
        filePreview.classList.add('hidden');
        jobStatusSection.classList.remove('hidden');
        
        processingProgressBarContainer.classList.remove('hidden');
        processingProgressBar.classList.add('pulsing-progress');
        statusMessage.textContent = 'Starting processing...';
        messageContainer.classList.add('hidden');
        
        // --- START OF THE NEW FIX: Implement a fake progress bar timer ---
        let fakeProgress = 0;
        const fakeProgressLimit = 95; // Stop the fake progress just before 100%
        
        if (fakeProgressInterval) {
            clearInterval(fakeProgressInterval);
        }

        fakeProgressInterval = setInterval(() => {
            if (!realProgressReceived && fakeProgress < fakeProgressLimit) {
                // Increment based on a sigmoid or simple linear function
                // This makes it look like it's calculating something
                fakeProgress += 2; 
                processingProgressBar.style.width = `${fakeProgress}%`;
                statusMessage.textContent = `Processing: ${fakeProgress}%`;
            } else if (fakeProgress >= fakeProgressLimit) {
                // Hold the fake progress at a high percentage to avoid jumping
                clearInterval(fakeProgressInterval);
            }
        }, 50); // Update the UI every 50 milliseconds for a smooth animation
        // --- END OF THE NEW FIX ---

        const formData = new FormData();
        formData.append('file_path', uploadedFilePath);
        formData.append('split_option', splitOption.value);
        
        const pageCount = parseInt(splitButton.dataset.pageCount, 10);
        if (splitOption.value === 'range') {
            const startPage = parseInt(document.getElementById('start-page').value, 10);
            const endPage = parseInt(document.getElementById('end-page').value, 10);
            
            if (isNaN(startPage) || isNaN(endPage) || startPage < 1 || endPage < startPage || endPage > pageCount) {
                showMessage(`Please enter a valid page range between 1 and ${pageCount}.`, 'error');
                resetUI();
                return;
            }
            formData.append('start_page', startPage);
            formData.append('end_page', endPage);
            downloadLink.textContent = 'Download PDF';
        } else {
            downloadLink.textContent = 'Download ZIP';
        }
        
        try {
            const splitResponse = await fetch('/api/split', {
                method: 'POST',
                body: formData
            });

            if (!splitResponse.ok) {
                const err = await splitResponse.json();
                throw new Error(err.error || 'Failed to submit split job.');
            }

            const data = await splitResponse.json();
            const jobId = data.job_id;
            statusMessage.textContent = 'Job submitted. Processing...';

            const jobPollingInterval = setInterval(async () => {
                const statusRes = await fetch(`/api/job/status/${jobId}`);
                const statusData = await statusRes.json();
                
                if (statusData.progress !== undefined) {
                    const percentage = Math.round(statusData.progress);
                    
                    if (percentage > 0) {
                        realProgressReceived = true; // Flag that real data is here
                        if (fakeProgressInterval) {
                            clearInterval(fakeProgressInterval);
                            fakeProgressInterval = null;
                        }
                        processingProgressBar.classList.remove('pulsing-progress');
                    }
                    
                    // New fix: Only update the progress bar if the new value is higher than the current.
                    const currentVisualProgress = parseFloat(processingProgressBar.style.width);
                    if (percentage > currentVisualProgress) {
                        processingProgressBar.style.width = `${percentage}%`;
                        statusMessage.textContent = `Processing: ${percentage}%`;
                    }
                } else {
                    statusMessage.textContent = `Status: ${statusData.status.charAt(0).toUpperCase() + statusData.status.slice(1)}...`;
                }

                if (statusData.status === 'finished') {
                    clearInterval(jobPollingInterval);
                    if (fakeProgressInterval) clearInterval(fakeProgressInterval);
                    
                    processingProgressBar.style.width = '100%';
                    statusMessage.textContent = 'Splitting complete!';
                    
                    jobStatusSection.classList.add('hidden');
                    downloadLink.href = `/api/job/download/${statusData.result}`;
                    downloadLink.classList.remove('hidden');
                    showMessage('Your split files are ready!', 'success');
                } else if (statusData.status === 'failed') {
                    clearInterval(jobPollingInterval);
                    if (fakeProgressInterval) clearInterval(fakeProgressInterval);
                    statusMessage.textContent = 'Splitting failed.';
                    jobStatusSection.classList.add('hidden');
                    showMessage(`Error: ${statusData.result}`, 'error');
                    resetUI();
                }
            }, 500); // Polling every 500ms for a smoother experience

        } catch (error) {
            jobStatusSection.classList.add('hidden');
            resetUI();
            showMessage(error.message || 'An unexpected error occurred.', 'error');
            console.error(error);
        }
    });
