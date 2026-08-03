/**
 * Client-side script for Plant Purity Testing Interface.
 * Manages Drag & Drop, File Upload Validation, REST API communications,
 * upload progress, and rendering prediction visualization results with Chart.js.
 */

document.addEventListener("DOMContentLoaded", () => {
    // UI Elements
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const browseBtn = document.getElementById("browseBtn");
    const uploadPrompt = document.getElementById("uploadPrompt");
    const previewContainer = document.getElementById("previewContainer");
    const imagePreview = document.getElementById("imagePreview");
    const removeBtn = document.getElementById("removeBtn");
    
    const errorAlert = document.getElementById("errorAlert");
    const errorText = document.getElementById("errorText");
    const actionArea = document.getElementById("actionArea");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const btnText = document.getElementById("btnText");
    const btnSpinner = document.getElementById("btnSpinner");
    
    const resultsCard = document.getElementById("resultsCard");
    const purityBadge = document.getElementById("purityBadge");
    const resPredictedClass = document.getElementById("resPredictedClass");
    const resConfidence = document.getElementById("resConfidence");
    const resTime = document.getElementById("resTime");
    const resReason = document.getElementById("resReason");
    
    const probFemaleBar = document.getElementById("probFemaleBar");
    const probFemaleVal = document.getElementById("probFemaleVal");
    const probHybridBar = document.getElementById("probHybridBar");
    const probHybridVal = document.getElementById("probHybridVal");
    const probMaleBar = document.getElementById("probMaleBar");
    const probMaleVal = document.getElementById("probMaleVal");
    
    const legendPureVal = document.getElementById("legendPureVal");
    const legendImpureVal = document.getElementById("legendImpureVal");
    
    let activeFile = null;
    let purityChart = null;

    // Supported extensions and max size (50MB limit)
    const ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'bmp', 'webp', 'dng', 'heic'];
    const MAX_FILE_SIZE = 50 * 1024 * 1024; 

    // ==============================================================================
    // DRAG AND DROP EVENT HANDLERS
    // ==============================================================================
    
    // Prevent browser default file open behavior on drag/drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Toggle drag state highlight borders
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'), false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const file = dt.files[0];
        if (file) {
            handleFileSelection(file);
        }
    });

    // Handle browse click
    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // prevent triggering dropZone click
        fileInput.click();
    });

    dropZone.addEventListener('click', () => {
        if (!activeFile) {
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) {
            handleFileSelection(file);
        }
    });

    // ==============================================================================
    // FILE VALIDATION AND PREVIEW
    // ==============================================================================
    
    function handleFileSelection(file) {
        hideError();
        hideResults();
        
        const fileExt = file.name.split('.').pop().toLowerCase();
        
        // 1. Validate File Format
        if (!ALLOWED_EXTENSIONS.includes(fileExt)) {
            showError(`Unsupported file format. Supported extensions: ${ALLOWED_EXTENSIONS.join(', ')}`);
            clearFileState();
            return;
        }

        // 2. Validate File Size (50 MB limit)
        if (file.size > MAX_FILE_SIZE) {
            showError("File size exceeds the 50 MB limit. Please select a smaller file.");
            clearFileState();
            return;
        }

        activeFile = file;
        
        // 3. Render client-side image preview (use server-side conversion for HEIC/DNG formats)
        if (fileExt === 'heic' || fileExt === 'dng') {
            // Show loading placeholder spinner
            imagePreview.src = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="224" height="224" viewBox="0 0 24 24" fill="none" stroke="%233b82f6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10" stroke-dasharray="30 30" stroke-dashoffset="0"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/></circle><text x="50%" y="60%" dominant-baseline="middle" text-anchor="middle" font-family="Outfit, sans-serif" font-size="2" fill="%23f8fafc">Generating Preview...</text></svg>`;
            uploadPrompt.style.display = "none";
            previewContainer.style.display = "flex";
            actionArea.style.display = "block";

            const formData = new FormData();
            formData.append("image", file);

            fetch("/convert-preview", {
                method: "POST",
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Preview generation failed.");
                }
                return response.json();
            })
            .then(data => {
                if (data.success && data.preview) {
                    // Update preview source with base64 converted JPEG
                    imagePreview.src = data.preview;
                } else {
                    throw new Error(data.error || "Preview generation failed.");
                }
            })
            .catch(err => {
                console.error("Error generating preview:", err);
                imagePreview.src = `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="224" height="224" viewBox="0 0 24 24" fill="none" stroke="%23ef4444" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><text x="50%" y="60%" dominant-baseline="middle" text-anchor="middle" font-family="Outfit, sans-serif" font-size="2.5" font-weight="600" fill="%23ef4444">PREVIEW FAILED</text></svg>`;
            });
        } else {
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                uploadPrompt.style.display = "none";
                previewContainer.style.display = "flex";
                actionArea.style.display = "block";
            };
            reader.onerror = () => {
                showError("Failed to read image file.");
                clearFileState();
            };
            reader.readAsDataURL(file);
        }
    }

    // Reset uploader state
    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // prevent triggering dropZone click
        clearFileState();
        hideResults();
        hideError();
    });

    function clearFileState() {
        activeFile = null;
        fileInput.value = "";
        imagePreview.src = "";
        previewContainer.style.display = "none";
        uploadPrompt.style.display = "flex";
        actionArea.style.display = "none";
    }

    // ==============================================================================
    // ERROR AND RESULTS TRANSITIONS
    // ==============================================================================
    
    function showError(message) {
        errorText.textContent = message;
        errorAlert.style.display = "flex";
    }

    function hideError() {
        errorAlert.style.display = "none";
    }

    function hideResults() {
        resultsCard.style.display = "none";
        resultsCard.className = "card results-card";
    }

    function resetAnalyzeButtonState() {
        analyzeBtn.disabled = false;
        removeBtn.disabled = false;
        browseBtn.disabled = false;
        dropZone.style.pointerEvents = "auto";
        dropZone.classList.remove("disabled");
        btnText.innerHTML = '<i class="fa-solid fa-credit-card mr-2"></i> Pay ₹99 & Analyze Specimen';
        btnSpinner.style.display = "none";
        btnSpinner.classList.add("hidden");
    }

    // ==============================================================================
    // REST API - RAZORPAY PAYMENT GATEWAY & INFERENCE PIPELINE GATING
    // ==============================================================================
    
    analyzeBtn.addEventListener('click', () => {
        if (!activeFile || analyzeBtn.disabled) return;

        // Set Loading & Disabled State
        analyzeBtn.disabled = true;
        removeBtn.disabled = true;
        browseBtn.disabled = true;
        dropZone.style.pointerEvents = "none";
        dropZone.classList.add("disabled");
        btnText.textContent = "Creating Order...";
        btnSpinner.style.display = "inline-block";
        btnSpinner.classList.remove("hidden");
        hideError();
        hideResults();

        const formData = new FormData();
        formData.append("image", activeFile);

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        const xhr = new XMLHttpRequest();

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                if (percentComplete < 100) {
                    btnText.textContent = `Preparing Specimen (${percentComplete}%)...`;
                } else {
                    btnText.textContent = "Opening Payment Gateway...";
                }
            }
        };

        xhr.onload = function() {
            let data = null;
            try {
                data = JSON.parse(xhr.responseText);
            } catch (err) {
                data = null;
            }

            if (xhr.status >= 200 && xhr.status < 300 && data && data.success) {
                // Step 2: Open Razorpay Standard Checkout Modal
                openRazorpayCheckout(data);
            } else {
                const msg = (data && data.error) ? data.error : "Failed to initialize payment order.";
                showError(msg);
                resetAnalyzeButtonState();
            }
        };

        xhr.onerror = function() {
            showError("Network connection error. Please check your internet connection.");
            resetAnalyzeButtonState();
        };

        xhr.timeout = 60000;
        xhr.open("POST", "/create-order", true);
        if (csrfToken) {
            xhr.setRequestHeader("X-CSRFToken", csrfToken);
        }
        xhr.send(formData);
    });

    function openRazorpayCheckout(orderData) {
        btnText.textContent = "Awaiting Payment...";
        
        const options = {
            "key": orderData.key_id,
            "amount": orderData.amount,
            "currency": orderData.currency,
            "name": "Genetic Purity AI",
            "description": "Plant Specimen Purity Analysis",
            "order_id": orderData.order_id,
            "handler": function (response) {
                // Payment Successful! Now send parameters to server for HMAC verification & prediction execution
                btnText.textContent = "Verifying Payment & Running Diagnostics...";
                verifyPaymentAndPredict({
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_signature: response.razorpay_signature,
                    temp_token: orderData.temp_token,
                    original_filename: orderData.original_filename
                });
            },
            "modal": {
                "ondismiss": function() {
                    showError("Payment cancelled. Plant purity prediction was not performed.");
                    resetAnalyzeButtonState();
                }
            },
            "theme": {
                "color": "#10b981"
            }
        };

        try {
            const rzp = new Razorpay(options);
            rzp.on('payment.failed', function(response) {
                const desc = response.error ? response.error.description : "Payment failed.";
                showError(`Payment failed: ${desc}. Prediction blocked.`);
                resetAnalyzeButtonState();
            });
            rzp.open();
        } catch (e) {
            console.error("Razorpay SDK Error:", e);
            // Fallback for dev mode when Razorpay JS script is blocked or in dev bypass mode
            showError("Opening payment gateway... (Dev Mode: Verifying direct order)");
            verifyPaymentAndPredict({
                razorpay_order_id: orderData.order_id,
                razorpay_payment_id: "pay_dev_mock123",
                razorpay_signature: "sig_dev_mock123",
                temp_token: orderData.temp_token,
                original_filename: orderData.original_filename
            });
        }
    }

    function verifyPaymentAndPredict(paymentPayload) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        fetch("/verify-payment", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken
            },
            body: JSON.stringify(paymentPayload)
        })
        .then(res => {
            return res.json().then(data => ({ status: res.status, body: data }));
        })
        .then(resData => {
            if (resData.status >= 200 && resData.status < 300 && resData.body.success) {
                renderResults(resData.body);
            } else {
                showError(resData.body.error || "Payment verification failed. Fake callback blocked.");
            }
            resetAnalyzeButtonState();
        })
        .catch(err => {
            showError("Network error during payment verification: " + err.message);
            resetAnalyzeButtonState();
        });
    }

    // ==============================================================================
    // RESULT RENDERING AND CHART CREATION
    // ==============================================================================
    
    function renderResults(result) {
        // Set styling class for results card border based on purity status
        const isUnknown = result.class === "UNKNOWN" || result.purity.toLowerCase().includes("unknown");
        const isPure = !isUnknown && result.purity.toLowerCase().startsWith("pure");
        
        let cardStyleClass = "status-impure";
        if (isUnknown) {
            cardStyleClass = "status-unknown";
        } else if (isPure) {
            cardStyleClass = "status-pure";
        }
        
        resultsCard.className = `card results-card ${cardStyleClass}`;
        
        // Update purity status badge
        purityBadge.querySelector('span').textContent = result.purity;
        
        // Key details mapping
        resPredictedClass.textContent = result.class;
        resConfidence.textContent = result.confidence;
        resTime.textContent = result.prediction_time;
        resReason.textContent = result.reason;
        
        // Extract raw probability percentages (Female, Hybrid, Male)
        const femaleVal = result.probabilities.female || 0;
        const hybridVal = result.probabilities.hybrid || 0;
        const maleVal = result.probabilities.male || 0;
        
        // Populate probability progress bars and values
        probFemaleBar.style.width = `${femaleVal}%`;
        probFemaleVal.textContent = `${femaleVal.toFixed(2)}%`;
        
        probHybridBar.style.width = `${hybridVal}%`;
        probHybridVal.textContent = `${hybridVal.toFixed(2)}%`;
        
        probMaleBar.style.width = `${maleVal}%`;
        probMaleVal.textContent = `${maleVal.toFixed(2)}%`;

        if (isUnknown) {
            legendPureVal.textContent = "0.00%";
            legendImpureVal.textContent = "0.00%";
            // Initialize or update Chart.js Doughnut Chart with unknown state
            updateChart(0, 0, true);
        } else {
            // Calculate Pure vs Impure chart values
            const pureConfidence = hybridVal;
            const impureConfidence = femaleVal + maleVal;
            
            legendPureVal.textContent = `${pureConfidence.toFixed(2)}%`;
            legendImpureVal.textContent = `${impureConfidence.toFixed(2)}%`;

            // Initialize or update Chart.js Doughnut Chart
            updateChart(pureConfidence, impureConfidence, false);
        }
        
        // Display results block
        resultsCard.style.display = "block";
        
        // Smoothly scroll down to results panel
        resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function updateChart(pureVal, impureVal, isUnknown = false) {
        const ctx = document.getElementById("purityChart").getContext("2d");
        
        // If chart already exists, destroy it before recreating to avoid visual bugs
        if (purityChart) {
            purityChart.destroy();
        }

        const labels = isUnknown ? ["Unknown Specimen"] : ["Pure Confidence", "Impure Confidence"];
        const data = isUnknown ? [100] : [pureVal, impureVal];
        const colors = isUnknown ? ["#f59e0b"] : ["#10b981", "#f43f5e"];

        purityChart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderColor: "#121824", // matches card bg
                    borderWidth: 3,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "75%",
                plugins: {
                    legend: {
                        display: false // legend rendered via HTML custom labels
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (isUnknown) {
                                    return ` ${context.label}: Non-plant or Unknown`;
                                }
                                return ` ${context.label}: ${context.raw.toFixed(2)}%`;
                            }
                        }
                    }
                }
            }
        });
    }

    // ==============================================================================
    // SERVER STATUS CHECK PIPELINE
    // ==============================================================================
    const statusBadge = document.getElementById("serverStatusBadge");
    let isServerOnline = true;

    function checkServerStatus() {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 seconds timeout

        fetch("/health", { signal: controller.signal })
            .then(response => {
                clearTimeout(timeoutId);
                if (response.ok) {
                    return response.json();
                }
                throw new Error("Server response not OK");
            })
            .then(data => {
                if (data.status === "online" || data.status === "healthy") {
                    setOnlineState();
                } else {
                    setOfflineState();
                }
            })
            .catch(error => {
                clearTimeout(timeoutId);
                setOfflineState();
            });
    }

    function setOnlineState() {
        isServerOnline = true;
        statusBadge.textContent = "🟢 ONLINE";
        statusBadge.className = "project-tag status-online";
        
        // Re-enable UI components if not currently uploading
        if (btnText.textContent === "Analyze Plant Specimen") {
            dropZone.classList.remove("disabled");
            browseBtn.classList.remove("disabled");
            browseBtn.disabled = false;
            analyzeBtn.classList.remove("disabled");
            analyzeBtn.disabled = false;
        }
        
        // If the offline message is currently visible, hide it
        if (errorText.textContent === "Prediction service is currently unavailable. Please try again later.") {
            hideError();
        }
    }

    function setOfflineState() {
        isServerOnline = false;
        statusBadge.textContent = "🔴 OFFLINE";
        statusBadge.className = "project-tag status-offline";
        
        // Disable UI components
        dropZone.classList.add("disabled");
        browseBtn.classList.add("disabled");
        browseBtn.disabled = true;
        analyzeBtn.classList.add("disabled");
        analyzeBtn.disabled = true;
        
        // Reset current file selection
        clearFileState();
        hideResults();
        
        // Display friendly offline notice
        showError("Prediction service is currently unavailable. Please try again later.");
    }

    // Run initial health check immediately
    checkServerStatus();

    // Periodically query the server status every 5 seconds
    setInterval(checkServerStatus, 5000);
});
