/**
 * Job Status Banner
 * Provides a persistent status banner for active jobs
 */

class JobStatusBanner {
    constructor(options = {}) {
        this.options = Object.assign({
            pollInterval: 5000,
            checkEndpoint: '/check-job-status/',
            showCompletedDuration: 10000, // How long to show completed jobs
            persistInStorage: true,
            maxTrackedJobs: 5
        }, options);

        this.activeJobs = new Map(); // Track active jobs
        this.pollTimer = null;
        this.initialized = false;
        this.bannerElement = null;
        this.activeBanner = null;
        this.trackedJobs = [];
        
        // Load tracked jobs from storage if enabled
        if (this.options.persistInStorage) {
            this.loadFromStorage();
        }
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }
    
    init() {
        if (this.initialized) return;
        
        // Check if banner is disabled for this page
        if (window.disableJobStatusBanner === true) {
            console.log('Job Status Banner disabled for this page');
            return;
        }
        
        // Create the banner container if it doesn't exist
        this.createBannerElement();
        
        // Start polling for job statuses
        this.startPolling();
        
        // Set up event listeners for minimizing/closing
        this.setupEventListeners();
        
        this.initialized = true;
        console.log('Job Status Banner initialized');
        
        // Check for active jobs immediately
        this.checkActiveJobs();
    }
    
    createBannerElement() {
        // Check if banner already exists in DOM
        let existingBanner = document.querySelector('.job-status-banner');
        if (existingBanner) {
            this.bannerElement = existingBanner;
            return;
        }
        
        // Create the banner element
        const banner = document.createElement('div');
        banner.className = 'job-status-banner';
        banner.innerHTML = `
            <div class="banner-header">
                <h5 class="banner-title">
                    <span class="activity-indicator"></span>
                    <span class="banner-job-name">Job Status</span>
                </h5>
                <div class="banner-controls">
                    <button class="banner-minimize" aria-label="Minimize">
                        <i class="bi bi-dash"></i>
                    </button>
                    <button class="banner-close" aria-label="Close">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            </div>
            <div class="banner-body">
                <div class="d-flex align-items-center">
                    <span class="status-badge bg-info">Initializing</span>
                    <span class="job-time ms-auto"></span>
                </div>
                <div class="progress">
                    <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                </div>
                <div class="details">
                    <div class="details-item">
                        <span class="details-label">Current Document:</span>
                        <span class="details-value current-document">--</span>
                    </div>
                    <div class="details-item">
                        <span class="details-label">Current Case:</span>
                        <span class="details-value current-case">--</span>
                    </div>
                    <div class="details-item">
                        <span class="details-label">Progress:</span>
                        <span class="details-value progress-text">0%</span>
                    </div>
                </div>
            </div>
            <div class="banner-actions">
                <a href="#" class="view-details">View Details</a>
                <div>
                    <button class="btn btn-sm btn-secondary pause-job">Pause</button>
                    <button class="btn btn-sm btn-danger cancel-job">Cancel</button>
                </div>
            </div>
        `;
        
        // Add to the DOM
        document.body.appendChild(banner);
        this.bannerElement = banner;
    }
    
    setupEventListeners() {
        // Minimize banner
        const minimizeBtn = this.bannerElement.querySelector('.banner-minimize');
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', () => this.toggleMinimize());
        }
        
        // Close banner
        const closeBtn = this.bannerElement.querySelector('.banner-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideBanner());
        }
        
