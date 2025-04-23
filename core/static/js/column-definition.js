/**
 * Column Definition Management
 * This file handles the column definition management interface functionality
 */

// Initialize global variables
let columnModal;
let promptsModal;
let columns = [];

/**
 * Opens the column definition modal
 */
function openAddColumnModal() {
    console.log('Opening add column modal');
    const modalElement = document.getElementById('columnModal');
    if (!modalElement) {
        console.error('Modal element not found');
        return;
    }
    
    // Reset the form
    document.getElementById('column-form').reset();
    document.getElementById('column-id').value = '';
    
    try {
        // Try using jQuery if available
        if (typeof $ !== 'undefined' && typeof $.fn.modal !== 'undefined') {
            console.log('Using jQuery modal');
            $(modalElement).modal('show');
            return;
        }
        
        // Otherwise use Bootstrap directly
        if (typeof bootstrap !== 'undefined' && typeof bootstrap.Modal !== 'undefined') {
            console.log('Using Bootstrap modal');
            let modal = bootstrap.Modal.getInstance(modalElement);
            if (!modal) {
                modal = new bootstrap.Modal(modalElement);
            }
            modal.show();
            return;
        }
        
        // Fallback to basic display if neither works
        console.log('Using basic modal display fallback');
        modalElement.style.display = 'block';
        modalElement.classList.add('show');
        document.body.classList.add('modal-open');
        
        // Create backdrop
        if (!document.querySelector('.modal-backdrop')) {
            const backdrop = document.createElement('div');
            backdrop.className = 'modal-backdrop fade show';
            document.body.appendChild(backdrop);
        }
    } catch (error) {
        console.error('Error showing modal:', error);
        alert('Error showing modal: ' + error.message);
    }
}

/**
 * Initialize column definition page functionality
 */
function initColumnDefinition() {
    console.log('Initializing column definition functionality');
    
    // Get the columns data from the window object (set by the template)
    if (window.columnsData && Array.isArray(window.columnsData)) {
        columns = window.columnsData;
        console.log(`Loaded ${columns.length} columns from template data`);
    }
    
    // Initialize modals
    try {
        const modalElement = document.getElementById('columnModal');
        if (modalElement) {
            columnModal = new bootstrap.Modal(modalElement, {
                keyboard: true,
                backdrop: true,
                focus: true
            });
        }
        
        const promptsModalElement = document.getElementById('promptsModal');
        if (promptsModalElement) {
            promptsModal = new bootstrap.Modal(promptsModalElement, {
                keyboard: true,
                backdrop: true
            });
        }
    } catch (error) {
        console.error('Error initializing modals:', error);
    }
    
    // Set up event listeners
    setupEventListeners();
    
    // Set the generated prompt from template data if available
    if (window.generatedPrompt) {
        const promptElement = document.getElementById('generated-prompt');
        if (promptElement) {
            promptElement.value = window.generatedPrompt;
        }
    } else {
        // Initial update of the generated prompt if not provided
        updateGeneratedPrompt();
    }
}

/**
 * Set up all event listeners for the page
 */
function setupEventListeners() {
    // Add Column button
    const addColumnBtn = document.getElementById('add-column');
    if (addColumnBtn) {
        addColumnBtn.addEventListener('click', openAddColumnModal);
    }
    
    // Edit Column buttons
    document.querySelectorAll('.edit-row').forEach(button => {
        button.addEventListener('click', function() {
            editColumn(this.closest('tr'));
        });
    });
    
    // Save Column button
    const saveColumnBtn = document.getElementById('save-column');
    if (saveColumnBtn) {
        saveColumnBtn.addEventListener('click', saveColumn);
    }
    
    // Delete Column buttons
    document.querySelectorAll('.delete-row').forEach(button => {
        button.addEventListener('click', function() {
            deleteColumn(this.closest('tr'));
        });
    });
    
    // Save Prompt button
    const savePromptBtn = document.getElementById('save-prompt');
    if (savePromptBtn) {
        savePromptBtn.addEventListener('click', savePrompt);
    }
    
    // Load Prompt button
    const loadPromptBtn = document.getElementById('load-prompt');
    if (loadPromptBtn) {
        loadPromptBtn.addEventListener('click', function() {
            loadPrompts();
            if (promptsModal) promptsModal.show();
        });
    }
    
    // Variables change handler
    ['disease_condition', 'population_age', 'grading_of_lesion'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', updateGeneratedPrompt);
            element.addEventListener('input', updateGeneratedPrompt);
        }
    });
    
    // Apply Defaults button
    const applyDefaultsBtn = document.getElementById('apply-defaults');
    if (applyDefaultsBtn) {
        applyDefaultsBtn.addEventListener('click', applyDefaults);
    }
    
    // Enhance category select with icons
    const categorySelect = document.getElementById('category');
    if (categorySelect) {
        Array.from(categorySelect.options).forEach(option => {
            const icon = option.dataset.icon;
            if (icon) {
                option.innerHTML = `<i class="bi ${icon}"></i> ${option.text}`;
            }
        });
    }
    
    // Add debug button to prompt card header
    const promptHeader = document.querySelector('.card-header .btn-group');
    if (promptHeader) {
        const debugBtn = document.createElement('button');
        debugBtn.className = 'btn btn-sm btn-outline-info';
        debugBtn.innerHTML = '<i class="bi bi-bug"></i> Debug Prompt';
        debugBtn.onclick = function() {
            const promptText = document.getElementById('generated-prompt').value;
            console.log('Current prompt template:', promptText);
            
            const debugInfo = document.getElementById('debug-info');
            if (debugInfo) {
                debugInfo.style.display = 'block';
                document.getElementById('debug-prompt').textContent = promptText;
            }
        };
        promptHeader.prepend(debugBtn);
    }
    
    // Set up modal close handlers
    document.querySelectorAll('[data-bs-dismiss="modal"]').forEach(button => {
        button.addEventListener('click', function() {
            const modalId = this.closest('.modal').id;
            closeModal(modalId);
        });
    });
}

