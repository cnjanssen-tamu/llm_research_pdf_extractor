/**
 * PDF Processor - Real-time Status Updater
 * 
 * This script handles fetching and displaying real-time status updates
 * for PDF processing jobs, showing the current document and case being processed.
 */

class StatusUpdater {
    constructor(options = {}) {
        console.log('StatusUpdater: Initializing with options', options);
        
        this.options = Object.assign({
            pollInterval: 2000,
            statusEndpoint: '/check-job-status/',
            maxRetries: 5
        }, options);
        
        this.pollTimer = null;
        this.currentJobId = null;
        this.retryCount = 0;
        this.lastStatus = null;
        
        // Processing phases order for visualizing progress
        this.phases = [
            'initializing',
            'preparing',
            'sending',
            'extracting',
            'processing',
            'completed'
        ];
        
        // DOM elements
        this.elements = {
            statusBadge: document.getElementById('processing-status-badge'),
            progressBar: document.querySelector('.progress-bar'),
            processedCount: document.getElementById('processed-count'),
            totalCount: document.getElementById('total-count'),
            caseCount: document.getElementById('case-count'),
            caseCounter: document.getElementById('case-counter'),
            processingDetails: document.getElementById('processing-details'),
            truncationAlert: document.getElementById('truncation-alert'),
            processingError: document.getElementById('processing-error'),
            formProcessingIndicator: document.getElementById('form-processing-indicator'),
            stepIndicators: document.querySelectorAll('.step-indicator')
        };
        
        // Debug DOM element existence
        console.log('StatusUpdater: DOM elements found:', {
            statusBadge: !!this.elements.statusBadge,
            progressBar: !!this.elements.progressBar,
            processedCount: !!this.elements.processedCount,
            totalCount: !!this.elements.totalCount,
            caseCount: !!this.elements.caseCount,
            caseCounter: !!this.elements.caseCounter,
            processingDetails: !!this.elements.processingDetails,
            truncationAlert: !!this.elements.truncationAlert,
            processingError: !!this.elements.processingError,
            formProcessingIndicator: !!this.elements.formProcessingIndicator,
            stepIndicators: this.elements.stepIndicators?.length || 0
        });
    }
    
    /**
     * Start polling for job status updates
     * @param {string} jobId - The ID of the job to poll for
     */
    startPolling(jobId) {
        if (!jobId) {
            console.error('Cannot start polling without a job ID');
            return;
        }
        
        // Clear any existing timer
        this.stopPolling();
        
        // Set current job ID
        this.currentJobId = jobId;
        this.retryCount = 0;
        
        // Initialize/reset progress elements if function exists
        if (typeof window.initializeProgressDisplay === 'function') {
            window.initializeProgressDisplay();
        }
        
        // Display the results section
        const resultsSection = document.getElementById('results-section');
        if (resultsSection) {
            resultsSection.style.display = 'block';
            resultsSection.classList.add('visible');
        }
        
        // Use initial status to show something right away
        const initialStatus = {
            status: 'initializing',
            progress_percent: 0,
            processed_count: 0,
            total_count: 0,
            processing_details: 'Initializing job...',
        };
        
        this.updateStatus(initialStatus);
        
        // Start polling
        this.pollStatus();
        
        console.log(`Started polling for job ${jobId} status every ${this.options.pollInterval}ms`);
    }
    
    /**
     * Stop polling for status updates
     */
    stopPolling() {
        console.log('StatusUpdater: Stopping polling');
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
    }
    
