/**
 * Progress UI initialization
 * Handles resetting and initializing the job progress UI elements
 */

// Function to initialize/reset progress display
function initializeProgressDisplay() {
    // Reset progress bar
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', '0');
    }
    
    // Reset step indicators
    const stepIndicators = document.querySelectorAll('.step-indicator');
    stepIndicators.forEach(indicator => {
        indicator.classList.remove('active', 'complete');
        // Only initialize step is active by default
        if (indicator.getAttribute('data-phase') === 'initializing') {
            indicator.classList.add('active');
        }
    });
    
    // Reset counters
    const processedCount = document.getElementById('processed-count');
    const totalCount = document.getElementById('total-count');
    const caseCount = document.getElementById('case-count');
    const caseCounter = document.getElementById('case-counter');
    
    if (processedCount) processedCount.textContent = '0';
    if (totalCount) totalCount.textContent = '0';
    if (caseCount) caseCount.textContent = '0';
    if (caseCounter) caseCounter.style.display = 'none';
    
    // Reset status badge
    const statusBadge = document.getElementById('processing-status-badge');
    if (statusBadge) {
        statusBadge.textContent = 'Initializing';
        statusBadge.className = 'badge bg-info';
    }
    
    // Hide any alerts or messages
    const truncationAlert = document.getElementById('truncation-alert');
    const processingDetails = document.getElementById('processing-details');
    const processingError = document.getElementById('processing-error');
    
    if (truncationAlert) truncationAlert.style.display = 'none';
    if (processingDetails) {
        processingDetails.innerHTML = '';
        processingDetails.style.display = 'none';
    }
    if (processingError) {
        processingError.textContent = '';
        processingError.style.display = 'none';
    }
    
    console.log('Progress display initialized/reset');
}

// Function to show the status section with proper initialization
function showStatusSection() {
    const resultsSection = document.getElementById('results-section');
    if (!resultsSection) return;
    
    // Reset the display first
    initializeProgressDisplay();
    
    // Show the section
    resultsSection.style.display = 'block';
    resultsSection.classList.add('visible');
    
    // Apply additional styles to ensure visibility
    resultsSection.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important;';
    
    console.log('Status section shown and initialized');
    
    // Force browser redraw
    void resultsSection.offsetWidth;
    
    // Log visibility status
    setTimeout(() => {
        const computedStyle = window.getComputedStyle(resultsSection);
        console.log('Status section display style:', computedStyle.display);
        console.log('Status section visibility:', computedStyle.visibility);
    }, 10);
}

// Show mock data for debugging/testing
function testStatusDisplay() {
    // First show the section
    showStatusSection();
    
    // Update with mock data
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.style.width = '35%';
        progressBar.setAttribute('aria-valuenow', '35');
    }
    
    const processedCount = document.getElementById('processed-count');
    const totalCount = document.getElementById('total-count');
    if (processedCount) processedCount.textContent = '2';
    if (totalCount) totalCount.textContent = '5';
    
    // Show case counter
    const caseCount = document.getElementById('case-count');
    const caseCounter = document.getElementById('case-counter');
    if (caseCount) caseCount.textContent = '8';
    if (caseCounter) caseCounter.style.display = 'block';
    
    // Show processing details
    const processingDetails = document.getElementById('processing-details');
    if (processingDetails) {
        processingDetails.innerHTML = '<p>Processing document: test-doc.pdf (Case: 3)</p>';
        processingDetails.style.display = 'block';
    }
    
    // Update phase indicators to show Extract as active
    const stepIndicators = document.querySelectorAll('.step-indicator');
    stepIndicators.forEach(indicator => {
        indicator.classList.remove('active', 'complete');
        const phase = indicator.getAttribute('data-phase');
        
        if (phase === 'extracting') {
            indicator.classList.add('active');
        } else if (['initializing', 'preparing', 'sending'].includes(phase)) {
            indicator.classList.add('complete');
        }
    });
    
    // Update status badge
    const statusBadge = document.getElementById('processing-status-badge');
    if (statusBadge) {
        statusBadge.textContent = 'Extracting';
        statusBadge.className = 'badge bg-primary';
    }
    
    console.log('Test status display updated with mock data');
}

// Make functions available globally
window.initializeProgressDisplay = initializeProgressDisplay;
window.showStatusSection = showStatusSection;
window.testStatusDisplay = testStatusDisplay;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('Progress initialization script loaded');
    
    // Initialize any buttons that might need to show the status section
    const debugButton = document.getElementById('btn-test-visibility');
    if (debugButton) {
        debugButton.addEventListener('click', testStatusDisplay);
    }
    
    const showButton = document.getElementById('btn-show-status');
    if (showButton) {
        showButton.addEventListener('click', showStatusSection);
    }
});

// If document is already ready, run immediately
if (document.readyState !== 'loading') {
    console.log('Document already ready, initializing progress functions');
} 