#!/usr/bin/env bash
set -euo pipefail
# Benchmark for APKMirror version filtering
generate_data() {
    local num_versions=50
    local i
    local v
    vers_list=""
    html_content="<html><body>"
    for ((i=1; i<=num_versions; i++)); do
        v="10.0.$i"
        vers_list+="$v"$'\n'
        if (( i % 2 == 0 )); then
            # Beta
            html_content+="<div><span class='ver'>$v</span> <span class='tag'>beta</span></div>"
            html_content+="Some random text around $v beta version..."
        else
            # Stable
            html_content+="<div><span class='ver'>$v</span></div>"
            html_content+="Some random text around $v version..."
        fi
        html_content+=$(printf 'x%.0s' {1..1000})
    done
    html_content+="</body></html>"
    vers_list="${vers_list%$'\n'}"
}

original_logic() {
    local vers="$1"
    local apkm_resp="$2"
    local __AAV__=false
    if [[ "$__AAV__" = false ]]; then
        local IFS=$'\n'
        vers=$(grep -iv "\(beta\|alpha\)" <<< "$vers")
        local v r_vers=()
        for v in "${vers[@]}"; do
            grep -iq "${v} \(beta\|alpha\)" <<< "$apkm_resp" || r_vers+=("$v")
        done
        echo "${r_vers[*]}"
    else
        echo "$vers"
    fi
}

corrected_loop_logic() {
    local vers="$1"
    local apkm_resp="$2"
    local __AAV__=false
    if [[ "$__AAV__" = false ]]; then
        local IFS=$'\n'
        vers=$(grep -iv "\(beta\|alpha\)" <<< "$vers")
        local v r_vers=()
        for v in $vers; do
            grep -iq "${v} \(beta\|alpha\)" <<< "$apkm_resp" || r_vers+=("$v")
        done
        echo "${r_vers[*]}"
    else
        echo "$vers"
    fi
}

optimized_logic() {
    local vers="$1"
    local apkm_resp="$2"
    local __AAV__=false
    if [[ "$__AAV__" = false ]]; then
        vers=$(grep -iv "\(beta\|alpha\)" <<< "$vers")
        if [[ -n "$vers" ]]; then
            local pattern
            # Escape dots
            pattern=$(echo "$vers" | sed 's/\./\\./g' | tr '\n' '|')
            pattern="${pattern%|}"

            # Debug: print pattern to stderr
            # echo "Pattern: $pattern" >&2

            local bad_vers
            # Use grep to find matches
            bad_vers=$(grep -Eoi "(${pattern})[[:space:]]+(beta|alpha)" <<< "$apkm_resp" | awk '{print tolower($1)}' | sort -u)

            # Debug: print bad_vers
            # echo "Bad vers: $bad_vers" >&2

            if [[ -n "$bad_vers" ]]; then
                vers=$(grep -vxFf <(echo "$bad_vers") <<< "$vers" || true)
            fi
        fi
        echo "$vers"
    else
        echo "$vers"
    fi
}

measure_time() {
    local start
    start=$(date +%s%N 2>/dev/null || date +%s)
    # Return start time
    echo "$start"
}

calc_duration() {
    local start=$1
    local end=$2
    # Simple duration calc (might be huge integer or small if %s)
    # Handle nanoseconds if present (length > 10)
    if [ ${#start} -gt 11 ]; then
        echo "$(( (end - start) / 1000000 )) ms"
    else
        echo "$(( end - start )) s"
    fi
}

run_benchmark() {
    local name="$1"
    local cmd="$2"
    local vers_in="$3"
    local html_in="$4"

    local start=$(measure_time)
    local output
    output=$(eval "$cmd" "\"$vers_in\"" "\"$html_in\"")
    local end=$(measure_time)

    local duration=$(calc_duration "$start" "$end")
    local count=$(echo "$output" | wc -w)

    echo "Bench: $name"
    echo "Time:  $duration"
    echo "Count: $count items"

    if [ "$name" == "optimized" ]; then
        # Check what was removed
        # diff based check
        :
    fi
    echo ""
    eval "${name}_output='$output'"
}

main() {
    generate_data

    run_benchmark "original" "original_logic" "$vers_list" "$html_content"
    run_benchmark "corrected" "corrected_loop_logic" "$vers_list" "$html_content"
    run_benchmark "optimized" "optimized_logic" "$vers_list" "$html_content"

    local orig_count=$(echo "$original_output" | wc -w)
    local corr_count=$(echo "$corrected_output" | wc -w)
    local opt_count=$(echo "$optimized_output" | wc -w)

    if [[ "$corr_count" -ne "$opt_count" ]]; then
        echo "FAIL: Corrected ($corr_count) and Optimized ($opt_count) counts differ!"

        # Debugging diff
        echo "Diff:"
        diff <(echo "$corrected_output" | tr ' ' '\n' | sort) <(echo "$optimized_output" | tr ' ' '\n' | sort)
    else
        echo "PASS: Counts match."
    fi
}

main
