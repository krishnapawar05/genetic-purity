/**
 * Client-side script for Plant Purity Testing Interface.
 * Manages Drag & Drop, File Upload Validation, REST API communications,
 * and rendering prediction visualization results with Chart.js.
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

    // Supported extensions and max size (16MB)
    const ALLOWED_EXTENSIONS = ['png', 'jpg', 'jpeg', 'bmp', 'webp'];
    const MAX_FILE_SIZE = 16 * 1024 * 1024; 

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

        // 2. Validate File Size
        if (file.size > MAX_FILE_SIZE) {
            showError("File size exceeds the 16MB limit.");
            clearFileState();
            return;
        }

        activeFile = file;
        
        // 3. Render client-side image preview
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

    // ==============================================================================
    // REST API - PIPELINE INFERENCE EXECUTION
    // ==============================================================================
    
    analyzeBtn.addEventListener('click', () => {
        if (!activeFile) return;

        // Set Loading State
        analyzeBtn.disabled = true;
        btnText.textContent = "Analyzing Specimen...";
        btnSpinner.style.display = "block";
        hideError();
        hideResults();

        const formData = new FormData();
        formData.append("image", activeFile);

        fetch("/predict", {
            method: "POST",
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errData => {
                    throw new Error(errData.error || `Server responded with status ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                renderResults(data);
            } else {
                showError(data.error || "Inference pipeline failed.");
            }
        })
        .catch(err => {
            console.error(err);
            showError(`Error: ${err.message || "An unexpected error occurred during prediction."}`);
        })
        .finally(() => {
            // Reset Loading State
            analyzeBtn.disabled = false;
            btnText.textContent = "Analyze Plant Specimen";
            btnSpinner.style.display = "none";
        });
    });

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
});
