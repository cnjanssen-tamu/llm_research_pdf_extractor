/**
 * Safari-specific fixes for status display in PDF Processor
 * 
 * This script applies special fixes and handlers for Safari
 * to ensure the status section displays properly.
 */

(function() {
    // Function to run when DOM is loaded
    function initialize() {
        console.log('Safari status fix: Initializing');
        
        // Add handler for the extraction button
        setupExtractionButton();
        
        // Add handler for the form submission
        setupFormSubmission();
    }
    
    // Setup handler for extraction button
    function setupExtractionButton() {
        const extractionButton = document.getElementById('extraction-button');
        if (extractionButton) {
            console.log('Safari status fix: Found extraction button, adding click handler');
            
            // Add a direct click handler
            extractionButton.addEventListener('click', function(event) {
                console.log('Safari status fix: Extraction button clicked');
                forceShowStatusSection();
            });
        } else {
            console.log('Safari status fix: Extraction button not found');
            
            // Try to add the handler after a delay (button might be created later)
            setTimeout(function() {
                const laterButton = document.getElementById('extraction-button');
                if (laterButton) {
                    console.log('Safari status fix: Found extraction button on retry');
                    laterButton.addEventListener('click', function(event) {
                        console.log('Safari status fix: Extraction button clicked (retry)');
                        forceShowStatusSection();
                    });
                }
            }, 1000);
        }
    }
    
    // Setup handler for form submission
    function setupFormSubmission() {
        const uploadForm = document.getElementById('upload-form');
        if (uploadForm) {
            console.log('Safari status fix: Found upload form, adding submit handler');
            
            // Add a direct submit handler
            uploadForm.addEventListener('submit', function(event) {
                console.log('Safari status fix: Form submitted');
                forceShowStatusSection();
            });
        } else {
            console.log('Safari status fix: Upload form not found');
        }
    }
    
    // Force show the status section with multiple approaches
    function forceShowStatusSection() {
        console.log('Safari status fix: Forcing status section visibility');
        
        // Try multiple methods to show the results section
        const resultsSection = document.getElementById('results-section');
        
        if (resultsSection) {
            // Method 1: Direct style changes
            resultsSection.style.display = 'block';
            resultsSection.style.visibility = 'visible';
            resultsSection.style.opacity = '1';
            
            // Method 2: Add visible class
            resultsSection.classList.add('visible');
            
            // Method 3: Set !important styles
            resultsSection.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important;';
            
            // Method 4: setAttribute for style
            resultsSection.setAttribute('style', 'display: block !important; visibility: visible !important; opacity: 1 !important;');
            
            // Force browser reflow
            void resultsSection.offsetWidth;
            
            // Log result
            setTimeout(function() {
                const computedStyle = window.getComputedStyle(resultsSection);
                console.log('Safari status fix: Status section display after force:', computedStyle.display);
                console.log('Safari status fix: Status section visibility after force:', computedStyle.visibility);
                console.log('Safari status fix: Status section opacity after force:', computedStyle.opacity);
            }, 50);
            
            // Method 5: Create a visible clone if still not visible
            setTimeout(function() {
                const computedStyle = window.getComputedStyle(resultsSection);
                if (computedStyle.display === 'none') {
                    console.log('Safari status fix: Still not visible, creating clone');
                    
                    // Create a clone with forced visibility
                    const clone = resultsSection.cloneNode(true);
                    clone.id = 'results-section-clone';
                    clone.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important;';
                    
                    // Insert after the original
                    resultsSection.parentNode.insertBefore(clone, resultsSection.nextSibling);
                    
                    // Update badge and details in the clone
                    const badge = clone.querySelector('#processing-status-badge');
                    if (badge) {
                        badge.textContent = 'Starting';
                        badge.className = 'badge bg-info';
                    }
                    
                    const details = clone.querySelector('#processing-details');
                    if (details) {
                        details.textContent = 'Preparing to process documents...';
                        details.style.display = 'block';
                    }
                }
            }, 100);
        } else {
            console.log('Safari status fix: Results section not found, cannot force visibility');
            
            // Try to create it if not found
            if (typeof window.fixProcessingUI === 'function') {
                console.log('Safari status fix: Trying to create missing UI');
                window.fixProcessingUI();
                
                // Try again with the newly created element
                setTimeout(forceShowStatusSection, 100);
            }
        }
    }
    
    // Run the initialization when the DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
    
    // Make the force show function available globally
    window.safariForceShowStatusSection = forceShowStatusSection;
})(); 