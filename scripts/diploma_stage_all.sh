#!/bin/bash
# Diploma Stage Pipeline - Batch Execution
# Runs Stage 1 (analysis), Stage 2 (verification), optionally Stage 3 (writing)

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STAGE_ALL=${1:-all}           # [1|2|3|all]
MODE=${2:-normal}              # [normal|update|force]
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_DIR=".planning/diploma_runs"
RUN_LOG="$LOG_DIR/run_$TIMESTAMP.log"

# Directories
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIPLOMA_DIR="$PROJECT_ROOT/diploma"
SCRIPT_DIR="$PROJECT_ROOT/scripts"

mkdir -p "$LOG_DIR"

# Functions
log() {
    local level=$1
    shift
    local msg="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${!level}[$timestamp] $msg${NC}" | tee -a "$RUN_LOG"
}

log_separator() {
    echo "" | tee -a "$RUN_LOG"
    echo -e "${BLUE}===============================================${NC}" | tee -a "$RUN_LOG"
    echo ""
}

print_header() {
    log BLUE "🔄 $1"
}

print_success() {
    log GREEN "✅ $1"
}

print_warning() {
    log YELLOW "⚠️  $1"
}

print_error() {
    log RED "❌ $1"
}

# Validation
validate_environment() {
    print_header "Validating environment..."

    if [[ ! -d "$DIPLOMA_DIR" ]]; then
        print_error "diploma/ directory not found: $DIPLOMA_DIR"
        exit 1
    fi

    if [[ ! -f "$DIPLOMA_DIR/Diploma.md" ]]; then
        print_error "Diploma.md not found"
        exit 1
    fi

    print_success "Environment validated"
}

# Stage 1: Diploma → Architecture Analysis
run_stage_1() {
    print_header "STAGE 1: Diploma → Architecture Analysis"
    log BLUE "Running: 01_diploma_to_architecture.md"
    log BLUE "Output: diploma/project-analysis/"
    log YELLOW "Note: This stage requires manual execution via Claude prompt"
    log YELLOW "File: diploma/01_diploma_to_architecture.md"

    echo ""
    log YELLOW "Next steps:"
    log YELLOW "1. Copy diploma/01_diploma_to_architecture.md content"
    log YELLOW "2. Paste into Claude Code"
    log YELLOW "3. Run with PROJECT_ROOT context"
    log YELLOW "4. Save output to diploma/project-analysis/"

    # In automation: would trigger Claude API or write to file
    # For now, informational only

    print_success "Stage 1 instructions displayed"
}

# Stage 2: Code → Diploma Verification
run_stage_2() {
    print_header "STAGE 2: Code → Diploma Verification"
    log BLUE "Running: 02_code_to_diploma_verification.md"
    log BLUE "Input: diploma/project-analysis/ + graphify-out/"
    log BLUE "Output: diploma/project-verification/"
    log YELLOW "Note: This stage requires manual execution via Claude prompt"
    log YELLOW "File: diploma/02_code_to_diploma_verification.md"

    echo ""
    log YELLOW "Next steps:"
    log YELLOW "1. Ensure graphify-out/ is up to date: /graphify System/ --update"
    log YELLOW "2. Copy diploma/02_code_to_diploma_verification.md content"
    log YELLOW "3. Paste into Claude Code"
    log YELLOW "4. Save output to diploma/project-verification/"

    # Add timestamps to output after completion
    if [[ -d "$DIPLOMA_DIR/project-verification/by-criterion" ]]; then
        log BLUE "Adding timestamps to Stage 2 output..."
        powershell -ExecutionPolicy Bypass -File "$SCRIPT_DIR/add_stage_timestamps.ps1" -Stage 2 -Force
        print_success "Stage 2 timestamps updated"
    fi

    print_success "Stage 2 instructions displayed"
}

# Stage 3: Writing Chapter 3
run_stage_3() {
    print_header "STAGE 3: Writing Chapter 3"
    log BLUE "Running: 03_write_chapter3.md"
    log BLUE "Input: diploma/project-verification/"
    log BLUE "Output: diploma/chapter-3/"
    log YELLOW "Note: This stage requires manual execution via Claude prompt"
    log YELLOW "File: diploma/03_write_chapter3.md"

    echo ""
    log YELLOW "Next steps:"
    log YELLOW "1. Copy diploma/03_write_chapter3.md content"
    log YELLOW "2. Paste into Claude Code with project context"
    log YELLOW "3. Follow IMRAD template from CHAPTER3_PROBLEMS_AND_ROADMAP.md"
    log YELLOW "4. Save sections to diploma/chapter-3/"

    print_success "Stage 3 instructions displayed"
}

# Validation after runs
validate_stage_outputs() {
    print_header "Validating Stage outputs..."

    # Check Stage 1
    if [[ -d "$DIPLOMA_DIR/project-analysis" ]]; then
        local file_count=$(find "$DIPLOMA_DIR/project-analysis" -name "*.md" | wc -l)
        if [[ $file_count -gt 0 ]]; then
            print_success "Stage 1 output found: $file_count files"
        else
            print_warning "Stage 1 output directory exists but is empty"
        fi
    fi

    # Check Stage 2
    if [[ -d "$DIPLOMA_DIR/project-verification/by-criterion" ]]; then
        local file_count=$(ls -1 "$DIPLOMA_DIR/project-verification/by-criterion/crit_*.md" 2>/dev/null | wc -l)
        if [[ $file_count -eq 8 ]]; then
            print_success "Stage 2 criterion files complete: 8/8"
        else
            print_warning "Stage 2 criterion files: $file_count/8"
        fi
    fi
}

# Summary report
print_summary() {
    log_separator
    print_header "PIPELINE EXECUTION SUMMARY"

    log GREEN "Timestamp: $TIMESTAMP"
    log GREEN "Mode: $MODE"
    log GREEN "Log saved to: $RUN_LOG"

    echo ""
    log BLUE "What's next:"
    log BLUE "1. Execute stages via Claude Code (manual)"
    log BLUE "2. After Stage 1: run /graphify System/ --update"
    log BLUE "3. After Stage 2: validate output files"
    log BLUE "4. After Stage 3: commit changes to diploma/chapter-3/"

    log_separator
}

# Main execution
main() {
    {
        log BLUE "DIPLOMA STAGE PIPELINE"
        log BLUE "Stage: $STAGE_ALL | Mode: $MODE | Time: $TIMESTAMP"
        log_separator

        validate_environment
        log_separator

        case $STAGE_ALL in
            1|all)
                run_stage_1
                [[ $STAGE_ALL == "1" ]] && log_separator
                ;& # Fall through for 'all'
            2|all)
                [[ $STAGE_ALL == "all" ]] && log_separator
                run_stage_2
                [[ $STAGE_ALL == "2" ]] && log_separator
                ;& # Fall through for 'all'
            3|all)
                [[ $STAGE_ALL == "all" ]] && log_separator
                run_stage_3
                log_separator
                ;;
            *)
                print_error "Unknown stage: $STAGE_ALL"
                echo "Usage: $0 [1|2|3|all] [normal|update|force]"
                exit 1
                ;;
        esac

        validate_stage_outputs
        print_summary

    } | tee "$RUN_LOG"

    print_success "Pipeline execution log: $RUN_LOG"
}

# Run
main "$@"
