/**
 * HTML-only scripts
 * 
 * This file contains JavaScript functions that will be included directly in HTML templates,
 * avoiding Django template syntax that causes linter errors.
 */

// Toggle view between parsed and raw response 
function toggleView(view) {
    const parsedView = document.getElementById('parsed-view');
    const rawView = document.getElementById('raw-view');
    const parsedBtn = document.getElementById('parsed-btn');
    const rawBtn = document.getElementById('raw-btn');
    
    if (view === 'parsed') {
        parsedView.style.display = 'block';
        rawView.style.display = 'none';
        parsedBtn.classList.add('active');
        rawBtn.classList.remove('active');
    } else {
        parsedView.style.display = 'none';
        rawView.style.display = 'block';
        parsedBtn.classList.remove('active');
        rawBtn.classList.add('active');
    }
    
    // Rehighlight code blocks if hljs exists
    if (typeof hljs !== 'undefined') {
        document.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightBlock(block);
        });
    }
}

// Toggle raw response visibility
function toggleRawResponse(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.display = element.style.display === 'none' ? 'block' : 'none';
    }
}

// Toggle collapse for document sections
function toggleCollapse(targetId) {
    const target = document.querySelector(targetId);
    if (target) {
        const isCurrentlyShown = target.classList.contains('show');
        
        // If we're opening this one, close any others that are open
        if (!isCurrentlyShown) {
            document.querySelectorAll('.collapse.show').forEach(openCollapse => {
                if (openCollapse.id !== targetId.substring(1)) {
                    openCollapse.classList.remove('show');
                    
                    // Update any related toggle buttons
                    const relatedRow = document.querySelector(`[data-bs-target="#${openCollapse.id}"]`);
                    if (relatedRow) {
                        const icon = relatedRow.querySelector('.bi-chevron-up');
                        if (icon) {
                            icon.classList.remove('bi-chevron-up');
                            icon.classList.add('bi-chevron-down');
                        }
                    }
                    
                    const relatedBtn = document.querySelector(`.toggle-btn[data-target="#${openCollapse.id}"]`);
                    if (relatedBtn) {
                        const icon = relatedBtn.querySelector('i');
                        const text = relatedBtn.querySelector('span');
                        if (icon) {
                            icon.classList.remove('bi-chevron-up');
                            icon.classList.add('bi-chevron-down');
                        }
                        if (text) {
                            text.textContent = 'Show Cases';
                        }
                    }
                }
            });
        }
        
        // Toggle the target
        target.classList.toggle('show');
        
        // Update row indicator
        const row = document.querySelector(`[data-bs-target="${targetId}"]`);
        if (row) {
            const icon = row.querySelector('.bi-chevron-down, .bi-chevron-up');
            if (icon) {
                if (!isCurrentlyShown) {
                    icon.classList.remove('bi-chevron-down');
                    icon.classList.add('bi-chevron-up');
                } else {
                    icon.classList.remove('bi-chevron-up');
                    icon.classList.add('bi-chevron-down');
                }
            }
        }
        
        // Update toggle button
        const toggleBtn = document.querySelector(`.toggle-btn[data-target="${targetId}"]`);
        if (toggleBtn) {
            const icon = toggleBtn.querySelector('i');
            const text = toggleBtn.querySelector('span');
            if (icon) {
                if (!isCurrentlyShown) {
                    icon.classList.remove('bi-chevron-down');
                    icon.classList.add('bi-chevron-up');
                } else {
                    icon.classList.remove('bi-chevron-up');
                    icon.classList.add('bi-chevron-down');
                }
            }
            if (text) {
                text.textContent = !isCurrentlyShown ? 'Hide Cases' : 'Show Cases';
            }
        }
    }
}

// Prompt-related functions
function loadDefaultPrompt(url) {
    $.get(url, function(data) {
        if (data.success) {
            $('#id_prompt_template').val(data.prompt);
            $('#active-prompt').text(data.prompt);
        }
    });
}

function editPrompt() {
    // Show prompt editor
    $('#prompt-editor-container').show();
    
    // Focus on the editor
    $('#id_prompt_template').focus();
}

function debugPrompt() {
    $('#debug-info').show();
    
    const prompt = $('#id_prompt_template').val();
    const files = document.getElementById('id_pdf_files').files;
    
    $('#debug-state').text(
        `Files selected: ${files.length}\nPrompt length: ${prompt.length} characters`
    );
    
    // Sample request that would be sent
    const sampleRequest = {
        prompt: prompt.substring(0, 100) + '...',
        files: Array.from(files).map(f => f.name)
    };
    
    $('#debug-request').text(JSON.stringify(sampleRequest, null, 2));
}

function useDefaultPrompt() {
    loadDefaultPrompt();
}

function toggleRawOutput() {
    $('#raw-output').toggle();
}

// Common initialization for document ready
function initializeProcessorPage() {
    // Handle PDF file selection
    $('#id_pdf_files').on('change', function(event) {
        const files = this.files;
        const tableContainer = $('#pdf-files-table');
        const filesList = $('#pdf-files-list');
        
        // Clear existing rows
        filesList.html('');
        
        if (files.length > 0) {
            // Show the table
            tableContainer.show();
            
            // Create a row for each file
            Array.from(files).forEach((file, index) => {
                const fileName = file.name;
                // Extract a default "study author" from the filename (remove extension and use as default)
                const defaultAuthor = fileName.replace(/\.[^/.]+$/, "");
                
                const row = $('<tr>').html(`
                    <td>${fileName}</td>
                    <td>
                        <input type="text" class="form-control" name="report_name_${index}" 
                            value="${fileName}" 
                            placeholder="Enter case report name">
                    </td>
                    <td>
                        <input type="text" class="form-control" name="study_author_${index}" 
                            value="${defaultAuthor}" 
                            placeholder="Enter study author">
                        <input type="hidden" name="file_index_${index}" value="${index}">
                    </td>
                `);
                filesList.append(row);
            });
        } else {
            // Hide the table if no files selected
            tableContainer.hide();
        }
    });
    
    // Toggle active prompt
    $('#toggle-active-prompt').on('click', function() {
        const container = $('#active-prompt-container');
        const button = $(this).find('i');
        
        if (container.css('display') === 'none') {
            container.show();
            button.removeClass('bi-arrows-expand').addClass('bi-arrows-collapse');
            $(this).html($(this).html().replace('Show Prompt', 'Hide Prompt'));
        } else {
            container.hide();
            button.removeClass('bi-arrows-collapse').addClass('bi-arrows-expand');
            $(this).html($(this).html().replace('Hide Prompt', 'Show Prompt'));
        }
    });
    
    // Toggle prompt editor
    $('#toggle-prompt-editor').on('click', function() {
        const container = $('#prompt-editor-container');
        const button = $(this).find('i');
        
        if (container.css('display') === 'none') {
            container.show();
            button.removeClass('bi-arrows-expand').addClass('bi-arrows-collapse');
            $(this).html($(this).html().replace('Expand', 'Collapse'));
        } else {
            container.hide();
            button.removeClass('bi-arrows-collapse').addClass('bi-arrows-expand');
            $(this).html($(this).html().replace('Collapse', 'Expand'));
        }
    });
}

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
} 