#!/bin/bash
# Diploma Pipeline Stage Output Validator
# Verifies Stage 1, Stage 2, and optionally Stage 3 outputs for integrity and completeness

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
VALIDATE_STAGE=${1:-all}          # [1|2|3|all]
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIPLOMA_DIR="$PROJECT_ROOT/diploma"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
REPORT_DIR=".planning/validation_reports"
REPORT_FILE="$REPORT_DIR/validation_$TIMESTAMP.json"

mkdir -p "$REPORT_DIR"

# State tracking
declare -a ERRORS=()
declare -a WARNINGS=()
declare -a PASSES=()
VALIDATION_RESULT="PASS"

# Helper functions
log_pass() {
    local msg="$1"
    echo -e "${GREEN}✅ $msg${NC}"
    PASSES+=("$msg")
}

log_warn() {
    local msg="$1"
    echo -e "${YELLOW}⚠️  $msg${NC}"
    WARNINGS+=("$msg")
    VALIDATION_RESULT="WARN"
}

log_error() {
    local msg="$1"
    echo -e "${RED}❌ $msg${NC}"
    ERRORS+=("$msg")
    VALIDATION_RESULT="FAIL"
}

log_info() {
    local msg="$1"
    echo -e "${CYAN}ℹ️  $msg${NC}"
}

# Check if file has required metadata header
check_metadata_header() {
    local filepath="$1"
    local stage_num="$2"

    if [[ ! -f "$filepath" ]]; then
        return 1  # File doesn't exist
    fi

    # Look for GENERATED: timestamp in comment
    if head -10 "$filepath" | grep -q "GENERATED:"; then
        return 0  # Has metadata
    fi

    return 1  # No metadata found
}

# Parse metadata from file
get_metadata() {
    local filepath="$1"

    if [[ -f "$filepath" ]]; then
        # Extract GENERATED timestamp
        grep "GENERATED:" "$filepath" | sed 's/.*GENERATED: //' | sed 's/ STAGE.*//' || echo "UNKNOWN"
    else
        echo "FILE_NOT_FOUND"
    fi
}

# Check if file is valid markdown
check_valid_markdown() {
    local filepath="$1"

    if [[ ! -f "$filepath" ]]; then
        return 1
    fi

    # Basic checks: non-empty, has some structure
    local lines=$(wc -l < "$filepath")
    if [[ $lines -lt 3 ]]; then
        return 1
    fi

    # Check for heading markers
    if grep -q "^#" "$filepath"; then
        return 0
    fi

    return 1
}

