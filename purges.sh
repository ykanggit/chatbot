#!/bin/bash

# Kotaemon Project Cleanup Script
# This script removes automatically generated files and directories
# to restore the project to source code mode.

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global counters for summary
TOTAL_FILES_DELETED=0
TOTAL_DIRECTORIES_DELETED=0

# Parse command line arguments
CLEAN_EVERYTHING=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --everything)
            CLEAN_EVERYTHING=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --everything    Remove ALL files including user data (dangerous!)"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "Default behavior: Preserves user data, removes only development artifacts"
            echo "Use --everything to remove user data as well"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to safely remove files/directories
safe_remove() {
    local target="$1"
    local description="$2"
    
    if [ -e "$target" ]; then
        print_status "Removing $description: $target"
        rm -rf "$target"
        print_success "Removed $description"
        
        # Count based on whether it's a file or directory
        if [ -d "$target" ]; then
            ((TOTAL_DIRECTORIES_DELETED++))
        else
            ((TOTAL_FILES_DELETED++))
        fi
    else
        print_status "Skipping $description (not found): $target"
    fi
}

# Function to find and remove files by pattern
find_and_remove() {
    local pattern="$1"
    local description="$2"
    
    print_status "Searching for $description..."
    local count=0
    
    while IFS= read -r -d '' file; do
        if [ -e "$file" ]; then
            print_status "Removing: $file"
            rm -rf "$file"
            ((count++))
            ((TOTAL_FILES_DELETED++))
        fi
    done < <(find . -name "$pattern" -print0 2>/dev/null)
    
    if [ $count -gt 0 ]; then
        print_success "Removed $count $description"
    else
        print_status "No $description found"
    fi
}

# Function to find and remove directories by pattern
find_and_remove_dirs() {
    local pattern="$1"
    local description="$2"
    
    print_status "Searching for $description directories..."
    local count=0
    
    while IFS= read -r -d '' dir; do
        if [ -d "$dir" ]; then
            print_status "Removing directory: $dir"
            rm -rf "$dir"
            ((count++))
            ((TOTAL_DIRECTORIES_DELETED++))
        fi
    done < <(find . -type d -name "$pattern" -print0 2>/dev/null)
    
    if [ $count -gt 0 ]; then
        print_success "Removed $count $description directories"
    else
        print_status "No $description directories found"
    fi
}

# Function to find and remove files by multiple patterns
find_and_remove_files() {
    local patterns=("$@")
    local description="$1"
    
    print_status "Searching for $description files..."
    local count=0
    
    for pattern in "${patterns[@]}"; do
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                print_status "Removing file: $file"
                rm -f "$file"
                ((count++))
                ((TOTAL_FILES_DELETED++))
            fi
        done < <(find . -name "$pattern" -type f -print0 2>/dev/null)
    done
    
    if [ $count -gt 0 ]; then
        print_success "Removed $count $description files"
    else
        print_status "No $description files found"
    fi
}

echo "=========================================="
echo "    Kotaemon Project Cleanup Script"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "app.py" ] || [ ! -f "flowsettings.py" ]; then
    print_error "This script must be run from the Kotaemon project root directory"
    exit 1
fi

# Show mode and get confirmation
if [ "$CLEAN_EVERYTHING" = true ]; then
    echo ""
    print_warning "⚠️  WARNING: Running in --everything mode!"
    print_warning "   This will delete ALL user data including:"
    print_warning "   - Uploaded documents and files"
    print_warning "   - Chat conversations and history"
    print_warning "   - User settings and configurations"
    print_warning "   - Application data and databases"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " confirm
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_status "Cleanup cancelled by user"
        exit 0
    fi
else
    echo ""
    print_status "Running in safe mode - user data will be preserved"
    print_status "Use --everything flag to also remove user data"
    echo ""
fi

print_status "Starting cleanup process..."

# 1. Remove application data directories (only in --everything mode)
if [ "$CLEAN_EVERYTHING" = true ]; then
    print_status "Step 1: Removing application data directories (user data)"
    safe_remove "ktem_app_data" "application data directory"
    safe_remove "gradio_tmp" "Gradio temporary files"
    safe_remove "storage" "storage directory"
else
    print_status "Step 1: Skipping application data directories (preserving user data)"
    print_status "   - ktem_app_data/ (user conversations, settings, uploaded files)"
    print_status "   - gradio_tmp/ (temporary web interface files)"
    print_status "   - storage/ (document storage and vector databases)"
fi

# 2. Remove installation directories
print_status "Step 2: Removing installation directories"
safe_remove "install_dir" "installation directory"
safe_remove "doc_env" "document environment directory"

# 3. Remove Python cache directories
print_status "Step 3: Removing Python cache directories"
find_and_remove_dirs "__pycache__" "Python cache"