        // Cancel job
        const cancelBtn = this.bannerElement.querySelector('.cancel-job');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (this.activeBanner && this.activeBanner.jobId) {
                    this.cancelJob(this.activeBanner.jobId);
                }
            });
        }
        
        // View details
        const viewDetailsLink = this.bannerElement.querySelector('.view-details');
        if (viewDetailsLink) {
            viewDetailsLink.addEventListener('click', (e) => {
                e.preventDefault();
                if (this.activeBanner && this.activeBanner.jobId) {
                    window.location.href = `/jobs/${this.activeBanner.jobId}/`;
                }
            });
        }
    }
    
    startPolling() {
        // Clear any existing timer
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
        }
        
        // Set up polling interval
        this.pollTimer = setInterval(() => {
            this.checkActiveJobs();
        }, this.options.pollInterval);
        
        console.log(`Polling job status every ${this.options.pollInterval}ms`);
    }
    
    stopPolling() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }
    
    checkActiveJobs() {
        // First check tracked jobs
        if (this.trackedJobs.length > 0) {
            // Get the most recent job
            const mostRecentJob = this.trackedJobs[0];
            
            // If we don't have an active banner or it's a different job, update
            if (!this.activeBanner || this.activeBanner.jobId !== mostRecentJob.id) {
                this.fetchJobStatus(mostRecentJob.id);
            } else {
                // Otherwise just poll the current active job
                this.fetchJobStatus(this.activeBanner.jobId);
            }
        } else {
            // Check if there are any active jobs in the system
            this.fetchActiveJobs();
        }
    }
    
    fetchActiveJobs() {
        fetch(this.options.checkEndpoint)
            .then(response => {
                if (response.status === 302 || response.status === 401) {
                    // Authentication issue, but we'll handle it gracefully
                    console.log('Authentication required for job status, skipping checks');
                    return { active_jobs: [] }; // Return empty jobs array
                }
                
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Check for the active_jobs property
                if (data && data.active_jobs && Array.isArray(data.active_jobs) && data.active_jobs.length > 0) {
                    // Update tracked jobs
                    data.active_jobs.forEach(job => {
                        if (job && job.id) {
                            this.trackJob(job);
                        }
                    });
                    
                    // Display the most recent job
                    const mostRecentJob = data.active_jobs[0];
                    if (mostRecentJob && mostRecentJob.id) {
                        this.fetchJobStatus(mostRecentJob.id);
                    }
                } else {
                    console.log('No active jobs found');
                    // No active jobs, hide banner if showing
                    if (this.activeBanner) {
                        this.hideBanner();
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching active jobs:', error);
                // Handle case where the endpoint returns invalid JSON
                if (error instanceof SyntaxError) {
                    console.warn('Received invalid JSON response from active jobs endpoint');
                }
            });
    }
    
    fetchJobStatus(jobId) {
        if (!jobId) return;
        
        // Build URL properly: Make sure we don't have double slashes
        const baseUrl = this.options.checkEndpoint.endsWith('/') 
            ? this.options.checkEndpoint.slice(0, -1) 
            : this.options.checkEndpoint;
        const url = `${baseUrl}/?job_id=${jobId}`;
        
        fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // The check_job_status endpoint returns the job data directly, not wrapped in a job property
                if (data && data.status) {
                    this.updateBanner(data);
                } else {
                    console.error('No job data returned for ID:', jobId);
                }
            })
            .catch(error => {
                console.error('Error fetching job status:', error, 'for job ID:', jobId);
                if (error instanceof SyntaxError) {
                    console.warn('Received invalid JSON response from job status endpoint');
                }
            });
    }
    
    updateBanner(jobData) {
        if (!jobData || !jobData.id) return;
        
        // Create or update job in tracking
        this.trackJob(jobData);
        
        // Update banner status
        const status = jobData.status || 'unknown';
        const progress = jobData.progress_percent || 0;
        const jobName = jobData.name || `Job #${jobData.id}`;
        const currentDoc = jobData.current_document || '--';
        const currentCase = jobData.current_case || '--';
        const detailsUrl = jobData.details_url || `/jobs/${jobData.id}/`;
        
        // Get or create banner
        if (!this.activeBanner || this.activeBanner.jobId !== jobData.id) {
            this.activeBanner = {
                jobId: jobData.id,
                status: status,
                progress: progress,
                completedTime: null
            };
        } else {
            // Update existing banner data
            this.activeBanner.status = status;
            this.activeBanner.progress = progress;
        }
        
        // Track completion time for auto-hiding completed jobs
        if (status === 'completed' && !this.activeBanner.completedTime) {
            this.activeBanner.completedTime = new Date();
            
            // Schedule hiding
            setTimeout(() => {
                if (this.activeBanner && this.activeBanner.jobId === jobData.id) {
                    this.hideBanner();
                }
            }, this.options.showCompletedDuration);
        }
        
        // Update DOM elements
        const banner = this.bannerElement;
        
        // Update title
        banner.querySelector('.banner-job-name').textContent = jobName;
        
        // Update status badge
        const statusBadge = banner.querySelector('.status-badge');
        statusBadge.textContent = this.formatStatus(status);
        statusBadge.className = 'status-badge ' + this.getStatusClass(status);
        
        // Update banner status class
        banner.classList.remove('status-running', 'status-completed', 'status-error', 'status-warning');
        banner.classList.add(this.getStatusStateClass(status));
        
        // Update progress bar
        banner.querySelector('.progress-bar').style.width = `${progress}%`;
        banner.querySelector('.progress-text').textContent = `${progress}%`;
        
        // Update details
        banner.querySelector('.current-document').textContent = currentDoc;
        banner.querySelector('.current-case').textContent = currentCase;
        
        // Update view details link
        banner.querySelector('.view-details').href = detailsUrl;
        
        // Update job time (elapsed or completed time)
        const jobTimeElement = banner.querySelector('.job-time');
        if (jobTimeElement) {
            if (jobData.completed_at && status === 'completed') {
                jobTimeElement.textContent = `Completed: ${this.formatTime(jobData.completed_at)}`;
            } else if (jobData.started_at) {
                const elapsedTime = this.calculateElapsedTime(jobData.started_at);
                jobTimeElement.textContent = `Elapsed: ${elapsedTime}`;
            } else {
                jobTimeElement.textContent = '';
            }
        }
        
        // Show the banner
        this.showBanner();
        
        // Apply pulse animation for running jobs
        if (status === 'running' || status === 'waiting' || status === 'processing') {
            banner.classList.add('pulse');
        } else {
            banner.classList.remove('pulse');
        }
    }
    
    showBanner() {
        this.bannerElement.classList.add('active');
    }
    
    hideBanner() {
        this.bannerElement.classList.remove('active');
        this.activeBanner = null;
    }
    
    toggleMinimize() {
        this.bannerElement.classList.toggle('minimized');
        
        // Update minimize button icon
        const minimizeBtn = this.bannerElement.querySelector('.banner-minimize i');
        if (minimizeBtn) {
            if (this.bannerElement.classList.contains('minimized')) {
                minimizeBtn.className = 'bi bi-arrows-expand';
            } else {
                minimizeBtn.className = 'bi bi-dash';
            }
        }
    }
    
    trackJob(jobData) {
        if (!jobData || !jobData.id) return;
        
        // Check if job already tracked
        const existingIndex = this.trackedJobs.findIndex(job => job.id === jobData.id);
        
        if (existingIndex >= 0) {
            // Update existing job data
            this.trackedJobs[existingIndex] = { ...this.trackedJobs[existingIndex], ...jobData };
        } else {
            // Add new job to tracking
            this.trackedJobs.unshift(jobData); // Add to beginning (newest first)
            
            // Limit number of tracked jobs
            if (this.trackedJobs.length > this.options.maxTrackedJobs) {
                this.trackedJobs = this.trackedJobs.slice(0, this.options.maxTrackedJobs);
            }
        }
        
        // Save to storage if enabled
        if (this.options.persistInStorage) {
            this.saveToStorage();
        }
    }
    
    cancelJob(jobId) {
        if (!jobId) return;
        
        if (confirm('Are you sure you want to cancel this job?')) {
            fetch(`${this.options.checkEndpoint}${jobId}/cancel/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Job cancelled successfully');
                    // Update banner or hide
                    this.checkActiveJobs();
                } else {
                    console.error('Failed to cancel job:', data.error);
                }
            })
            .catch(error => {
                console.error('Error cancelling job:', error);
            });
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
    
    saveToStorage() {
        if (typeof localStorage !== 'undefined') {
            try {
                localStorage.setItem('jobStatusBanner', JSON.stringify({
                    trackedJobs: this.trackedJobs,
                    lastUpdated: new Date().toISOString()
                }));
            } catch (e) {
                console.error('Error saving to localStorage:', e);
            }
        }
    }
    
    loadFromStorage() {
        if (typeof localStorage !== 'undefined') {
            try {
                const stored = localStorage.getItem('jobStatusBanner');
                if (stored) {
                    const data = JSON.parse(stored);
                    if (data.trackedJobs && Array.isArray(data.trackedJobs)) {
                        this.trackedJobs = data.trackedJobs;
                        
                        // Filter out completed jobs older than 1 hour
                        const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
                        this.trackedJobs = this.trackedJobs.filter(job => {
                            // Keep if not completed or recently completed
                            if (job.status !== 'completed') return true;
                            if (!job.completed_at) return true;
                            
                            const completedAt = new Date(job.completed_at);
                            return completedAt > oneHourAgo;
                        });
                    }
                }
            } catch (e) {
                console.error('Error loading from localStorage:', e);
                this.trackedJobs = [];
            }
        }
    }
    
    formatStatus(status) {
        if (!status) return 'Unknown';
        
        // Format status for display
        switch (status.toLowerCase()) {
            case 'running':
                return 'Running';
            case 'waiting':
                return 'Waiting';
            case 'processing':
                return 'Processing';
            case 'completed':
                return 'Completed';
            case 'error':
            case 'failed':
                return 'Error';
            case 'cancelled':
                return 'Cancelled';
            default:
                return status.charAt(0).toUpperCase() + status.slice(1);
        }
    }
    
    getStatusClass(status) {
        if (!status) return 'bg-secondary';
        
        // Get Bootstrap class for status
        switch (status.toLowerCase()) {
            case 'running':
            case 'processing':
                return 'bg-primary';
            case 'waiting':
                return 'bg-info';
            case 'completed':
                return 'bg-success';
            case 'error':
            case 'failed':
                return 'bg-danger';
            case 'cancelled':
                return 'bg-secondary';
            case 'warning':
                return 'bg-warning';
            default:
                return 'bg-secondary';
        }
    }
    
    getStatusStateClass(status) {
        if (!status) return 'status-running';
        
        // Get state class for banner styling
        switch (status.toLowerCase()) {
            case 'running':
            case 'processing':
            case 'waiting':
                return 'status-running';
            case 'completed':
                return 'status-completed';
            case 'error':
            case 'failed':
                return 'status-error';
            case 'warning':
            case 'cancelled':
                return 'status-warning';
            default:
                return 'status-running';
        }
    }
    
    formatTime(timestamp) {
        if (!timestamp) return '';
        
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    calculateElapsedTime(startTime) {
        if (!startTime) return '';
        
        const start = new Date(startTime);
        const now = new Date();
        const elapsedMs = now - start;
        
        const seconds = Math.floor((elapsedMs / 1000) % 60);
        const minutes = Math.floor((elapsedMs / (1000 * 60)) % 60);
        const hours = Math.floor(elapsedMs / (1000 * 60 * 60));
        
        if (hours > 0) {
            return `${hours}h ${minutes}m ${seconds}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds}s`;
        } else {
            return `${seconds}s`;
        }
    }
}

// Just make the class available globally
window.JobStatusBanner = JobStatusBanner; 