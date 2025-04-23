/**
 * Debug Status - Tool for troubleshooting the status updater
 */

function debugStatusUpdater() {
    console.group('Status Updater Debug');
    console.log('Debug session started at:', new Date().toISOString());
    
    // Check if jQuery is loaded
    console.log('jQuery loaded:', typeof $ !== 'undefined');
    
    // Check if StatusUpdater class exists
    console.log('StatusUpdater class exists:', typeof StatusUpdater !== 'undefined');
    
    // Check for required DOM elements
    const requiredElements = [
        '#processing-status-badge',
        '.progress-bar',
        '#processed-count',
        '#total-count',
        '#case-count',
        '#case-counter',
        '#processing-details',
        '#truncation-alert',
        '#processing-error',
        '#form-processing-indicator',
        '.step-indicator'
    ];
    
    const missingElements = [];
    
    requiredElements.forEach(selector => {
        const elements = document.querySelectorAll(selector);
        const status = elements.length > 0;
        console.log(`Found '${selector}':`, status, status ? `(${elements.length} elements)` : '');
        
        if (!status) {
            missingElements.push(selector);
        }
    });
    
    console.log('Missing elements:', missingElements.length > 0 ? missingElements : 'None');
    
    // Check stylesheet loading
    const styleLoaded = [...document.styleSheets].some(sheet => 
        sheet.href && sheet.href.includes('status-updater.css')
    );
    console.log('Status updater CSS loaded:', styleLoaded);
    
    // Check status URL
    let statusUrl = null;
    try {
        // Try to find the status URL in script tags
        const scripts = document.querySelectorAll('script');
        for (const script of scripts) {
            if (script.textContent.includes('check_job_status')) {
                const match = script.textContent.match(/statusEndpoint:\s*['"]([^'"]+)['"]/);
                if (match) {
                    statusUrl = match[1];
                    break;
                }
            }
        }
    } catch (e) {
        console.error('Error finding status URL:', e);
    }
    console.log('Status URL found:', statusUrl);
    
    // Try to manually test a status request
    if (statusUrl) {
        console.log('Testing status endpoint manually...');
        fetch(statusUrl + '?job_id=test')
            .then(response => {
                console.log('Status endpoint response status:', response.status);
                return response.text();
            })
            .then(text => {
                console.log('Status endpoint response received:', text.substring(0, 100) + '...');
            })
            .catch(error => {
                console.error('Error testing status endpoint:', error);
            });
    }
    
    // Create a mock status object and try to update the UI
    if (typeof StatusUpdater !== 'undefined') {
        try {
            console.log('Creating test status updater instance...');
            const testUpdater = new StatusUpdater({
                statusEndpoint: statusUrl || '/check-job-status/',
                jobId: 'test-job'
            });
            
            console.log('Creating mock status data...');
            const mockStatus = {
                status: 'processing',
                progress_percent: 45,
                processed_count: 2,
                total_count: 5,
                total_case_count: 12,
                current_document: 'test-document.pdf',
                current_case: '3',
                processing_details: 'Testing status updater',
                last_updated: new Date().toISOString()
            };
            
            console.log('Testing updateStatus method with mock data...');
            testUpdater.updateStatus(mockStatus);
        } catch (e) {
            console.error('Error creating test instance:', e);
        }
    }
    
    console.log('Debug session ended');
    console.groupEnd();
    
    return {
        missingElements,
        styleLoaded,
        jQueryLoaded: typeof $ !== 'undefined',
        statusUpdaterLoaded: typeof StatusUpdater !== 'undefined',
        statusUrl
    };
}

// Run debug function when this script loads
window.addEventListener('DOMContentLoaded', () => {
    console.log('DOM fully loaded, running debug...');
    debugStatusUpdater();
});

// Make debug function available globally
window.debugStatusUpdater = debugStatusUpdater; 