# Stage 1 Validation
validate_stage_1() {
    echo ""
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${BLUE}STAGE 1 VALIDATION${NC}"
    echo -e "${BLUE}===========================================${NC}"

    local expected_files=(
        "ch01/concepts/subjectivity_framework.md"
        "ch02/concepts/case_studies.md"
        "ch02/concepts/evaluation_criteria_extracted.md"
        "ch03/architecture/system_map.md"
        "ch03/identity/identity_model.md"
        "ch03/interaction/interaction_model.md"
        "ch03/memory/memory_model.md"
        "ch03/requirements/system_requirements.md"
        "ch03/runtime/runtime_model.md"
        "synthesis/code_community_labels.md"
        "synthesis/criteria_to_code.md"
        "synthesis/cross_graph_map.md"
        "synthesis/master_concepts.md"
    )

    local found_count=0
    local valid_count=0
    local metadata_count=0

    for file in "${expected_files[@]}"; do
        local full_path="$DIPLOMA_DIR/project-analysis/$file"

        if [[ -f "$full_path" ]]; then
            found_count=$((found_count + 1))

            if check_valid_markdown "$full_path"; then
                valid_count=$((valid_count + 1))

                if check_metadata_header "$full_path" "1"; then
                    metadata_count=$((metadata_count + 1))
                    local gen_time=$(get_metadata "$full_path")
                    log_pass "Found with metadata: $(basename $file) (generated: $gen_time)"
                else
                    log_warn "Found but missing metadata header: $(basename $file)"
                fi
            else
                log_error "Found but invalid markdown: $file"
            fi
        else
            log_error "Missing required file: $file"
        fi
    done

    echo ""
    echo "Stage 1 Summary:"
    echo "  Files found: $found_count/${#expected_files[@]}"
    echo "  Valid markdown: $valid_count/${#expected_files[@]}"
    echo "  With metadata: $metadata_count/${#expected_files[@]}"

    if [[ $found_count -eq ${#expected_files[@]} ]] && [[ $valid_count -eq ${#expected_files[@]} ]]; then
        log_pass "Stage 1 output complete"
    else
        log_warn "Stage 1 output incomplete or invalid"
    fi
}

# Stage 2 Validation
validate_stage_2() {
    echo ""
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${BLUE}STAGE 2 VALIDATION${NC}"
    echo -e "${BLUE}===========================================${NC}"

    # Criterion files
    local criterion_files=(
        "crit_01_autonomy.md"
        "crit_02_agency.md"
        "crit_03_identity.md"
        "crit_04_normativity.md"
        "crit_05_temporal.md"
        "crit_06_interaction.md"
        "crit_07_embodiment.md"
        "crit_08_emergence.md"
    )

    local section_files=(
        "3.1_concept.md"
        "3.2_application.md"
        "3.3_installation.md"
        "3.4_testing.md"
    )

    # Check criteria
    echo ""
    log_info "Checking criterion files (by-criterion/)..."
    local crit_found=0
    local crit_valid=0
    local crit_metadata=0

    for file in "${criterion_files[@]}"; do
        local full_path="$DIPLOMA_DIR/project-verification/by-criterion/$file"

        if [[ -f "$full_path" ]]; then
            crit_found=$((crit_found + 1))

            if check_valid_markdown "$full_path"; then
                crit_valid=$((crit_valid + 1))

                if check_metadata_header "$full_path" "2"; then
                    crit_metadata=$((crit_metadata + 1))
                    local gen_time=$(get_metadata "$full_path")
                    log_pass "Criterion file valid: $(basename $file) (generated: $gen_time)"
                else
                    log_warn "Criterion file missing metadata: $(basename $file)"
                fi
            else
                log_error "Criterion file invalid: $file"
            fi
        else
            log_error "Missing criterion file: $file"
        fi
    done

    echo ""
    echo "Criterion Summary: $crit_found/8 found, $crit_valid/8 valid, $crit_metadata/8 with metadata"

    # Check sections
    echo ""
    log_info "Checking section files (by-section/)..."
    local sec_found=0
    local sec_valid=0
    local sec_metadata=0

    for file in "${section_files[@]}"; do
        local full_path="$DIPLOMA_DIR/project-verification/by-section/$file"

        if [[ -f "$full_path" ]]; then
            sec_found=$((sec_found + 1))

            if check_valid_markdown "$full_path"; then
                sec_valid=$((sec_valid + 1))

                if check_metadata_header "$full_path" "2"; then
                    sec_metadata=$((sec_metadata + 1))
                    local gen_time=$(get_metadata "$full_path")
                    log_pass "Section file valid: $(basename $file) (generated: $gen_time)"
                else
                    log_warn "Section file missing metadata: $(basename $file)"
                fi
            else
                log_error "Section file invalid: $file"
            fi
        else
            log_error "Missing section file: $file"
        fi
    done

    echo ""
    echo "Section Summary: $sec_found/4 found, $sec_valid/4 valid, $sec_metadata/4 with metadata"

    # Check blueprint
    echo ""
    log_info "Checking blueprint file..."
    local blueprint_path="$DIPLOMA_DIR/project-verification/chapter3_materials/final_chapter_blueprint.md"
    if [[ -f "$blueprint_path" ]]; then
        if check_valid_markdown "$blueprint_path"; then
            if check_metadata_header "$blueprint_path" "2"; then
                log_pass "Blueprint file valid and has metadata"
            else
                log_warn "Blueprint file valid but missing metadata"
            fi
        else
            log_error "Blueprint file invalid markdown"
        fi
    else
        log_error "Missing blueprint file"
    fi

    # Summary
    local total_stage2_expected=13  # 8 criteria + 4 sections + 1 blueprint
    local blueprint_exists=0
    [[ -f "$blueprint_path" ]] && blueprint_exists=1
    local total_stage2_found=$((crit_found + sec_found + blueprint_exists))

    if [[ $crit_found -eq 8 ]] && [[ $sec_found -eq 4 ]] && [[ -f "$blueprint_path" ]]; then
        log_pass "Stage 2 output complete (13/13 files)"
    else
        log_warn "Stage 2 output incomplete ($total_stage2_found/$total_stage2_expected files)"
    fi
}

# Stage 3 Validation (optional)
validate_stage_3() {
    echo ""
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${BLUE}STAGE 3 VALIDATION${NC}"
    echo -e "${BLUE}===========================================${NC}"

    if [[ ! -d "$DIPLOMA_DIR/chapter-3" ]]; then
        log_warn "Stage 3 directory does not exist yet (expected for incomplete pipeline)"
        return
    fi

    local chapter3_files=(
        "3.1_Introduction.md"
        "3.2_Methods.md"
        "3.3_Results.md"
        "3.4_Analysis.md"
    )

    local found=0
    for file in "${chapter3_files[@]}"; do
        local full_path="$DIPLOMA_DIR/chapter-3/$file"
        if [[ -f "$full_path" ]]; then
            found=$((found + 1))
            if check_valid_markdown "$full_path"; then
                log_pass "Chapter section found: $(basename $file)"
            else
                log_error "Chapter section invalid markdown: $file"
            fi
        fi
    done

    if [[ $found -eq 0 ]]; then
        log_info "Stage 3: No chapter files written yet (expected during active development)"
    else
        echo "Stage 3 Summary: $found/4 sections written"
    fi
}

# Generate JSON report
generate_report() {
    cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "validation_stage": "$VALIDATE_STAGE",
  "result": "$VALIDATION_RESULT",
  "passes": $(printf '%s\n' "${PASSES[@]}" | jq -R . | jq -s .),
  "warnings": $(printf '%s\n' "${WARNINGS[@]}" | jq -R . | jq -s .),
  "errors": $(printf '%s\n' "${ERRORS[@]}" | jq -R . | jq -s .),
  "summary": {
    "total_passes": ${#PASSES[@]},
    "total_warnings": ${#WARNINGS[@]},
    "total_errors": ${#ERRORS[@]}
  }
}
EOF
}

# Main
main() {
    echo -e "${BLUE}=========================================================${NC}"
    echo -e "${BLUE}DIPLOMA PIPELINE STAGE OUTPUT VALIDATOR${NC}"
    echo -e "${BLUE}=========================================================${NC}"
    echo ""
    echo "Timestamp: $TIMESTAMP"
    echo "Stage(s): $VALIDATE_STAGE"
    echo "Project: $PROJECT_ROOT"
    echo ""

    case $VALIDATE_STAGE in
        1|all)
            validate_stage_1
            [[ $VALIDATE_STAGE == "1" ]] && skip_rest=true
            ;& # Fall through for 'all'
        2|all)
            validate_stage_2
            [[ $VALIDATE_STAGE == "2" ]] && skip_rest=true
            ;& # Fall through for 'all'
        3|all)
            validate_stage_3
            ;;
        *)
            log_error "Unknown stage: $VALIDATE_STAGE"
            echo "Usage: $0 [1|2|3|all]"
            exit 1
            ;;
    esac

    # Final summary
    echo ""
    echo -e "${BLUE}=========================================================${NC}"
    echo -e "${BLUE}VALIDATION SUMMARY${NC}"
    echo -e "${BLUE}=========================================================${NC}"
    echo ""
    echo "Passes:   ${#PASSES[@]}"
    echo "Warnings: ${#WARNINGS[@]}"
    echo "Errors:   ${#ERRORS[@]}"
    echo ""

    if [[ ${#ERRORS[@]} -gt 0 ]]; then
        echo -e "${RED}Result: FAIL - $VALIDATION_RESULT${NC}"
        echo ""
        echo "Errors:"
        printf '%s\n' "${ERRORS[@]}" | sed 's/^/  - /'
    elif [[ ${#WARNINGS[@]} -gt 0 ]]; then
        echo -e "${YELLOW}Result: WARN - $VALIDATION_RESULT${NC}"
        echo ""
        echo "Warnings:"
        printf '%s\n' "${WARNINGS[@]}" | sed 's/^/  - /'
    else
        echo -e "${GREEN}Result: PASS - All validations passed${NC}"
    fi

    echo ""
    echo "Report saved: $REPORT_FILE"

    # Generate JSON report
    generate_report

    # Exit with appropriate code
    [[ $VALIDATION_RESULT == "FAIL" ]] && exit 1
    exit 0
}

# Run
main "$@"
