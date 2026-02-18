#!/bin/bash
set -u

source_lib() {
    source lib.sh
}

echo "Defining lib.sh..."
cat << 'LIB' > lib.sh
declare -A MY_MAP
MY_MAP["key"]="value"
my_func() {
    echo "Inside my_func: ${MY_MAP["key"]:-unset}"
}
LIB

echo "Sourcing lib.sh via function..."
source_lib

echo "Checking variable in main scope..."
if [[ -v MY_MAP ]]; then
    echo "MY_MAP is set"
else
    echo "MY_MAP is unset"
fi

echo "Calling function defined in lib.sh..."
my_func
