/**
 * Box-inspired theme toggle functionality
 */
document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('themeToggle');
    const themeOptions = document.querySelectorAll('.theme-option');
    const debugPanel = document.getElementById('themeDebugPanel');
    const toggleThemeDebug = document.getElementById('toggleThemeDebug');
    const closeDebugPanel = document.getElementById('closeDebugPanel');
    
    // Function to set theme
    function setTheme(theme, saveToStorage = true) {
        document.documentElement.setAttribute('data-bs-theme', theme);
        document.documentElement.setAttribute('data-theme', theme);
        
        if (saveToStorage) {
            localStorage.setItem('pdf-processor-theme', theme);
        }
        
        // Update debug panel if it exists and is visible
        updateDebugPanel();
        
        console.log(`Theme set to: ${theme}`);
    }
    
    // Function to get system theme preference
    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    
    // Function to update debug panel
    function updateDebugPanel() {
        if (!debugPanel) return;
        
        const currentThemeEl = document.getElementById('currentTheme');
        const htmlDataThemeEl = document.getElementById('htmlDataTheme');
        const htmlBsDataThemeEl = document.getElementById('htmlBsDataTheme');
        const localStorageThemeEl = document.getElementById('localStorageTheme');
        const systemPreferenceEl = document.getElementById('systemPreference');
        
        if (currentThemeEl) {
            let currentTheme = localStorage.getItem('pdf-processor-theme');
            if (!currentTheme) {
                currentTheme = `system (${getSystemTheme()})`;
            }
            currentThemeEl.textContent = currentTheme;
        }
        
        if (htmlDataThemeEl) {
            htmlDataThemeEl.textContent = document.documentElement.getAttribute('data-theme') || 'not set';
        }
        
        if (htmlBsDataThemeEl) {
            htmlBsDataThemeEl.textContent = document.documentElement.getAttribute('data-bs-theme') || 'not set';
        }
        
        if (localStorageThemeEl) {
            localStorageThemeEl.textContent = localStorage.getItem('pdf-processor-theme') || 'not set';
        }
        
        if (systemPreferenceEl) {
            systemPreferenceEl.textContent = getSystemTheme();
        }
    }
    
    // Initialize theme based on saved preference or system
    function initializeTheme() {
        const savedTheme = localStorage.getItem('pdf-processor-theme');
        
        if (savedTheme) {
            // Use saved theme
            setTheme(savedTheme, false);
        } else {
            // Use system preference
            const systemTheme = getSystemTheme();
            setTheme(systemTheme, false);
        }
        
        // Highlight the active theme in the dropdown if exists
        if (themeOptions) {
            themeOptions.forEach(option => {
                const optionTheme = option.getAttribute('data-theme');
                if ((optionTheme === savedTheme) || 
                    (!savedTheme && optionTheme === 'system')) {
                    option.classList.add('active');
                } else {
                    option.classList.remove('active');
                }
            });
        }
    }
    
    // Initialize theme on page load
    initializeTheme();
    
    // Theme toggle button handler
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(newTheme);
            
            // Update active state in dropdown
            if (themeOptions) {
                themeOptions.forEach(option => {
                    if (option.getAttribute('data-theme') === newTheme) {
                        option.classList.add('active');
                    } else {
                        option.classList.remove('active');
                    }
                });
            }
        });
    }
    
    // Theme dropdown options handlers
    if (themeOptions) {
        themeOptions.forEach(option => {
            option.addEventListener('click', function() {
                const selectedTheme = this.getAttribute('data-theme');
                
                themeOptions.forEach(opt => opt.classList.remove('active'));
                this.classList.add('active');
                
                if (selectedTheme === 'system') {
                    // Use system preference
                    localStorage.removeItem('pdf-processor-theme');
                    setTheme(getSystemTheme(), false);
                } else {
                    // Use selected theme
                    setTheme(selectedTheme);
                }
                
                // Log theme change
                console.log(`Theme changed to: ${selectedTheme}`);
            });
        });
    }
    
    // Listen for system theme preference changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        const newSystemTheme = e.matches ? 'dark' : 'light';
        
        // Only change theme if using system preference (no localStorage setting)
        if (!localStorage.getItem('pdf-processor-theme')) {
            setTheme(newSystemTheme, false);
            console.log(`System theme changed to: ${newSystemTheme}`);
        }
        
        // Update debug info if panel is visible
        updateDebugPanel();
    });
    
    // Debug panel functionality
    if (toggleThemeDebug) {
        toggleThemeDebug.addEventListener('click', function() {
            debugPanel.style.display = debugPanel.style.display === 'none' ? 'block' : 'none';
            updateDebugPanel();
        });
    }
    
    if (closeDebugPanel) {
        closeDebugPanel.addEventListener('click', function() {
            debugPanel.style.display = 'none';
        });
    }
    
    // Initialize JobStatusBanner if available
    if (typeof JobStatusBanner !== 'undefined' && !window.disableJobStatusBanner) {
        try {
            const banner = new JobStatusBanner({
                checkEndpoint: "/check-job-status/",
                pollInterval: 5000
            });
        } catch (e) {
            console.error('Error initializing JobStatusBanner:', e);
        }
    }
    
    // Update debug info every second if panel is visible
    if (debugPanel && debugPanel.style.display === 'block') {
        setInterval(updateDebugPanel, 1000);
    }
}); 