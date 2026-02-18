#!/bin/bash
set -u

func() {
    MY_ASSOC["foo"]="bar"
}

echo "Calling func..."
func
echo "Result: ${MY_ASSOC["foo"]}"
