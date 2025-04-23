/**
 * Safari-specific debugging tools for PDF Processor
 */

// Make sure all debug functions are directly accessible in the global scope
window.testStatusVisibility = function() {
    console.group('Safari Visibility Test');
    
    // Force display results section
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        console.log('Found results-section, forcing display: block');
        resultsSection.style.cssText = 'display: block !important';
        resultsSection.classList.add('visible');
        
        // Check computed style to verify it's actually displayed
        const computedStyle = window.getComputedStyle(resultsSection);
        console.log('Computed display value:', computedStyle.display);
    } else {
        console.error('Could not find results-section element');
        alert('Error: Results section not found.');
    }
    
    // Check all key elements
    const elements = {
        'processing-status-badge': document.getElementById('processing-status-badge'),
        'progress-bar': document.querySelector('.progress-bar'),
        'processing-details': document.getElementById('processing-details'),
        'case-counter': document.getElementById('case-counter')
    };
    
    // Log status and force display for each element
    Object.entries(elements).forEach(([name, element]) => {
        if (element) {
            console.log(`Found ${name}, current display:`, window.getComputedStyle(element).display);
            
            // Force display on processing details
            if (name === 'processing-details') {
                element.style.cssText = 'display: block !important';
                element.textContent = 'Safari test: Forcing visibility of processing details';
                element.style.backgroundColor = '#ffff99';
                element.style.color = '#000000';
                element.style.padding = '10px';
                element.style.margin = '10px 0';
                element.style.border = '2px solid #ff9900';
            }
            
            // Show case counter
            if (name === 'case-counter') {
                element.style.cssText = 'display: inline-block !important';
                const caseCount = document.getElementById('case-count');
                if (caseCount) {
                    caseCount.textContent = '42';
                }
            }
            
            // Update progress bar
            if (name === 'progress-bar') {
                element.style.width = '75%';
                element.style.backgroundColor = '#4CAF50';
            }
            
            // Update badge
            if (name === 'processing-status-badge') {
                element.textContent = 'SAFARI TEST';
                element.className = 'badge bg-warning';
            }
        } else {
            console.error(`Could not find ${name} element`);
        }
    });
    
    // Force update the processing steps visualization
    const stepIndicators = document.querySelectorAll('.step-indicator');
    if (stepIndicators.length > 0) {
        console.log(`Found ${stepIndicators.length} step indicators, highlighting current step`);
        
        // Reset all steps
        stepIndicators.forEach(indicator => {
            indicator.classList.remove('active', 'complete');
        });
        
        // Make first two complete and third active
        for (let i = 0; i < stepIndicators.length; i++) {
            if (i < 2) {
                stepIndicators[i].classList.add('complete');
            } else if (i === 2) {
                stepIndicators[i].classList.add('active');
            }
        }
    } else {
        console.error('Could not find step indicators');
    }
    
    console.log('Safari visibility test complete');
    console.groupEnd();
    
    // Return true to indicate test was run
    return 'Test complete - check the results on your page';
};

window.showStatusSection = function() {
    console.log('showStatusSection: Forcing status section visibility');
    
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        resultsSection.style.cssText = 'display: block !important';
        resultsSection.classList.add('visible');
        
        // Add inline styles with !important to override any CSS
        resultsSection.setAttribute('style', 'display: block !important; visibility: visible !important; opacity: 1 !important;');
        
        // Force redraw for Safari
        void resultsSection.offsetWidth;
        
        setTimeout(() => {
            const computedStyle = window.getComputedStyle(resultsSection);
            console.log('Status section display value after force:', computedStyle.display);
            alert('Status section should now be visible. If not visible, check console for details.');
        }, 100);
    } else {
        console.error('Results section not found');
        alert('Error: Results section not found. Try reloading the page.');
        
        // Try to create it
        if (typeof window.fixProcessingUI === 'function') {
            window.fixProcessingUI();
            
            // Try again
            const newResultsSection = document.getElementById('results-section');
            if (newResultsSection) {
                newResultsSection.style.cssText = 'display: block !important';
                newResultsSection.classList.add('visible');
                alert('Created new results section. It should now be visible.');
            }
        }
    }
};

window.testStatusUpdater = function() {
    console.log('testStatusUpdater: Testing status updater with mock data');
    
    // Ensure the status section exists and is visible
    if (!document.getElementById('results-section')) {
        if (typeof window.fixProcessingUI === 'function') {
            window.fixProcessingUI();
            alert('Created missing UI elements. Status section should now exist.');
        } else {
            alert('Error: fixProcessingUI function not available. Cannot create missing elements.');
            return;
        }
    }
    
    // Force show status section
    window.showStatusSection();
    
    // Create mock data
    const mockStatus = {
        status: 'processing',
        progress_percent: 65,
        processed_count: 3,
        total_count: 5,
        total_case_count: 24,
        current_document: 'example.pdf',
        current_case: '7',
        processing_details: 'Testing status updater in Safari',
        last_updated: new Date().toISOString()
    };
    
    // Find the status updater instance or create one
    let updater = window.statusUpdater;
    if (!updater) {
        try {
            console.log('Creating new StatusUpdater instance');
            updater = new window.StatusUpdater({
                statusEndpoint: '/check-job-status/',
                jobId: 'test-safari'
            });
            window.statusUpdater = updater;
        } catch (e) {
            console.error('Error creating StatusUpdater:', e);
            alert('Error: Could not create StatusUpdater. See console for details.');
            return;
        }
    }
    
    // Force update with mock data
    try {
        updater.updateStatus(mockStatus);
        console.log('Sent test update to status updater');
        
        // Update badge directly
        const badge = document.getElementById('processing-status-badge');
        if (badge) {
            badge.textContent = 'SAFARI TEST';
            badge.className = 'badge bg-info';
        }
        
        alert('Test status update sent. The UI should now show mock data.');
    } catch (e) {
        console.error('Error updating status:', e);
        alert('Error: Could not update status. See console for details.');
    }
};

// Make sure these are in the global scope for Safari
console.log('Safari debug functions loaded in global scope:', {
    testStatusVisibility: typeof window.testStatusVisibility === 'function',
    showStatusSection: typeof window.showStatusSection === 'function',
    testStatusUpdater: typeof window.testStatusUpdater === 'function'
});

// Run initial visibility check when loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Safari debug script loaded and DOM ready');
}); 