#!/bin/bash
set -u

declare -A MY_ASSOC

func() {
    MY_ASSOC["foo"]="bar"
}

echo "Calling func..."
func
echo "Result: ${MY_ASSOC["foo"]}"
