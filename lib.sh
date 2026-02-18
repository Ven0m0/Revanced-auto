declare -A MY_MAP
MY_MAP["key"]="value"
my_func() {
    echo "Inside my_func: ${MY_MAP[key]:-unset}"
}
