/**
 * Job Progress Handling
 * 
 * Handles job status display, progress updates, and phase visualization
 * Used by both processor.html and job_detail.html
 */

class JobProgress {
    /**
     * Initialize a new JobProgress tracker
     * @param {Object} options Configuration options
     * @param {string} options.jobId The ID of the job to track
     * @param {string} options.jobStatusUrl The URL to fetch job status from
     * @param {number} options.pollInterval How often to poll for status (in ms)
     * @param {string} options.containerSelector The selector for the container element
     * @param {string} options.progressBarSelector The selector for the progress bar element
     * @param {string} options.statusSelector The selector for the status element
     * @param {string} options.detailsSelector The selector for the details element
     * @param {Function} options.onUpdate Callback when job status is updated
     * @param {Function} options.onComplete Callback when job is complete
     * @param {Function} options.onError Callback when an error occurs
     */
    constructor(options) {
        console.log('[JobProgress] Initializing with options:', options);
        
        // Set default options
        this.options = Object.assign({
            pollInterval: 3000,
            containerSelector: '#job-progress-container',
            progressBarSelector: '#job-progress-bar',
            statusSelector: '#job-status',
            detailsSelector: '#job-details',
            onUpdate: null,
            onComplete: null,
            onError: null,
            debug: true
        }, options);

        // Validate required options
        if (!this.options.jobId) {
            this.log('ERROR', 'No jobId provided');
            throw new Error('JobProgress requires a jobId');
        }

        if (!this.options.jobStatusUrl) {
            this.log('ERROR', 'No jobStatusUrl provided');
            throw new Error('JobProgress requires a jobStatusUrl');
        }

        // Initialize state
        this.jobId = this.options.jobId;
        this.timer = null;
        this.pollCount = 0;
        this.lastStatus = null;
        this.lastUpdated = null;
        this.elements = {};
        this.isActive = false;
        this.initialized = false;
        
        // Find DOM elements
        this.findElements();
        
        this.log('INFO', `JobProgress initialized for job ${this.jobId}`);
        this.initialized = true;
    }

    /**
     * Log a message to the console if debugging is enabled
     * @param {string} level - Log level (INFO, WARN, ERROR, DEBUG)
     * @param {string} message - The message to log
     * @param {Object} data - Optional data to include in the log
     */
    log(level, message, data = null) {
        if (!this.options.debug) return;
        
        const timestamp = new Date().toISOString();
        const prefix = `[JobProgress ${this.jobId}] [${level}] [${timestamp}]`;
        
        switch(level) {
            case 'ERROR':
                console.error(prefix, message, data || '');
                break;
            case 'WARN':
                console.warn(prefix, message, data || '');
                break;
            case 'DEBUG':
                console.debug(prefix, message, data || '');
                break;
            case 'INFO':
            default:
                console.log(prefix, message, data || '');
        }
    }
    
    /**
     * Find and store references to DOM elements
     */
    findElements() {
        try {
            this.log('DEBUG', 'Finding DOM elements with selectors', {
                container: this.options.containerSelector,
                progressBar: this.options.progressBarSelector,
                status: this.options.statusSelector,
                details: this.options.detailsSelector
            });
            
            // Find container
            this.elements.container = document.querySelector(this.options.containerSelector);
            if (!this.elements.container) {
                this.log('WARN', `Container element not found: ${this.options.containerSelector}`);
            } else {
                this.log('DEBUG', 'Found container element', this.elements.container);
            }
            
            // Find progress bar
            this.elements.progressBar = document.querySelector(this.options.progressBarSelector);
            if (!this.elements.progressBar) {
                this.log('WARN', `Progress bar element not found: ${this.options.progressBarSelector}`);
            } else {
                this.log('DEBUG', 'Found progress bar element', this.elements.progressBar);
            }
            
            // Find status element
            this.elements.status = document.querySelector(this.options.statusSelector);
            if (!this.elements.status) {
                this.log('WARN', `Status element not found: ${this.options.statusSelector}`);
            } else {
                this.log('DEBUG', 'Found status element', this.elements.status);
            }
            
            // Find details element
            this.elements.details = document.querySelector(this.options.detailsSelector);
            if (!this.elements.details) {
                this.log('WARN', `Details element not found: ${this.options.detailsSelector}`);
            } else {
                this.log('DEBUG', 'Found details element', this.elements.details);
            }

            // Find phase elements if they exist
            this.elements.phases = {
                container: document.querySelector('#job-phases'),
                initializing: document.querySelector('#phase-initializing'),
                preparing: document.querySelector('#phase-preparing'),
                extracting: document.querySelector('#phase-extracting'),
                processing: document.querySelector('#phase-processing'),
                sending: document.querySelector('#phase-sending'),
                completed: document.querySelector('#phase-completed')
            };
            
            if (this.elements.phases.container) {
                this.log('DEBUG', 'Found phases container', this.elements.phases);
            }
        } catch (error) {
            this.log('ERROR', 'Error finding DOM elements', error);
        }
    }