    /**
     * Fetch the current job status
     */
    pollStatus() {
        if (!this.currentJobId) return;
        
        // Create URL with job ID
        const url = `${this.options.statusEndpoint}?job_id=${this.currentJobId}`;
        
        // Fetch status
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Reset retry count on success
                this.retryCount = 0;
                
                // Process the data
                this.updateStatus(data);
                
                // Check if we need to continue polling
                if (this.shouldContinuePolling(data)) {
                    this.schedulePoll();
                } else {
                    console.log('Stopping polling - job completed or failed');
                }
            })
            .catch(error => {
                console.error('Error fetching job status:', error);
                
                // Increment retry count
                this.retryCount++;
                
                // Stop polling if max retries exceeded
                if (this.retryCount >= this.options.maxRetries) {
                    console.error(`Max retries (${this.options.maxRetries}) exceeded, stopping polling`);
                    this.displayError('Failed to connect to server. Please refresh the page to try again.');
                } else {
                    // Try again with exponential backoff
                    const backoffTime = Math.min(30000, this.options.pollInterval * Math.pow(2, this.retryCount));
                    console.log(`Retry ${this.retryCount} in ${backoffTime}ms`);
                    this.pollTimer = setTimeout(() => this.pollStatus(), backoffTime);
                }
            });
    }
    
    schedulePoll() {
        this.pollTimer = setTimeout(() => this.pollStatus(), this.options.pollInterval);
    }
    
    shouldContinuePolling(data) {
        // Check if the job is still in progress
        if (data.status) {
            const status = data.status.toLowerCase();
            return status !== 'completed' && status !== 'failed' && status !== 'error';
        }
        
        // If job data is nested in response
        if (data.job && data.job.status) {
            const status = data.job.status.toLowerCase();
            return status !== 'completed' && status !== 'failed' && status !== 'error';
        }
        
        // Default to true if we can't determine
        return true;
    }
    
    /**
     * Update the status display with the latest data
     * @param {Object} data - The status data from the API
     */
    updateStatus(data) {
        // Store a reference to the data for debugging
        this.lastStatus = data;
        
        // Log the data we received
        console.log('Status update:', data);
        
        // Extract data, handling both the original format and the new format
        const statusData = data.job || data;
        
        // Update the UI with the status information
        this.updateProgressBar(statusData);
        this.updateStatusBadge(statusData);
        this.updateProcessingDetails(statusData);
        this.updateCaseCount(statusData);
        this.updateProcessingPhase(statusData);
        
        // Check for errors or truncation
        this.checkForErrors(statusData);
        this.checkForTruncation(statusData);
        
        // Run any custom handlers
        this.runCustomHandlers(statusData);
        
        // Show the download buttons when the job is done
        if (statusData.status === 'completed') {
            this.showDownloadButtons();
        }
    }
    
    updateProgressBar(data) {
        // Update progress bar
        if (this.elements.progressBar) {
            const progressPercent = data.progress_percent || 0;
            console.log(`StatusUpdater: Setting progress bar to ${progressPercent}%`);
            this.elements.progressBar.style.width = `${progressPercent}%`;
            this.elements.progressBar.setAttribute('aria-valuenow', progressPercent);
        } else {
            console.error('StatusUpdater: Progress bar element not found');
        }
        
        // Update processed count
        if (this.elements.processedCount && this.elements.totalCount) {
            console.log(`StatusUpdater: Updating count to ${data.processed_count || 0}/${data.total_count || 0}`);
            this.elements.processedCount.textContent = data.processed_count || 0;
            this.elements.totalCount.textContent = data.total_count || 0;
        } else {
            console.error('StatusUpdater: Count elements not found');
        }
    }
    
    updateStatusBadge(data) {
        // Update status badge
        if (this.elements.statusBadge) {
            let statusText = 'Unknown';
            let badgeClass = 'bg-secondary';
            
            switch (data.status) {
                case 'pending':
                    statusText = 'Pending';
                    badgeClass = 'bg-warning';
                    break;
                case 'in_progress':
                case 'processing':
                    statusText = 'Processing';
                    badgeClass = 'bg-primary';
                    break;
                case 'waiting':
                    statusText = 'Waiting';
                    badgeClass = 'bg-info';
                    break;
                case 'extracting':
                    statusText = 'Extracting';
                    badgeClass = 'bg-info';
                    break;
                case 'completed':
                    statusText = 'Completed';
                    badgeClass = 'bg-success';
                    break;
                case 'error':
                case 'failed':
                    statusText = 'Error';
                    badgeClass = 'bg-danger';
                    break;
            }
            
            // Update badge text and class
            this.elements.statusBadge.textContent = statusText;
            this.elements.statusBadge.className = badgeClass + ' badge';
        } else {
            console.error('StatusUpdater: Status badge element not found');
        }
    }
    
    updateProcessingDetails(data) {
        // Update processing details
        if (this.elements.processingDetails) {
            let details = '';
            
            if (data.current_document) {
                details += `Currently processing: ${data.current_document}`;
                
                if (data.current_case) {
                    details += ` (Case: ${data.current_case})`;
                }
                
                if (data.last_updated) {
                    const lastUpdate = new Date(data.last_updated);
                    const now = new Date();
                    const diffSeconds = Math.round((now - lastUpdate) / 1000);
                    
                    if (diffSeconds < 60) {
                        details += ` - Updated ${diffSeconds} seconds ago`;
                    } else {
                        const diffMinutes = Math.floor(diffSeconds / 60);
                        details += ` - Updated ${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
                    }
                }
                
                console.log(`StatusUpdater: Setting processing details: ${details}`);
                this.elements.processingDetails.innerHTML = `<p>${details}</p>`;
                this.elements.processingDetails.style.display = 'block';
            } else if (data.processing_details) {
                console.log(`StatusUpdater: Setting raw processing details: ${data.processing_details}`);
                this.elements.processingDetails.textContent = data.processing_details;
                this.elements.processingDetails.style.display = 'block';
            } else {
                console.log('StatusUpdater: No processing details to display');
                this.elements.processingDetails.style.display = 'none';
            }
        } else {
            console.error('StatusUpdater: Processing details element not found');
        }
    }
    
    updateCaseCount(data) {
        // Update case count if available
        if (this.elements.caseCount && this.elements.caseCounter && data.total_case_count) {
            console.log(`StatusUpdater: Updating case count to ${data.total_case_count}`);
            this.elements.caseCount.textContent = data.total_case_count;
            this.elements.caseCounter.style.display = 'block';
        }
    }
    
    updateProcessingPhase(data) {
        // Update the processing phase visualization
        const processingDetails = data.processing_details || '';
        let currentPhase = 'initializing';
        
        // Determine current phase based on status and processing details
        if (data.status === 'completed') {
            currentPhase = 'completed';
        } else if (processingDetails.includes('extracting') || processingDetails.includes('extraction')) {
            currentPhase = 'extracting';
        } else if (processingDetails.includes('processing')) {
            currentPhase = 'processing';
        } else if (processingDetails.includes('sending')) {
            currentPhase = 'sending';
        } else if (processingDetails.includes('preparing')) {
            currentPhase = 'preparing';
        }
        
        // Update phase indicators
        if (this.elements.stepIndicators && this.elements.stepIndicators.length > 0) {
            // Remove active class from all indicators
            this.elements.stepIndicators.forEach(indicator => {
                indicator.classList.remove('active');
            });
            
            // Add active class to current phase and all previous phases
            let activateRest = false;
            this.elements.stepIndicators.forEach(indicator => {
                const phase = indicator.getAttribute('data-phase');
                
                if (phase === currentPhase) {
                    indicator.classList.add('active');
                    activateRest = true;
                } else if (activateRest) {
                    // Don't activate phases after the current one
                } else {
                    // Activate phases before the current one
                    indicator.classList.add('active');
                }
            });
        } else {
            console.error('StatusUpdater: Step indicators not found');
        }
    }
    
    checkForErrors(data) {
        // Check for errors
        if (this.elements.processingError) {
            if (data.error || (data.status === 'error') || (data.status === 'failed')) {
                const errorMessage = data.error || 'An error occurred during processing';
                this.elements.processingError.textContent = errorMessage;
                this.elements.processingError.style.display = 'block';
            } else {
                this.elements.processingError.style.display = 'none';
            }
        }
    }
    
    checkForTruncation(data) {
        // Check for truncation
        if (this.elements.truncationAlert && data.is_truncated) {
            console.log('StatusUpdater: Showing truncation alert');
            this.elements.truncationAlert.style.display = 'block';
        }
    }
    
    handleContinueProcessing() {
        if (!this.currentJobId) return;
        
        // Send request to continue processing
        fetch(`/continue-processing/${this.currentJobId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Continuation request successful');
                
                // Hide truncation alert
                if (this.elements.truncationAlert) {
                    this.elements.truncationAlert.style.display = 'none';
                }
                
                // Update processing details
                if (this.elements.processingDetails) {
                    this.elements.processingDetails.innerHTML = '<p>Continuing processing...</p>';
                    this.elements.processingDetails.style.display = 'block';
                }
            } else {
                console.error('Continuation request failed:', data.error);
                this.displayError(data.error || 'Failed to continue processing.');
            }
        })
        .catch(error => {
            console.error('Error requesting continuation:', error);
            this.displayError('Failed to continue processing. Please try again.');
        });
    }
    
    displayError(message) {
        if (this.elements.processingError) {
            this.elements.processingError.textContent = message;
            this.elements.processingError.style.display = 'block';
        } else {
            console.error('Error:', message);
        }
    }
    
    showDownloadButtons() {
        const downloadButtons = document.getElementById('download-buttons');
        
        if (downloadButtons) {
            downloadButtons.style.display = 'block';
        }
    }
    
    getCsrfToken() {
        // Get CSRF token from cookie or meta tag
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
            
        if (cookieValue) return cookieValue;
        
        // Try from meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        return metaTag ? metaTag.getAttribute('content') : '';
    }
    
    runCustomHandlers(data) {
        // Event for custom handlers
        const event = new CustomEvent('jobStatusUpdate', { detail: data });
        document.dispatchEvent(event);
    }
}

// Export for use in other scripts
window.StatusUpdater = StatusUpdater;

// Helper function to set up polling
function setupStatusCheckTimer() {
    const jobIdInput = document.getElementById('job-id');
    
    if (jobIdInput && jobIdInput.value) {
        const jobId = jobIdInput.value;
        
        if (window.statusUpdater) {
            window.statusUpdater.startPolling(jobId);
        } else if (typeof StatusUpdater !== 'undefined') {
            window.statusUpdater = new StatusUpdater();
            window.statusUpdater.startPolling(jobId);
        }
    }
}

// Make the helper function globally available
window.setupStatusCheckTimer = setupStatusCheckTimer; 