# 4. Remove Python compiled files
print_status "Step 4: Removing Python compiled files"
find_and_remove_files "*.pyc" "*.pyo" "*.pyd" "Python compiled files"

# 5. Remove build artifacts
print_status "Step 5: Removing build artifacts"
safe_remove "build" "build directory"
safe_remove "dist" "dist directory"
find_and_remove_dirs "*.egg-info" "Python egg info"
safe_remove ".eggs" "eggs directory"

# 6. Remove test artifacts
print_status "Step 6: Removing test artifacts"
safe_remove ".pytest_cache" "pytest cache"
safe_remove ".coverage" "coverage file"
safe_remove "htmlcov" "HTML coverage directory"
safe_remove ".tox" "tox directory"

# 7. Remove cache directories
print_status "Step 7: Removing cache directories"
safe_remove ".theflow" "theflow cache"
safe_remove ".ruff_cache" "ruff cache"
find_and_remove_dirs ".mypy_cache" "mypy cache"
safe_remove ".pytype" "pytype cache"
safe_remove ".pyre" "pyre cache"

# 8. Remove environment files (except .env.example)
print_status "Step 8: Removing environment files"
env_count=0
while IFS= read -r -d '' file; do
    if [ -f "$file" ]; then
        print_status "Removing environment file: $file"
        rm -f "$file"
        ((env_count++))
        ((TOTAL_FILES_DELETED++))
    fi
done < <(find . -name ".env" ! -name ".env.example" -print0 2>/dev/null)

if [ $env_count -gt 0 ]; then
    print_success "Removed $env_count environment files (preserved .env.example)"
else
    print_status "No environment files found (preserved .env.example)"
fi

# 9. Remove log files
print_status "Step 9: Removing log files"
find_and_remove_files "*.log" "log files"
safe_remove "logs" "logs directory"

# 10. Remove IDE files
print_status "Step 10: Removing IDE files"
safe_remove ".idea" "IntelliJ IDEA files"
safe_remove ".vscode" "VS Code files"
find_and_remove_files "*.swp" "*.swo" "Vim swap files"

# 11. Remove OS files
print_status "Step 11: Removing OS files"
find_and_remove_files ".DS_Store" "macOS files"
find_and_remove_files "Thumbs.db" "Windows files"

# 12. Remove temporary files
print_status "Step 12: Removing temporary files"
find_and_remove_files "*.tmp" "*.temp" "temporary files"

# 13. Remove conda/venv directories
print_status "Step 13: Removing virtual environment directories"
find_and_remove_dirs "venv" "Python virtual environment"
find_and_remove_dirs ".venv" "Python virtual environment"
find_and_remove_dirs "env" "Python environment"
find_and_remove_dirs "*install_dir*" "installation directories"

# 14. Remove mypy configuration files
print_status "Step 14: Removing mypy configuration files"
find_and_remove_files ".dmypy.json" "dmypy.json" "mypy configuration files"

# 15. Clean pip cache (optional)
if command -v pip &> /dev/null; then
    print_status "Step 15: Cleaning pip cache"
    pip cache purge 2>/dev/null || print_warning "Failed to clean pip cache"
fi

# 16. Clean conda cache (optional)
if command -v conda &> /dev/null; then
    print_status "Step 16: Cleaning conda cache"
    conda clean --all -y 2>/dev/null || print_warning "Failed to clean conda cache"
fi

echo ""
echo "=========================================="
print_success "Cleanup completed successfully!"
echo "=========================================="
echo ""

# Print summary
echo "📊 CLEANUP SUMMARY"
echo "=================="
if [ $TOTAL_FILES_DELETED -gt 0 ] || [ $TOTAL_DIRECTORIES_DELETED -gt 0 ]; then
    print_success "Total files deleted: $TOTAL_FILES_DELETED"
    print_success "Total directories deleted: $TOTAL_DIRECTORIES_DELETED"
    print_success "Total items removed: $((TOTAL_FILES_DELETED + TOTAL_DIRECTORIES_DELETED))"
else
    print_status "No files or directories were found to delete"
fi

# Show mode information
if [ "$CLEAN_EVERYTHING" = true ]; then
    print_warning "Mode: Complete cleanup (user data removed)"
else
    print_success "Mode: Safe cleanup (user data preserved)"
fi
echo "=================="
echo ""

print_status "The project has been restored to source code mode."
if [ "$CLEAN_EVERYTHING" = true ]; then
    print_status "All files including user data have been removed."
else
    print_status "Development artifacts removed, user data preserved."
fi
echo ""
print_status "To start fresh, you can now:"
print_status "1. Run the installation script: ./scripts/run_macos.sh (or run_linux.sh)"
print_status "2. Or install manually: pip install -e libs/kotaemon && pip install -e libs/ktem"
print_status "3. Or use Docker: docker build -t kotaemon ."
echo "" 