/**
 * Shows an error message to the user
 */
function showError(message) {
    alert(message);
}

/**
 * Closes a modal with graceful fallbacks
 */
function closeModal(modalId) {
    // Try Bootstrap first
    try {
        if (typeof bootstrap !== 'undefined') {
            const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
            if (modal) {
                modal.hide();
                return;
            }
        }
    } catch (e) {
        console.error('Bootstrap modal close failed:', e);
    }
    
    // Fallback to jQuery
    try {
        if (typeof $ !== 'undefined') {
            $(`#${modalId}`).modal('hide');
            return;
        }
    } catch (e) {
        console.error('jQuery modal close failed:', e);
    }
    
    // Manual fallback if both fail
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('show');
        document.body.classList.remove('modal-open');
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    }
}

/**
 * Edits an existing column
 */
function editColumn(row) {
    if (!row) return;
    
    const columnId = row.getAttribute('data-column-id');
    if (!columnId) return;
    
    document.getElementById('column-id').value = columnId;
    document.getElementById('name').value = row.cells[0].textContent.trim();
    document.getElementById('description').value = row.cells[1].textContent.trim();
    document.getElementById('category').value = row.closest('table').dataset.category;
    document.getElementById('include_confidence').checked = 
        row.querySelector('input[type="checkbox"]').checked;
    
    openAddColumnModal();
}

/**
 * Saves a column definition
 */
function saveColumn() {
    const form = document.getElementById('column-form');
    const formData = new FormData(form);
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // Use apiUrls passed from the template
    const saveUrl = window.apiUrls?.saveColumns || '/save-columns/';
    
    // Debug - log what we're sending
    const columnData = {
        id: formData.get('id') || null,
        name: formData.get('name'),
        description: formData.get('description'),
        category: formData.get('category'),
        include_confidence: formData.get('include_confidence') === 'on'
    };
    
    console.log('Saving column to URL:', saveUrl);
    console.log('Column data:', columnData);
    console.log('CSRF Token:', csrfToken ? 'present' : 'missing');
    
    fetch(saveUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            columns: [columnData]
        })
    })
    .then(response => {
        console.log('Response status:', response.status, response.statusText);
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Response data:', data);
        if (data.success) {
            // Update the prompt before reloading
            updateGeneratedPrompt().then(() => {
                location.reload();
            });
        } else {
            showError(data.error || 'Failed to save column');
        }
    })
    .catch(error => {
        console.error('Error saving column:', error);
        showError(error.message);
    });
}

/**
 * Deletes a column definition
 */
function deleteColumn(row) {
    if (!confirm('Are you sure you want to delete this column?')) {
        return;
    }

    const columnId = row.getAttribute('data-column-id');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    // Use apiUrls passed from the template
    const deleteUrl = window.apiUrls?.deleteColumn.replace(':id', columnId) || `/columns/delete/${columnId}/`;
    
    fetch(deleteUrl, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            row.remove();
            updateGeneratedPrompt();
        } else {
            showError(data.error || 'Failed to delete column');
        }
    })
    .catch(error => {
        console.error('Error deleting column:', error);
        showError(error.message);
    });
}

/**
 * Updates the generated prompt
 */
