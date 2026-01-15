#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}! $1${NC}"
}

load_env() {
    local env_file="$SCRIPT_DIR/.env"
    if [[ -f "$env_file" ]]; then
        print_success "Loading environment variables from .env"
        set -a
        source "$env_file"
        set +a
        
        # Verify signing environment variables
        if [[ -n "$APPLE_ID" && -n "$APPLE_APP_SPECIFIC_PASSWORD" && -n "$APPLE_TEAM_ID" ]]; then
            print_success "Apple signing credentials loaded (APPLE_TEAM_ID=$APPLE_TEAM_ID)"
        else
            print_warning "Apple signing credentials not complete in .env"
            print_warning "App will be signed but NOT notarized"
        fi
    else
        print_warning ".env file not found, skipping environment setup"
    fi
}

detect_platform() {
    case "$(uname -s)" in
        Darwin*)
            if [[ "$(uname -m)" == "arm64" ]]; then
                echo "mac-arm64"
            else
                echo "mac-x64"
            fi
            ;;
        Linux*)
            echo "linux"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            echo "win"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

check_dependencies() {
    print_header "Checking Dependencies"

    local missing=0

    if command -v python3 &> /dev/null; then
        print_success "Python3: $(python3 --version)"
    else
        print_error "Python3 not found"
        missing=1
    fi

    if command -v pip &> /dev/null || command -v pip3 &> /dev/null; then
        print_success "pip: $(pip3 --version 2>/dev/null || pip --version)"
    else
        print_error "pip not found"
        missing=1
    fi

    if command -v node &> /dev/null; then
        print_success "Node.js: $(node --version)"
    else
        print_error "Node.js not found"
        missing=1
    fi

    if command -v npm &> /dev/null; then
        print_success "npm: $(npm --version)"
    else
        print_error "npm not found"
        missing=1
    fi

    if [[ $missing -eq 1 ]]; then
        print_error "Missing dependencies. Please install them first."
        exit 1
    fi
}

setup_venv() {
    cd "$BACKEND_DIR"

    if [[ ! -d ".venv" ]]; then
        print_warning ".venv not found, creating..."
        python3 -m venv .venv
    fi

    if [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
    elif [[ -f ".venv/Scripts/activate" ]]; then
        source .venv/Scripts/activate
    else
        print_error "Failed to find .venv activate script"
        exit 1
    fi

    print_success "Using venv: $(which python)"
}

build_backend() {
    print_header "Building Backend with PyInstaller"

    cd "$BACKEND_DIR"

    setup_venv

    if ! command -v pyinstaller &> /dev/null; then
        print_warning "PyInstaller not found, installing..."
        pip install pyinstaller
    fi

    # Clean previous build artifacts to ensure fresh build
    print_success "Cleaning previous build artifacts..."
    rm -rf dist build __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

    print_success "Installing backend dependencies (force reinstall)..."
    pip install . --force-reinstall --no-deps
    pip install .

    print_success "Running PyInstaller..."
    pyinstaller nemori-backend.spec --clean --noconfirm

    local platform=$(detect_platform)

    # Set executable permissions on Unix systems
    if [[ "$platform" != "win" ]]; then
        chmod +x "$BACKEND_DIR/dist/nemori-backend/nemori-backend"
    fi

    print_success "Backend built: $BACKEND_DIR/dist/nemori-backend/"

    deactivate 2>/dev/null || true

    cd "$SCRIPT_DIR"
}

build_frontend() {
    local target=$1

    print_header "Building Frontend for $target"

    # Load environment variables for signing/notarization
    load_env

    cd "$FRONTEND_DIR"

    if [[ ! -d "node_modules" ]]; then
        print_warning "node_modules not found, installing..."
        npm install
    fi

    print_success "Building Electron app..."

    case "$target" in
        mac)
            npm run build && npx electron-builder --mac --publish never
            ;;
        mac-x64)
            npm run build && npx electron-builder --mac --x64 --publish never
            ;;
        mac-arm64)
            npm run build && npx electron-builder --mac --arm64 --publish never
            ;;
        win)
            npm run build && npx electron-builder --win --publish never
            ;;
        linux)
            npm run build && npx electron-builder --linux --publish never
            ;;
        *)
            print_error "Unknown target: $target"
            exit 1
            ;;
    esac

    print_success "Frontend built: $FRONTEND_DIR/dist/"

    cd "$SCRIPT_DIR"
}

