# Create main project directory structure
$directories = @(
    ".\core",
    ".\core\static\css",
    ".\core\templates",
    ".\core\services",
    ".\core\media\pdfs",
    ".\pdf_processor"
)

foreach ($dir in $directories) {
    New-Item -ItemType Directory -Path $dir -Force
}

# Create necessary Python files
$pythonFiles = @(
    ".\core\__init__.py",
    ".\core\models.py",
    ".\core\views.py",
    ".\core\forms.py",
    ".\core\urls.py",
    ".\core\services\__init__.py",
    ".\core\services\llm_service.py",
    ".\core\services\pdf_service.py",
    ".\pdf_processor\__init__.py",
    ".\pdf_processor\settings.py",
    ".\pdf_processor\urls.py",
    ".\pdf_processor\wsgi.py",
    ".\pdf_processor\asgi.py",
    ".\manage.py"
)

foreach ($file in $pythonFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Create template files
$templateFiles = @(
    ".\core\templates\base.html",
    ".\core\templates\processor.html",
    ".\core\templates\results.html"
)

foreach ($file in $templateFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Create static files
$staticFiles = @(
    ".\core\static\css\styles.css"
)

foreach ($file in $staticFiles) {
    New-Item -ItemType File -Path $file -Force
}

# Create .env file
$envContent = @"
SECRET_KEY=your_django_secret_key_here
DEBUG=True
GEMINI_API_KEY=your_gemini_api_key_here
"@

Set-Content -Path ".\pdf_processor\.env" -Value $envContent

# Create .gitignore file
$gitignoreContent = @"
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
*.egg-info/
.installed.cfg
*.egg

# Django
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal
media/
staticfiles/

# Environment variables
.env

# VS Code
.vscode/
*.code-workspace

# Windows
Thumbs.db
ehthumbs.db
Desktop.ini

# PDFs
core/media/pdfs/*
!core/media/pdfs/.gitkeep
"@

Set-Content -Path ".\.gitignore" -Value $gitignoreContent

# Create empty .gitkeep file in pdfs directory
New-Item -ItemType File -Path ".\core\media\pdfs\.gitkeep" -Force

# Create requirements.txt
$requirementsContent = @"
django>=4.2.0
google-generativeai>=0.3.0
pandas>=2.0.0
python-dotenv>=1.0.0
django-crispy-forms>=2.0
whitenoise>=6.0.0
"@

Set-Content -Path ".\requirements.txt" -Value $requirementsContent

Write-Host "Project structure created successfully!"