function updateGeneratedPrompt() {
    const variables = {
        disease_condition: document.getElementById('disease_condition')?.value || '',
        population_age: document.getElementById('population_age')?.value || '',
        grading_of_lesion: document.getElementById('grading_of_lesion')?.value || ''
    };
    
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    
    // Use apiUrls passed from the template
    const saveUrl = window.apiUrls?.saveColumns || '/save-columns/';

    return fetch(saveUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            action: 'generate_prompt',
            variables: variables
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success && data.prompt_template) {
            const promptElement = document.getElementById('generated-prompt');
            if (promptElement) {
                promptElement.value = data.prompt_template;
                // Also update debug info if visible
                const debugPrompt = document.getElementById('debug-prompt');
                if (debugPrompt) {
                    debugPrompt.textContent = data.prompt_template;
                }
            }
        } else {
            throw new Error(data.error || 'Failed to generate prompt');
        }
    })
    .catch(error => {
        console.error('Error updating prompt:', error);
        showError(error.message);
    });
}

/**
 * Applies default columns
 */
function applyDefaults() {
    if (confirm('Are you sure you want to reset to default columns? This will remove all custom columns.')) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        // Use apiUrls passed from the template
        const applyUrl = window.apiUrls?.applyDefaults || '/apply-default-columns/';
        
        fetch(applyUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                updateGeneratedPrompt().then(() => {
                    location.reload();
                });
            } else {
                throw new Error(data.error || 'Failed to apply default columns');
            }
        })
        .catch(error => {
            console.error('Error applying defaults:', error);
            showError('Failed to apply default columns: ' + error.message);
        });
    }
}

/**
 * Saves the current prompt
 */
function savePrompt() {
    const promptContent = document.getElementById('generated-prompt').value;
    if (!promptContent.trim()) {
        showError('No prompt content to save');
        return;
    }

    const variables = {
        disease_condition: document.getElementById('disease_condition')?.value || '',
        population_age: document.getElementById('population_age')?.value || '',
        grading_of_lesion: document.getElementById('grading_of_lesion')?.value || ''
    };
    
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
    
    // Use apiUrls passed from the template
    const savePromptUrl = window.apiUrls?.savePrompt || '/save-prompt/';
    
    fetch(savePromptUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            name: `Column-based Prompt ${timestamp}`,
            content: promptContent,
            variables: variables
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert('Prompt saved successfully!');
        } else {
            throw new Error(data.error || 'Failed to save prompt');
        }
    })
    .catch(error => {
        console.error('Error saving prompt:', error);
        showError('Failed to save prompt: ' + error.message);
    });
}

/**
 * Loads available prompts
 */
function loadPrompts() {
    // Use apiUrls passed from the template
    const loadPromptUrl = window.apiUrls?.loadPrompts || '/load-prompts/';
    
    fetch(loadPromptUrl)
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        const promptsList = document.getElementById('prompts-list');
        if (promptsList) {
            promptsList.innerHTML = '';
            data.prompts.forEach(prompt => {
                const li = document.createElement('li');
                li.className = 'list-group-item d-flex justify-content-between align-items-center';
                li.innerHTML = `
                    <span>${prompt.name}</span>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-outline-primary load-prompt" 
                                data-prompt-id="${prompt.id}">
                            <i class="bi bi-box-arrow-in-down"></i> Load
                        </button>
                        <button class="btn btn-sm btn-outline-danger delete-prompt" 
                                data-prompt-id="${prompt.id}">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                `;
                promptsList.appendChild(li);
            });

            // Add event listeners to the new buttons
            promptsList.querySelectorAll('.load-prompt').forEach(button => {
                button.addEventListener('click', function() {
                    const promptId = this.dataset.promptId;
                    loadPrompt(promptId);
                });
            });
        }
    })
    .catch(error => {
        console.error('Error loading prompts:', error);
        showError('Failed to load prompts: ' + error.message);
    });
}

/**
 * Loads a specific prompt
 */
function loadPrompt(promptId) {
    // Use apiUrls passed from the template
    const getPromptUrl = window.apiUrls?.getPrompt.replace(':id', promptId) || `/get-prompt/${promptId}/`;
    
    fetch(getPromptUrl)
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        document.getElementById('generated-prompt').value = data.content;
        if (data.variables) {
            document.getElementById('disease_condition').value = data.variables.disease_condition || '';
            document.getElementById('population_age').value = data.variables.population_age || '';
            document.getElementById('grading_of_lesion').value = data.variables.grading_of_lesion || '';
        }
        if (promptsModal) {
            promptsModal.hide();
        }
    })
    .catch(error => {
        console.error('Error loading prompt:', error);
        showError('Failed to load prompt: ' + error.message);
    });
}

// Initialize the page when DOM is fully loaded
document.addEventListener('DOMContentLoaded', initColumnDefinition); 