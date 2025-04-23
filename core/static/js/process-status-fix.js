/**
 * Process Status Fix - Creates and repairs missing UI elements for job status display
 */

(function() {
    console.log('Process Status Fix: Script loaded');
    
    // Create missing elements based on the template structure
    function createProcessingUI() {
        console.log('Process Status Fix: Creating processing UI elements');
        
        const container = document.querySelector('.container');
        if (!container) {
            console.error('Process Status Fix: No container element found');
            return false;
        }
        
        // Check if results section already exists
        let resultsSection = document.getElementById('results-section');
        if (resultsSection) {
            console.log('Process Status Fix: Results section already exists');
        } else {
            console.log('Process Status Fix: Creating results section');
            resultsSection = document.createElement('div');
            resultsSection.id = 'results-section';
            resultsSection.className = 'mt-4';
            resultsSection.style.display = 'none';
            
            // Create card
            const card = document.createElement('div');
            card.className = 'card';
            
            // Create card header
            const cardHeader = document.createElement('div');
            cardHeader.className = 'card-header d-flex justify-content-between align-items-center';
            
            const cardTitle = document.createElement('h3');
            cardTitle.className = 'card-title mb-0';
            cardTitle.textContent = 'Processing Progress';
            
            const statusBadge = document.createElement('span');
            statusBadge.id = 'processing-status-badge';
            statusBadge.className = 'badge bg-info';
            statusBadge.textContent = 'Initializing';
            
            cardHeader.appendChild(cardTitle);
            cardHeader.appendChild(statusBadge);
            
            // Create card body
            const cardBody = document.createElement('div');
            cardBody.className = 'card-body';
            
            // Create processing status
            const processingStatus = document.createElement('div');
            processingStatus.id = 'processing-status';
            
            // Create progress bar
            const progressContainer = document.createElement('div');
            progressContainer.className = 'progress mb-3';
            
            const progressBar = document.createElement('div');
            progressBar.className = 'progress-bar';
            progressBar.role = 'progressbar';
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', '0');
            progressBar.setAttribute('aria-valuemin', '0');
            progressBar.setAttribute('aria-valuemax', '100');
            
            progressContainer.appendChild(progressBar);
            
            // Create processing steps visualization
            const stepsContainer = document.createElement('div');
            stepsContainer.className = 'processing-steps mb-3';
            
            const stepsFlexContainer = document.createElement('div');
            stepsFlexContainer.className = 'd-flex justify-content-between position-relative';
            
            // Create steps for each phase
            const phases = ['initializing', 'preparing', 'sending', 'extracting', 'processing', 'completed'];
            const phaseLabels = ['Initialize', 'Prepare', 'Send', 'Extract', 'Process', 'Complete'];
            
            phases.forEach((phase, index) => {
                const step = document.createElement('div');
                step.className = 'processing-step';
                
                const indicator = document.createElement('div');
                indicator.className = phase === 'initializing' ? 'step-indicator active' : 'step-indicator';
                indicator.setAttribute('data-phase', phase);
                
                const number = document.createElement('span');
                number.className = 'step-number';
                number.textContent = (index + 1).toString();
                
                const label = document.createElement('div');
                label.className = 'step-label';
                label.textContent = phaseLabels[index];
                
                indicator.appendChild(number);
                step.appendChild(indicator);
                step.appendChild(label);
                
                stepsFlexContainer.appendChild(step);
            });
            
            // Add progress line connecting steps
            const progressLine = document.createElement('div');
            progressLine.className = 'progress-line';
            stepsFlexContainer.appendChild(progressLine);
            
            stepsContainer.appendChild(stepsFlexContainer);
            
            // Create info counters
            const countersContainer = document.createElement('div');
            countersContainer.className = 'd-flex justify-content-between mb-3';
            
            const processingInfo = document.createElement('div');
            processingInfo.id = 'processing-info';
            
            const processedCount = document.createElement('span');
            processedCount.id = 'processed-count';
            processedCount.textContent = '0';
            
            const totalCount = document.createElement('span');
            totalCount.id = 'total-count';
            totalCount.textContent = '0';
            
            processingInfo.appendChild(processedCount);
            processingInfo.appendChild(document.createTextNode(' of '));
            processingInfo.appendChild(totalCount);
            processingInfo.appendChild(document.createTextNode(' documents processed'));
            
            const caseCounter = document.createElement('div');
            caseCounter.id = 'case-counter';
            caseCounter.className = 'text-primary';
            caseCounter.style.display = 'none';
            
            const caseIcon = document.createElement('i');
            caseIcon.className = 'bi bi-file-earmark-text';
            
            const caseCount = document.createElement('span');
            caseCount.id = 'case-count';
            caseCount.textContent = '0';
            
            caseCounter.appendChild(caseIcon);
            caseCounter.appendChild(document.createTextNode(' '));
            caseCounter.appendChild(caseCount);
            caseCounter.appendChild(document.createTextNode(' cases extracted'));
            
            countersContainer.appendChild(processingInfo);
            countersContainer.appendChild(caseCounter);
            
            // Create truncation alert
            const truncationAlert = document.createElement('div');
            truncationAlert.id = 'truncation-alert';
            truncationAlert.className = 'alert alert-warning alert-dismissible fade show mb-3';
            truncationAlert.role = 'alert';
            truncationAlert.style.display = 'none';
            
            const truncationIcon = document.createElement('i');
            truncationIcon.className = 'bi bi-exclamation-triangle-fill me-1';
            
            const truncationMessage = document.createElement('span');
            truncationMessage.id = 'truncation-message';
            truncationMessage.textContent = 'Response was truncated due to token limits. Some cases may not have been extracted.';
            
            const truncationActions = document.createElement('div');
            truncationActions.className = 'mt-2';
            
            const continueBtn = document.createElement('button');
            continueBtn.id = 'continue-processing-btn';
            continueBtn.className = 'btn btn-sm btn-warning';
            continueBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Continue Processing';
            
            truncationActions.appendChild(continueBtn);
            
            const dismissBtn = document.createElement('button');
            dismissBtn.type = 'button';
            dismissBtn.className = 'btn-close';
            dismissBtn.setAttribute('data-bs-dismiss', 'alert');
            dismissBtn.setAttribute('aria-label', 'Close');
            
            truncationAlert.appendChild(truncationIcon);
            truncationAlert.appendChild(truncationMessage);
            truncationAlert.appendChild(truncationActions);
            truncationAlert.appendChild(dismissBtn);
            
            // Create processing details and error message
            const processingDetails = document.createElement('div');
            processingDetails.id = 'processing-details';
            processingDetails.className = 'alert alert-info mb-3';
            processingDetails.style.display = 'none';
            
            const processingError = document.createElement('div');
            processingError.id = 'processing-error';
            processingError.className = 'alert alert-danger';
            processingError.style.display = 'none';
            
            // Assemble all elements
            processingStatus.appendChild(progressContainer);
            processingStatus.appendChild(stepsContainer);
            processingStatus.appendChild(countersContainer);
            processingStatus.appendChild(truncationAlert);
            processingStatus.appendChild(processingDetails);
            processingStatus.appendChild(processingError);
            
            cardBody.appendChild(processingStatus);
            
            card.appendChild(cardHeader);
            card.appendChild(cardBody);
            
            resultsSection.appendChild(card);
            
            // Append results section after the upload form
            const uploadForm = document.querySelector('#upload-form');
            if (uploadForm) {
                uploadForm.parentNode.after(resultsSection);
            } else {
                container.appendChild(resultsSection);
            }
        }
        
        return true;
    }
    
    // Trigger fix on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', function() {
        console.log('Process Status Fix: DOM loaded, checking UI elements');
        
        // Check if required elements are missing
        const missingElements = [
            '#processing-status-badge',
            '.progress-bar',
            '#processed-count',
            '#total-count',
            '#case-count',
            '#case-counter',
            '#processing-details',
            '#truncation-alert',
            '#processing-error'
        ].filter(selector => document.querySelectorAll(selector).length === 0);
        
        if (missingElements.length > 0) {
            console.warn('Process Status Fix: Missing elements:', missingElements);
            createProcessingUI();
            
            // Force reload of any existing status updater instance
            if (typeof window.StatusUpdater !== 'undefined' && window.statusUpdater) {
                console.log('Process Status Fix: Reloading status updater');
                
                // Get jobId from existing instance if available
                const jobId = window.statusUpdater.jobId;
                if (jobId) {
                    console.log('Process Status Fix: Restarting polling with job ID', jobId);
                    setTimeout(() => window.statusUpdater.startPolling(jobId), 500);
                }
            }
        } else {
            console.log('Process Status Fix: All UI elements present');
        }
    });
    
    // Add manual fix function to window for debugging
    window.fixProcessingUI = createProcessingUI;

    // Add Safari-specific test function
    window.testStatusVisibility = function() {
        console.group('Safari Visibility Test');
        
        // Force display results section
        const resultsSection = document.getElementById('results-section');
        if (resultsSection) {
            console.log('Found results-section, forcing display: block');
            resultsSection.style.display = 'block';
            
            // Check computed style to verify it's actually displayed
            const computedStyle = window.getComputedStyle(resultsSection);
            console.log('Computed display value:', computedStyle.display);
        } else {
            console.error('Could not find results-section element');
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
                    element.style.display = 'block';
                    element.textContent = 'Safari test: Forcing visibility of processing details';
                    element.style.backgroundColor = '#ffff99';
                    element.style.color = '#000000';
                    element.style.padding = '10px';
                    element.style.margin = '10px 0';
                    element.style.border = '2px solid #ff9900';
                }
                
                // Show case counter
                if (name === 'case-counter') {
                    element.style.display = 'inline-block';
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
})(); 