    /**
     * Start polling for job status
     */
    startTracking() {
        if (this.isActive) {
            this.log('WARN', 'Tracking already active, ignoring startTracking call');
            return;
        }
        
        this.log('INFO', 'Starting job status tracking');
        this.isActive = true;
        this.pollStatus(); // Immediate first poll
        
        // Set up interval for subsequent polls
        this.timer = setInterval(() => {
            this.pollStatus();
        }, this.options.pollInterval);
        
        this.log('DEBUG', `Polling interval set to ${this.options.pollInterval}ms`);
    }

    /**
     * Stop polling for job status
     */
    stopTracking() {
        if (!this.isActive) {
            this.log('DEBUG', 'Tracking not active, ignoring stopTracking call');
            return;
        }
        
        this.log('INFO', 'Stopping job status tracking');
        
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        
        this.isActive = false;
    }

    /**
     * Poll the server for job status
     */
    pollStatus() {
        const startTime = performance.now();
        this.pollCount++;
        
        // Add cache-busting parameter
        const cacheBuster = `_=${Date.now()}`;
        const url = this.options.jobStatusUrl + 
            (this.options.jobStatusUrl.includes('?') ? '&' : '?') + 
            `job_id=${this.jobId}&${cacheBuster}`;
        
        this.log('DEBUG', `Polling status (count: ${this.pollCount})`, { url });
        
        fetch(url)
            .then(response => {
                const responseTime = performance.now() - startTime;
                this.log('DEBUG', `Received response in ${responseTime.toFixed(2)}ms, status: ${response.status}`);
                
                if (!response.ok) {
                    throw new Error(`Server responded with status ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const processTime = performance.now() - startTime;
                this.log('INFO', `Received job data in ${processTime.toFixed(2)}ms`, data);
                
                if (data.error) {
                    throw new Error(data.error);
                }
                
                // Update UI with job data
                this.updateDisplay(data);
                
                // Calculate time since last update from server
                let serverTimeSinceUpdate = null;
                if (data.last_updated && this.lastUpdated !== data.last_updated) {
                    const lastUpdatedDate = new Date(data.last_updated);
                    const now = new Date();
                    serverTimeSinceUpdate = Math.floor((now - lastUpdatedDate) / 1000);
                    this.log('DEBUG', `Server time since update: ${serverTimeSinceUpdate}s`);
                }
                
                // Check if status changed
                if (this.lastStatus !== data.status) {
                    this.log('INFO', `Job status changed: ${this.lastStatus || 'none'} → ${data.status}`);
                    this.lastStatus = data.status;
                }
                
                // Store last updated time
                this.lastUpdated = data.last_updated;
                
                // Trigger onUpdate callback if defined
                if (typeof this.options.onUpdate === 'function') {
                    try {
                        this.options.onUpdate(data);
                    } catch (err) {
                        this.log('ERROR', 'Error in onUpdate callback', err);
                    }
                }
                
                // Check if job is complete
                if (['completed', 'error', 'failed', 'cancelled'].includes(data.status)) {
                    this.log('INFO', `Job is in terminal state: ${data.status}, stopping tracking`);
                    this.stopTracking();
                    
                    // Trigger onComplete callback if defined
                    if (typeof this.options.onComplete === 'function') {
                        try {
                            this.options.onComplete(data);
                        } catch (err) {
                            this.log('ERROR', 'Error in onComplete callback', err);
                        }
                    }
                }
            })
            .catch(error => {
                const errorTime = performance.now() - startTime;
                this.log('ERROR', `Error polling job status (${errorTime.toFixed(2)}ms)`, error);
                
                // Update UI to show error
                if (this.elements.status) {
                    this.elements.status.textContent = `Error checking status: ${error.message}`;
                }
                
                // If consecutive errors exceed threshold, stop tracking
                if (this.pollCount > 10) {
                    this.log('WARN', 'Multiple consecutive errors, stopping tracking');
                    this.stopTracking();
                }
                
                // Trigger onError callback if defined
                if (typeof this.options.onError === 'function') {
                    try {
                        this.options.onError(error);
                    } catch (err) {
                        this.log('ERROR', 'Error in onError callback', err);
                    }
                }
            });
    }

    /**
     * Update the UI with job data
     * @param {Object} data The job data from the server
     */
    updateDisplay(data) {
        try {
            this.log('DEBUG', 'Updating display with job data');
            
            // Update progress bar if it exists
            if (this.elements.progressBar) {
                const percent = data.progress_percent || 0;
                this.elements.progressBar.style.width = `${percent}%`;
                this.elements.progressBar.setAttribute('aria-valuenow', percent);
                
                // Add appropriate classes based on status
                this.elements.progressBar.classList.remove('bg-success', 'bg-danger', 'bg-warning');
                
                if (data.status === 'completed') {
                    this.elements.progressBar.classList.add('bg-success');
                } else if (data.status === 'error' || data.status === 'failed') {
                    this.elements.progressBar.classList.add('bg-danger');
                } else if (data.status === 'cancelled') {
                    this.elements.progressBar.classList.add('bg-warning');
                }
                
                this.log('DEBUG', `Updated progress bar to ${percent}%`);
            }
            
            // Update status if it exists
            if (this.elements.status) {
                // Format status for display
                let statusText;
                if (data.status === 'in_progress' || data.status === 'processing') {
                    statusText = `Processing (${data.processed_count} of ${data.total_count} documents)`;
                } else if (data.status === 'completed') {
                    statusText = `Completed (${data.total_count} documents, ${data.total_case_count} cases)`;
                } else if (data.status === 'error' || data.status === 'failed') {
                    statusText = `Failed: ${data.error || 'Unknown error'}`;
                } else if (data.status === 'cancelled') {
                    statusText = 'Cancelled';
                } else {
                    statusText = data.status.charAt(0).toUpperCase() + data.status.slice(1);
                }
                
                this.elements.status.textContent = statusText;
                this.log('DEBUG', `Updated status text to "${statusText}"`);
            }
            
            // Update details if it exists
            if (this.elements.details) {
                let detailsText = '';
                
                if (data.processing_details) {
                    detailsText = data.processing_details;
                } else if (data.status === 'completed') {
                    detailsText = `Processed ${data.total_count} documents, found ${data.total_case_count} cases.`;
                    
                    // Add completed time if available
                    if (data.completed_at) {
                        const completedDate = new Date(data.completed_at);
                        detailsText += ` Completed at ${completedDate.toLocaleString()}.`;
                    }
                } else if (data.status === 'pending') {
                    detailsText = 'Job is queued and waiting to start.';
                }
                
                this.elements.details.textContent = detailsText;
                this.log('DEBUG', `Updated details text to "${detailsText}"`);
            }
            
            // Update phase visualization if it exists
            if (this.elements.phases.container && data.current_phase) {
                this.updatePhaseDisplay(data.current_phase);
            }
            
        } catch (error) {
            this.log('ERROR', 'Error updating display', error);
        }
    }

    /**
     * Update the phase visualization
     * @param {string} phase The current processing phase
     */
    updatePhaseDisplay(phase) {
        try {
            this.log('DEBUG', `Updating phase display to "${phase}"`);
            
            // Map of phases to their order
            const phaseOrder = {
                'initializing': 0,
                'preparing': 1,
                'extracting': 2,
                'processing': 3, 
                'sending': 4,
                'completed': 5
            };
            
            const currentPhaseOrder = phaseOrder[phase] || 0;
            
            // Update each phase element
            Object.entries(this.elements.phases).forEach(([phaseName, element]) => {
                if (phaseName === 'container' || !element) return;
                
                // Remove all state classes
                element.classList.remove('phase-active', 'phase-complete', 'phase-pending');
                
                // Get the order of this phase
                const thisPhaseOrder = phaseOrder[phaseName] || 0;
                
                // Set appropriate class based on progress
                if (phaseName === phase) {
                    element.classList.add('phase-active');
                } else if (thisPhaseOrder < currentPhaseOrder) {
                    element.classList.add('phase-complete');
                } else {
                    element.classList.add('phase-pending');
                }
            });
            
            this.log('DEBUG', 'Phase display updated');
        } catch (error) {
            this.log('ERROR', 'Error updating phase display', error);
        }
    }
}

// Make available globally
window.JobProgress = JobProgress; 