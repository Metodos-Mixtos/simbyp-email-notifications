/**
 * Batch Import functionality for the admin dashboard.
 * Handles CSV file upload, validation, and results display.
 */

/**
 * Download the CSV template for batch import
 */
function downloadTemplate() {
    const templateButton = document.getElementById('downloadTemplateButton');
    const templateSpinner = document.getElementById('templateSpinner');
    
    // Show spinner
    templateSpinner.classList.add('show');
    templateButton.disabled = true;
    
    fetch('/api/batch-import-template')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.blob();
        })
        .then(blob => {
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `plantilla_correos_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            // Show success toast
            showToast('Template downloaded successfully', 'success');
        })
        .catch(error => {
            console.error('Error downloading template:', error);
            showToast(`Error downloading template: ${error.message}`, 'danger');
        })
        .finally(() => {
            // Hide spinner
            templateSpinner.classList.remove('show');
            templateButton.disabled = false;
        });
}

/**
 * Handle batch import form submission
 */
function handleBatchImport(event) {
    event.preventDefault();
    
    const csvFileInput = document.getElementById('csvFileInput');
    const batchImportButton = document.getElementById('batchImportButton');
    const importSpinner = document.getElementById('importSpinner');
    const resultsContainer = document.getElementById('importResultsContainer');
    
    if (!csvFileInput.files || csvFileInput.files.length === 0) {
        showToast('Please select a CSV file', 'warning');
        return;
    }
    
    const file = csvFileInput.files[0];
    
    // Validate file type
    if (!file.name.endsWith('.csv')) {
        showToast('File must be a CSV file', 'danger');
        return;
    }
    
    // Validate file size (max 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        showToast('File is too large (max 10MB)', 'danger');
        return;
    }
    
    // Show spinner and disable button
    importSpinner.classList.add('show');
    batchImportButton.disabled = true;
    
    // Create FormData
    const formData = new FormData();
    formData.append('file', file);
    
    // Upload file
    fetch('/api/batch-import', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            displayImportResults(data);
            
            // Show toast based on status
            if (data.status === 'success') {
                showToast('Batch import completed successfully!', 'success');
                // Clear file input
                csvFileInput.value = '';
                // Reload user list
                setTimeout(() => loadUsers(), 500);
            } else if (data.status === 'partial') {
                showToast(`Batch import completed with ${data.summary.errors} error(s). Check details below.`, 'warning');
                // Reload user list for successfully imported users
                setTimeout(() => loadUsers(), 500);
            } else {
                showToast(`Batch import failed: ${data.summary.errors} error(s)`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error during batch import:', error);
            showToast(`Error during batch import: ${error.message}`, 'danger');
        })
        .finally(() => {
            // Hide spinner and enable button
            importSpinner.classList.remove('show');
            batchImportButton.disabled = false;
        });
}

/**
 * Display import results on the page
 */
function displayImportResults(data) {
    const resultsContainer = document.getElementById('importResultsContainer');
    const resultsSummary = document.getElementById('importResultsSummary');
    const errorDetailsContainer = document.getElementById('errorDetailsContainer');
    const errorDetailsList = document.getElementById('errorDetailsList');
    
    // Build summary message
    const summary = data.summary;
    let summaryHtml = `
        <strong>Summary:</strong>
        <ul style="margin-bottom: 0;">
            <li>Total rows processed: ${summary.total}</li>
            <li><span class="text-success">Created:</span> ${summary.created}</li>
            <li><span class="text-info">Updated:</span> ${summary.updated}</li>
            <li><span class="text-warning">Skipped:</span> ${summary.skipped}</li>
            <li><span class="text-danger">Errors:</span> ${summary.errors}</li>
        </ul>
    `;
    
    // Set alert class based on status
    let alertClass = 'alert-info';
    if (data.status === 'success') {
        alertClass = 'alert-success';
    } else if (data.status === 'partial') {
        alertClass = 'alert-warning';
    } else {
        alertClass = 'alert-danger';
    }
    
    resultsSummary.className = `alert ${alertClass}`;
    resultsSummary.innerHTML = summaryHtml;
    
    // Display errors if any
    if (data.errors && data.errors.length > 0) {
        errorDetailsContainer.style.display = 'block';
        errorDetailsList.innerHTML = '';
        
        data.errors.forEach(error => {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-row';
            
            let errorHtml = `
                <strong>Row ${error.row}${error.email ? ` (${error.email})` : ''}:</strong>
                <ul style="margin-bottom: 0; margin-top: 5px;">
            `;
            
            error.errors.forEach(msg => {
                errorHtml += `<li>${escapeHtml(msg)}</li>`;
            });
            
            errorHtml += '</ul>';
            
            errorDiv.innerHTML = errorHtml;
            errorDetailsList.appendChild(errorDiv);
        });
    } else {
        errorDetailsContainer.style.display = 'none';
    }
    
    // Show results container
    resultsContainer.style.display = 'block';
}

/**
 * Escape HTML special characters to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
