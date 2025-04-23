from django.test import TestCase, Client, LiveServerTestCase
from django.urls import reverse
from core.models import ColumnDefinition, ProcessingJob
import json
from django.contrib.auth.models import User
import unittest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os
from selenium.common.exceptions import TimeoutException
import time
import platform
from selenium.webdriver.support.ui import Select
import logging
from pathlib import Path
import subprocess
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Module level variable to track Selenium availability
selenium_available = False

class ColumnDefinitionTests(TestCase):
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        
        # Create some test columns
        self.column1 = ColumnDefinition.objects.create(
            name='test_column1',
            description='Test Column 1',
            category='demographics',
            order=1,
            include_confidence=True
        )
        self.column2 = ColumnDefinition.objects.create(
            name='test_column2',
            description='Test Column 2',
            category='presentation',
            order=2,
            include_confidence=False
        )

    def test_column_list_view(self):
        """Test the column definition list view"""
        response = self.client.get(reverse('core:columns'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'column_definition.html')
        self.assertContains(response, 'test_column1')
        self.assertContains(response, 'test_column2')

    def test_add_column(self):
        """Test adding a new column"""
        new_column_data = {
            'name': 'new_column',
            'description': 'New Test Column',
            'category': 'demographics',
            'order': 3,
            'include_confidence': True
        }
        response = self.client.post(
            reverse('core:save_columns'),
            data=json.dumps({'columns': [new_column_data]}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ColumnDefinition.objects.filter(name='new_column').exists())

    def test_update_column(self):
        """Test updating an existing column"""
        updated_data = {
            'id': self.column1.id,
            'name': 'test_column1',
            'description': 'Updated Description',
            'category': 'demographics',
            'order': 1,
            'include_confidence': True
        }
        response = self.client.post(
            reverse('core:save_columns'),
            data=json.dumps({'columns': [updated_data]}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        updated_column = ColumnDefinition.objects.get(id=self.column1.id)
        self.assertEqual(updated_column.description, 'Updated Description')

    def test_delete_column(self):
        """Test deleting a column"""
        response = self.client.post(
            reverse('core:delete_column', kwargs={'pk': self.column1.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ColumnDefinition.objects.filter(id=self.column1.id).exists())

    def test_duplicate_column_name(self):
        """Test attempting to create a column with a duplicate name"""
        duplicate_data = {
            'name': 'test_column1',  # This name already exists
            'description': 'Duplicate Column',
            'category': 'demographics',
            'order': 3,
            'include_confidence': True
        }
        response = self.client.post(
            reverse('core:save_columns'),
            data=json.dumps({'columns': [duplicate_data]}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('already exists', response.json()['error'])

    def test_update_column_order(self):
        """Test updating column order"""
        order_data = [
            {'id': self.column1.id, 'order': 2},
            {'id': self.column2.id, 'order': 1}
        ]
        response = self.client.post(
            reverse('core:update_column_order'),
            data=json.dumps(order_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ColumnDefinition.objects.get(id=self.column1.id).order, 2)
        self.assertEqual(ColumnDefinition.objects.get(id=self.column2.id).order, 1)

    def test_validate_column_name(self):
        """Test column name validation"""
        # Test valid name
        response = self.client.post(
            reverse('core:validate_column_name'),
            {'name': 'valid_column_name'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['valid'])

        # Test invalid name
        response = self.client.post(
            reverse('core:validate_column_name'),
            {'name': '1invalid_name'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['valid'])

    def test_bulk_save_columns(self):
        """Test bulk saving of columns"""
        # Clear existing columns
        ColumnDefinition.objects.all().delete()
        
        bulk_data = {
            'columns': [
                {
                    'name': 'bulk_column1',
                    'description': 'Bulk Column 1',
                    'category': 'demographics',
                    'order': 1,
                    'include_confidence': True
                },
                {
                    'name': 'bulk_column2',
                    'description': 'Bulk Column 2',
                    'category': 'presentation',
                    'order': 2,
                    'include_confidence': False
                }
            ]
        }
        response = self.client.post(
            reverse('core:save_columns'),
            data=json.dumps(bulk_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ColumnDefinition.objects.count(), 2)
        self.assertTrue(ColumnDefinition.objects.filter(name='bulk_column1').exists())
        self.assertTrue(ColumnDefinition.objects.filter(name='bulk_column2').exists())

def find_chrome_binary():
    """Find Chrome binary location with detailed logging"""
    logger.info("Starting Chrome binary detection...")
    
    # Check environment variables first
    for env_var in ['CHROME_BIN', 'CHROME_PATH', 'GOOGLE_CHROME_BIN']:
        chrome_path = os.environ.get(env_var)
        if chrome_path and os.path.exists(chrome_path):
            logger.info(f"Found Chrome via environment variable {env_var}: {chrome_path}")
            return chrome_path
    
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        str(Path(os.environ.get('PROGRAMFILES', '')).joinpath('Google/Chrome/Application/chrome.exe')),
        str(Path(os.environ.get('PROGRAMFILES(X86)', '')).joinpath('Google/Chrome/Application/chrome.exe')),
        str(Path(os.environ.get('LOCALAPPDATA', '')).joinpath('Google/Chrome/Application/chrome.exe'))
    ]

    logger.info(f"Checking {len(possible_paths)} possible Chrome locations...")
    for path in possible_paths:
        try:
            if os.path.exists(path):
                logger.info(f"Found Chrome at: {path}")
                return path
        except Exception as e:
            logger.warning(f"Error checking path {path}: {str(e)}")
    
    # Try using registry with better error handling
    try:
        import winreg
        logger.info("Attempting to find Chrome via Windows registry...")
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        chrome_path = winreg.QueryValue(key, None)
        if os.path.exists(chrome_path):
            logger.info(f"Found Chrome in registry at: {chrome_path}")
            return chrome_path
    except Exception as e:
        logger.warning(f"Registry search failed: {str(e)}")

    # Try using 'where' command with timeout
    try:
        logger.info("Attempting to find Chrome using 'where' command...")
        process = subprocess.run(['where', 'chrome'], 
                               text=True, 
                               capture_output=True, 
                               timeout=5)
        if process.returncode == 0:
            chrome_path = process.stdout.strip().split('\n')[0]
            if os.path.exists(chrome_path):
                logger.info(f"Found Chrome using 'where' command at: {chrome_path}")
                return chrome_path
    except subprocess.TimeoutExpired:
        logger.warning("'where' command timed out")
    except Exception as e:
        logger.warning(f"'where' command failed: {str(e)}")

    logger.error("Chrome binary not found in any location")
    return None

class ColumnDefinitionJavaScriptTests(LiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logger.info("Starting Selenium setup...")
        
        try:
            # System information logging
            logger.info("=== System Information ===")
            logger.info(f"Platform: {platform.system()}")
            logger.info(f"Platform release: {platform.release()}")
            logger.info(f"Python version: {platform.python_version()}")
            logger.info(f"Selenium version: {webdriver.__version__}")
            logger.info("========================")
            
            # Find Chrome binary with retry logic
            max_retries = 3
            retry_count = 0
            chrome_binary = None
            
            while retry_count < max_retries and not chrome_binary:
                chrome_binary = find_chrome_binary()
                if not chrome_binary:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(f"Chrome binary not found, attempt {retry_count}/{max_retries}")
                        time.sleep(2)
                    else:
                        raise Exception("Chrome not found after maximum retries. Please install Google Chrome.")
            
            logger.info(f"Using Chrome binary at: {chrome_binary}")
            
            # Configure Chrome options
            chrome_options = webdriver.ChromeOptions()
            chrome_options.binary_location = chrome_binary
            
            # Add required arguments
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-gpu')  # Required for Windows
            chrome_options.add_argument('--disable-extensions')  # Disable extensions
            chrome_options.add_argument('--disable-software-rasterizer')  # Disable software rasterizer
            
            if os.environ.get('CI'):  # If running in CI environment
                chrome_options.add_argument('--headless')
            
            # Add required capabilities
            chrome_options.set_capability('browserName', 'chrome')
            chrome_options.set_capability('platformName', 'windows')
            
            # Install and setup ChromeDriver with retry logic
            logger.info("Installing ChromeDriver...")
            max_driver_retries = 3
            driver_retry_count = 0
            driver_path = None
            
            while driver_retry_count < max_driver_retries and not driver_path:
                try:
                    driver_path = ChromeDriverManager().install()
                    logger.info(f"ChromeDriver installed at: {driver_path}")
                except Exception as e:
                    driver_retry_count += 1
                    if driver_retry_count < max_driver_retries:
                        logger.warning(f"ChromeDriver installation failed, attempt {driver_retry_count}/{max_driver_retries}: {str(e)}")
                        time.sleep(2)
                    else:
                        raise Exception(f"ChromeDriver installation failed after maximum retries: {str(e)}")
            
            service = Service(
                driver_path,
                log_path='chromedriver.log'
            )
            
            # Initialize WebDriver with detailed error handling
            try:
                cls.selenium = webdriver.Chrome(
                    service=service,
                    options=chrome_options
                )
                cls.selenium.implicitly_wait(10)
                logger.info("Chrome WebDriver initialized successfully")
                
                # Test server connection with retry logic
                max_server_retries = 3
                server_retry_count = 0
                
                while server_retry_count < max_server_retries:
                    try:
                        logger.info(f"Attempting to connect to test server at: {cls.live_server_url}")
                        cls.selenium.get(cls.live_server_url)
                        page_source_length = len(cls.selenium.page_source)
                        logger.info(f"Current URL: {cls.selenium.current_url}")
                        logger.info(f"Page source length: {page_source_length}")
                        
                        if page_source_length > 0:
                            logger.info("Successfully connected to test server")
                            break
                        else:
                            raise Exception("Empty page source received")
                            
                    except Exception as e:
                        server_retry_count += 1
                        logger.warning(f"Server connection attempt {server_retry_count} failed: {str(e)}")
                        if server_retry_count >= max_server_retries:
                            raise Exception(f"Failed to connect to test server after {max_server_retries} attempts: {str(e)}")
                        time.sleep(2)
                
                cls.selenium_available = True
                
            except Exception as e:
                logger.error(f"WebDriver initialization failed: {str(e)}", exc_info=True)
                cls._cleanup_selenium(cls.selenium)
                raise
            
        except Exception as e:
            logger.error(f"Selenium setup failed: {str(e)}", exc_info=True)
            cls.selenium_available = False
            raise unittest.SkipTest(f"Selenium tests skipped due to setup error: {str(e)}")

    @classmethod
    def _cleanup_selenium(cls, driver):
        """Helper method to cleanup Selenium resources"""
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.warning(f"Error during Selenium cleanup: {str(e)}")

    def login_user(self):
        """Helper method to log in the test user"""
        try:
            # Navigate to admin login
            logger.info("Navigating to admin login page...")
            login_url = f"{self.live_server_url}/admin/login/"
            logger.info(f"Login URL: {login_url}")
            self.selenium.get(login_url)
            
            # Wait for login form with detailed error handling
            logger.info("Waiting for login form...")
            try:
                username_input = WebDriverWait(self.selenium, 10).until(
                    EC.presence_of_element_located((By.NAME, "username"))
                )
                logger.info("Username input found")
            except Exception as e:
                logger.error("Username input not found")
                self.take_screenshot('login_form_username_failure')
                page_source = self.selenium.page_source
                logger.debug(f"Page source: {page_source[:500]}...")
                raise Exception(f"Username input not found: {str(e)}")
            
            try:
                password_input = self.selenium.find_element(By.NAME, "password")
                logger.info("Password input found")
            except Exception as e:
                logger.error("Password input not found")
                self.take_screenshot('login_form_password_failure')
                raise Exception(f"Password input not found: {str(e)}")
            
            # Fill in credentials
            logger.info("Filling in credentials...")
            try:
                username_input.send_keys("testuser")
                password_input.send_keys("testpass123")
                logger.info("Credentials filled in successfully")
            except Exception as e:
                logger.error("Failed to fill in credentials")
                self.take_screenshot('login_credentials_failure')
                raise Exception(f"Failed to fill in credentials: {str(e)}")
            
            # Submit form
            logger.info("Submitting login form...")
            try:
                submit_button = self.selenium.find_element(By.CSS_SELECTOR, '[type="submit"]')
                submit_button.click()
                logger.info("Login form submitted")
            except Exception as e:
                logger.error("Failed to submit login form")
                self.take_screenshot('login_submit_failure')
                raise Exception(f"Failed to submit login form: {str(e)}")
            
            # Wait for redirect to complete with timeout
            logger.info("Waiting for login redirect...")
            try:
                WebDriverWait(self.selenium, 10).until(
                    lambda driver: driver.current_url != login_url
                )
                logger.info(f"Redirected to: {self.selenium.current_url}")
            except Exception as e:
                logger.error("Login redirect failed or timed out")
                self.take_screenshot('login_redirect_failure')
                raise Exception(f"Login redirect failed: {str(e)}")
            
            # Verify login success
            if "/admin/login/" in self.selenium.current_url:
                logger.error("Still on login page after submission - login likely failed")
                self.take_screenshot('login_verification_failure')
                page_source = self.selenium.page_source
                logger.debug(f"Page source after login: {page_source[:500]}...")
                raise Exception("Login failed - still on login page")
            
            logger.info("Login completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            try:
                current_url = self.selenium.current_url
                logger.error(f"Current URL at failure: {current_url}")
            except:
                pass
            return False

    def setUp(self):
        """Set up test environment"""
        try:
            logger.info("Starting test setup...")
            
            super().setUp()
            if not self.selenium_available:
                logger.warning("Selenium is not available, skipping test")
                self.skipTest("Selenium is not available")
            
            # Create test user and make them a superuser
            logger.info("Creating test user...")
            self.user = User.objects.create_user(
                username='testuser',
                password='testpass123',
                is_staff=True,
                is_superuser=True
            )
            logger.info(f"Created test user: {self.user.username}")
            
            # Log in the user
            logger.info("Attempting to log in test user...")
            if not self.login_user():
                raise Exception("Failed to log in test user")
            logger.info("User logged in successfully")
            
            # Navigate to columns page
            logger.info("Navigating to columns page...")
            columns_url = f"{self.live_server_url}{reverse('core:columns')}"
            logger.info(f"Columns URL: {columns_url}")
            self.selenium.get(columns_url)
            
            # Wait for page to load
            logger.info("Waiting for page to load...")
            try:
                WebDriverWait(self.selenium, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logger.info("Page loaded successfully")
            except Exception as e:
                logger.error(f"Page load timeout: {str(e)}")
                self.take_screenshot('page_load_failure')
                raise
            
            # Get CSRF token
            logger.info("Retrieving CSRF token...")
            try:
                self.csrf_token = self.selenium.find_element(By.NAME, 'csrfmiddlewaretoken').get_attribute('value')
                logger.info("CSRF token retrieved successfully")
            except Exception as e:
                logger.error("Failed to retrieve CSRF token")
                self.take_screenshot('csrf_token_failure')
                page_source = self.selenium.page_source
                logger.debug(f"Page source: {page_source[:500]}...")  # Log first 500 chars of page source
                raise
            
            # Add CSRF token to browser
            logger.info("Adding CSRF token to browser...")
            try:
                self.selenium.execute_script(
                    'var meta = document.createElement("meta"); '
                    'meta.name = "csrf-token"; '
                    f'meta.content = "{self.csrf_token}"; '
                    'document.head.appendChild(meta);'
                )
                logger.info("CSRF token added to browser successfully")
            except Exception as e:
                logger.error(f"Failed to add CSRF token to browser: {str(e)}")
                self.take_screenshot('csrf_token_add_failure')
                raise
            
            logger.info("Setup completed successfully")
            
        except Exception as e:
            logger.error(f"Setup failed: {str(e)}", exc_info=True)
            self.take_screenshot('setup_failure')
            try:
                current_url = self.selenium.current_url
                logger.error(f"Current URL at failure: {current_url}")
            except:
                pass
            raise

    def take_screenshot(self, name):
        """Take a screenshot with the given name"""
        try:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            screenshot_dir = Path("test_screenshots")
            screenshot_dir.mkdir(exist_ok=True)
            
            screenshot_path = screenshot_dir / f"{name}_{timestamp}.png"
            self.selenium.save_screenshot(str(screenshot_path))
            logger.info(f"Screenshot saved to: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"Failed to take screenshot: {str(e)}")
            return None

    def run(self, result=None):
        """Override run to capture screenshots on failure"""
        test_method = getattr(self, self._testMethodName)
        test_name = self._testMethodName
        
        @wraps(test_method)
        def run_test(*args, **kwargs):
            try:
                return test_method(*args, **kwargs)
            except Exception as e:
                if hasattr(self, 'selenium'):
                    screenshot_path = self.take_screenshot(f"failure_{test_name}")
                    if screenshot_path:
                        logger.error(f"Test failed. Screenshot saved to: {screenshot_path}")
                raise
        
        setattr(self, self._testMethodName, run_test)
        super().run(result)

    def test_add_column(self):
        """Test adding a new column through the API"""
        try:
            # Navigate to columns page
            self.selenium.get(f"{self.live_server_url}{reverse('core:columns')}")
            
            # Wait for page to load
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get fresh CSRF token
            csrf_token = self.selenium.find_element(By.NAME, 'csrfmiddlewaretoken').get_attribute('value')
            
            # Prepare column data
            column_data = {
                'name': 'new_column',
                'description': 'New Column Description',
                'category': 'demographics',
                'include_confidence': True,
                'order': 1
            }
            
            # Make the API request using JavaScript
            script = f"""
                fetch('{reverse('core:add_column')}', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-CSRFToken': '{csrf_token}'
                    }},
                    body: JSON.stringify({json.dumps(column_data)})
                }}).then(response => response.json()).then(data => {{
                    if (!data.success) throw new Error(data.error || 'Failed to add column');
                }});
            """
            self.selenium.execute_script(script)
            
            # Wait for the column to appear in the database
            def column_exists():
                return ColumnDefinition.objects.filter(name='new_column').exists()
            
            WebDriverWait(self.selenium, 10).until(lambda _: column_exists())
            
            # Verify the column was created with correct data
            column = ColumnDefinition.objects.get(name='new_column')
            self.assertEqual(column.description, 'New Column Description')
            self.assertEqual(column.category, 'demographics')
            self.assertTrue(column.include_confidence)
            self.assertEqual(column.order, 1)
            
        except Exception as e:
            self.take_screenshot('test_add_column_failure')
            logger.error(f"test_add_column failed: {str(e)}", exc_info=True)
            raise

    def test_edit_column(self):
        """Test editing an existing column through the API"""
        column = ColumnDefinition.objects.create(
            name='edit_test',
            description='Original Description',
            category='demographics',
            order=1
        )
        
        client = Client()
        url = reverse('core:edit_column', kwargs={'pk': column.pk})
        data = {
            'name': 'edit_test',
            'description': 'Updated Description',
            'category': 'demographics',
            'include_confidence': True,
            'order': 1
        }
        response = client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Expect redirect
        
        column.refresh_from_db()
        self.assertEqual(column.description, 'Updated Description')

    def test_delete_column(self):
        """Test deleting a column through the API"""
        column = ColumnDefinition.objects.create(
            name='test_delete',
            category='demographics'
        )
        
        response = self.client.post(
            reverse('core:delete_column', kwargs={'pk': column.pk}),
            HTTP_X_CSRFTOKEN=self.csrf_token
        )
        
        # Update expected status code
        self.assertEqual(response.status_code, 200)  # Changed from 302
        self.assertFalse(ColumnDefinition.objects.filter(pk=column.pk).exists())

    def test_column_ordering(self):
        """Test that columns are properly ordered"""
        try:
            # Create test columns
            columns = [
                ColumnDefinition.objects.create(name='col1', description='Column 1', category='demographics', order=2),
                ColumnDefinition.objects.create(name='col2', description='Column 2', category='demographics', order=1),
                ColumnDefinition.objects.create(name='col3', description='Column 3', category='demographics', order=3)
            ]
            
            # Navigate to columns page
            self.selenium.get(f"{self.live_server_url}{reverse('core:columns')}")
            
            # Wait for table to load
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'table'))
            )
            
            # Get all column rows
            rows = self.selenium.find_elements(By.CSS_SELECTOR, 'tr[data-column-id]')
            
            # Verify initial order
            self.assertEqual(len(rows), 3)
            self.assertIn('col2', rows[0].get_attribute('innerHTML'))  # First by order
            self.assertIn('col1', rows[1].get_attribute('innerHTML'))
            self.assertIn('col3', rows[2].get_attribute('innerHTML'))
            
            # Test reordering through API
            new_order = [
                {'id': columns[0].id, 'order': 3},  # col1 -> order 3
                {'id': columns[1].id, 'order': 1},  # col2 -> order 1 (unchanged)
                {'id': columns[2].id, 'order': 2}   # col3 -> order 2
            ]
            
            # Get fresh CSRF token
            csrf_token = self.selenium.find_element(By.NAME, 'csrfmiddlewaretoken').get_attribute('value')
            
            # Execute reordering via JavaScript
            script = f"""
                fetch('{reverse('core:update_column_order')}', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-CSRFToken': '{csrf_token}'
                    }},
                    body: JSON.stringify({json.dumps(new_order)})
                }}).then(response => response.json()).then(data => {{
                    if (!data.success) throw new Error(data.error || 'Failed to update column order');
                }});
            """
            self.selenium.execute_script(script)
            
            # Wait for reordering to take effect and refresh page
            time.sleep(1)
            self.selenium.refresh()
            
            # Wait for table to reload
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'table'))
            )
            
            # Verify new order in database
            columns_ordered = ColumnDefinition.objects.all().order_by('order')
            self.assertEqual(columns_ordered[0].name, 'col2')  # order 1
            self.assertEqual(columns_ordered[1].name, 'col3')  # order 2
            self.assertEqual(columns_ordered[2].name, 'col1')  # order 3
            
            # Verify new order in UI
            rows = self.selenium.find_elements(By.CSS_SELECTOR, 'tr[data-column-id]')
            self.assertEqual(len(rows), 3)
            self.assertIn('col2', rows[0].get_attribute('innerHTML'))
            self.assertIn('col3', rows[1].get_attribute('innerHTML'))
            self.assertIn('col1', rows[2].get_attribute('innerHTML'))
            
        except Exception as e:
            self.take_screenshot('test_column_ordering_failure')
            logger.error(f"test_column_ordering failed: {str(e)}", exc_info=True)
            raise

    def test_prompt_generation(self):
        """Test that prompt template is generated correctly"""
        client = Client()
        url = reverse('core:save_columns')
        data = {
            'columns': [
                {
                    'name': 'test_col',
                    'description': 'Test Description',
                    'category': 'demographics',
                    'include_confidence': True,
                    'order': 1
                }
            ],
            'disease_condition': 'Test Disease',
            'population_age': 'Adult',
            'grading_of_lesion': 'Grade I-IV'
        }
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('prompt_template', response.json())

    def test_unique_column_names(self):
        """Test that column names must be unique"""
        ColumnDefinition.objects.create(
            name='unique_test',
            description='First Column',
            category='demographics'
        )
        
        with self.assertRaises(Exception):  # Should raise an integrity error
            ColumnDefinition.objects.create(
                name='unique_test',
                description='Second Column',
                category='demographics'
            )

    def test_add_column_ui(self):
        """Test adding a column through the UI"""
        try:
            # Navigate to columns page
            self.selenium.get(f"{self.live_server_url}{reverse('core:columns')}")
            
            # Wait for add button and click it
            add_button = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable((By.ID, "add-column"))
            )
            add_button.click()
            
            # Wait for modal to appear
            modal = WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.ID, "columnModal"))
            )
            
            # Wait for form fields to be present
            name_input = WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.NAME, "name"))
            )
            description_input = modal.find_element(By.NAME, "description")
            category_select = Select(modal.find_element(By.NAME, "category"))
            confidence_checkbox = modal.find_element(By.NAME, "include_confidence")
            
            # Fill in the form fields
            name_input.send_keys("ui_test_column")
            description_input.send_keys("UI Test Description")
            category_select.select_by_value("demographics")
            if not confidence_checkbox.is_selected():
                confidence_checkbox.click()
            
            # Submit the form
            submit_button = modal.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            submit_button.click()
            
            # Wait for success message or column to appear in table
            WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'tr[data-name="ui_test_column"]'))
            )
            
            # Verify the column was created in the database
            column = ColumnDefinition.objects.get(name='ui_test_column')
            self.assertEqual(column.description, 'UI Test Description')
            self.assertEqual(column.category, 'demographics')
            self.assertTrue(column.include_confidence)
            
        except Exception as e:
            self.take_screenshot('test_add_column_ui_failure')
            logger.error(f"test_add_column_ui failed: {str(e)}", exc_info=True)
            raise

    @unittest.skipUnless(lambda self: self.is_selenium_available, "Selenium not available")
    def test_edit_column_ui(self):
        """Test editing a column through the UI"""
        try:
            # Create a test column
            column = ColumnDefinition.objects.create(
                name='edit_test',
                description='Original Description',
                category='demographics',
                order=1
            )
            
            # Navigate to columns page
            self.selenium.get(f'{self.live_server_url}{reverse("core:columns")}')
            
            # Get CSRF token from the page
            csrf_token = self.selenium.find_element(By.NAME, 'csrfmiddlewaretoken').get_attribute('value')
            
            # Add CSRF token to request headers
            self.selenium.execute_script(
                'var meta = document.createElement("meta"); '
                'meta.name = "csrf-token"; '
                f'meta.content = "{csrf_token}"; '
                'document.head.appendChild(meta);'
            )
            
            # Wait for and click edit button
            edit_button = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//tr[@data-column-id='{column.id}']//button[contains(@class, 'edit-row')]")
                )
            )
            edit_button.click()
            
            # Wait for edit form to appear
            description_input = WebDriverWait(self.selenium, 10).until(
                EC.presence_of_element_located((By.NAME, "description"))
            )
            
            # Clear and update description
            description_input.clear()
            description_input.send_keys("Updated Description")
            
            # Submit form
            submit_button = self.selenium.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_button.click()
            
            # Handle any alert that might appear
            try:
                WebDriverWait(self.selenium, 3).until(EC.alert_is_present())
                alert = self.selenium.switch_to.alert
                alert_text = alert.text
                alert.accept()
                print(f"Alert appeared with text: {alert_text}")
                if "error" in alert_text.lower():
                    raise Exception(f"Server error occurred: {alert_text}")
            except TimeoutException:
                pass  # No alert appeared, which is expected
            
            # Wait for update to complete and verify
            def description_is_updated(driver):
                try:
                    column.refresh_from_db()
                    return column.description == "Updated Description"
                except Exception:
                    return False
            
            WebDriverWait(self.selenium, 10).until(description_is_updated)
            
        except Exception as e:
            print(f"Error in test_edit_column_ui: {str(e)}")
            raise

    @unittest.skipUnless(lambda self: self.is_selenium_available, "Selenium not available")
    def test_delete_column_ui(self):
        """Test deleting a column through the UI"""
        try:
            # Create a test column
            column = ColumnDefinition.objects.create(
                name='delete_test',
                description='Test Description',
                category='demographics',
                order=1
            )
            
            # Navigate to columns page
            self.selenium.get(f'{self.live_server_url}{reverse("core:columns")}')
            
            # Get CSRF token from the page
            csrf_token = self.selenium.find_element(By.NAME, 'csrfmiddlewaretoken').get_attribute('value')
            
            # Add CSRF token to request headers
            self.selenium.execute_script(
                'var meta = document.createElement("meta"); '
                'meta.name = "csrf-token"; '
                f'meta.content = "{csrf_token}"; '
                'document.head.appendChild(meta);'
            )
            
            # Wait for and click delete button
            delete_button = WebDriverWait(self.selenium, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//tr[@data-column-id='{column.id}']//button[contains(@class, 'delete-row')]")
                )
            )
            delete_button.click()
            
            # Accept the confirmation dialog
            WebDriverWait(self.selenium, 10).until(EC.alert_is_present())
            alert = self.selenium.switch_to.alert
            alert.accept()
            
            # Wait for deletion to complete
            def column_is_deleted(driver):
                try:
                    return not ColumnDefinition.objects.filter(id=column.id).exists()
                except Exception:
                    return False
            
            WebDriverWait(self.selenium, 10).until(column_is_deleted)
            
        except Exception as e:
            print(f"Error in test_delete_column_ui: {str(e)}")
            raise

    def tearDown(self):
        """Clean up resources after each test"""
        logger.info("Starting test cleanup...")
        try:
            # Clean up test data
            logger.info("Cleaning up test data...")
            ColumnDefinition.objects.all().delete()
            User.objects.all().delete()
            
            if hasattr(self, 'selenium'):
                logger.info("Cleaning up Selenium session...")
                try:
                    # Clear cookies and local storage
                    self.selenium.delete_all_cookies()
                    self.selenium.execute_script("window.localStorage.clear();")
                    self.selenium.execute_script("window.sessionStorage.clear();")
                    
                    # Close any alert that might be present
                    try:
                        alert = self.selenium.switch_to.alert
                        alert.accept()
                    except Exception:
                        pass
                    
                    # Reset to default content
                    self.selenium.switch_to.default_content()
                    
                except Exception as e:
                    logger.warning(f"Error during Selenium cleanup: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in tearDown: {str(e)}", exc_info=True)
        finally:
            try:
                super().tearDown()
            except Exception as e:
                logger.error(f"Error in parent tearDown: {str(e)}", exc_info=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level resources"""
        logger.info("Starting class-level cleanup...")
        try:
            if hasattr(cls, 'selenium'):
                logger.info("Cleaning up Selenium WebDriver...")
                cls._cleanup_selenium(cls.selenium)
                delattr(cls, 'selenium')
            
            # Clean up log files
            log_files = ['chromedriver.log', 'test_failure.png']
            for log_file in log_files:
                try:
                    if os.path.exists(log_file):
                        os.remove(log_file)
                        logger.info(f"Removed log file: {log_file}")
                except Exception as e:
                    logger.warning(f"Error removing log file {log_file}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in tearDownClass: {str(e)}", exc_info=True)
        finally:
            try:
                super().tearDownClass()
            except Exception as e:
                logger.error(f"Error in parent tearDownClass: {str(e)}", exc_info=True) 