build_all() {
    local platform=$(detect_platform)
    local target

    case "$platform" in
        mac-arm64)
            target="mac-arm64"
            ;;
        mac-x64)
            target="mac-x64"
            ;;
        win)
            target="win"
            ;;
        linux)
            target="linux"
            ;;
        *)
            print_error "Unknown platform"
            exit 1
            ;;
    esac

    build_backend
    build_frontend "$target"

    print_header "Build Complete!"
    echo -e "Backend: ${GREEN}$BACKEND_DIR/dist/nemori-backend/${NC}"
    echo -e "Frontend: ${GREEN}$FRONTEND_DIR/dist/${NC}"
}

clean() {
    print_header "Cleaning Build Artifacts"

    rm -rf "$BACKEND_DIR/dist"
    rm -rf "$BACKEND_DIR/build"
    rm -rf "$FRONTEND_DIR/dist"
    rm -rf "$FRONTEND_DIR/out"

    print_success "Cleaned all build artifacts"
}

show_menu() {
    local platform=$(detect_platform)

    echo -e "\n${BLUE}Nemori Desktop Build Script${NC}"
    echo -e "Detected platform: ${GREEN}$platform${NC}\n"
    echo "1) Build all (backend + frontend for current platform)"
    echo "2) Build backend only"
    echo "3) Build frontend only"
    echo "4) Clean build artifacts"
    echo "5) Check dependencies"
    echo "6) Exit"
    echo ""
}

select_frontend_target() {
    local platform=$(detect_platform)

    echo -e "\nSelect frontend target:"

    case "$platform" in
        mac-arm64|mac-x64)
            echo "1) macOS (universal)"
            echo "2) macOS x64"
            echo "3) macOS arm64"
            ;;
        win)
            echo "1) Windows x64"
            ;;
        linux)
            echo "1) Linux"
            ;;
    esac

    echo ""
    read -p "Enter choice: " frontend_choice

    case "$platform" in
        mac-arm64|mac-x64)
            case "$frontend_choice" in
                1) echo "mac" ;;
                2) echo "mac-x64" ;;
                3) echo "mac-arm64" ;;
                *) echo "mac" ;;
            esac
            ;;
        win)
            echo "win"
            ;;
        linux)
            echo "linux"
            ;;
    esac
}

main() {
    if [[ $# -gt 0 ]]; then
        case "$1" in
            --all)
                check_dependencies
                build_all
                ;;
            --backend)
                check_dependencies
                build_backend
                ;;
            --frontend)
                check_dependencies
                build_frontend "${2:-$(detect_platform | sed 's/-.*$//')}"
                ;;
            --clean)
                clean
                ;;
            --help)
                echo "Usage: $0 [option]"
                echo "Options:"
                echo "  --all       Build everything for current platform"
                echo "  --backend   Build backend only"
                echo "  --frontend  Build frontend only"
                echo "  --clean     Clean build artifacts"
                echo "  --help      Show this help"
                echo ""
                echo "Run without options for interactive mode."
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
        exit 0
    fi

    while true; do
        show_menu
        read -p "Enter choice [1-6]: " choice

        case "$choice" in
            1)
                check_dependencies
                build_all
                ;;
            2)
                check_dependencies
                build_backend
                ;;
            3)
                check_dependencies
                local target=$(select_frontend_target)
                build_frontend "$target"
                ;;
            4)
                clean
                ;;
            5)
                check_dependencies
                ;;
            6)
                echo -e "\n${GREEN}Goodbye!${NC}\n"
                exit 0
                ;;
            *)
                print_error "Invalid choice"
                ;;
        esac
    done
}

main "$@"
