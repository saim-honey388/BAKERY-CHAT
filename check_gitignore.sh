#!/bin/bash

echo "Checking if .gitignore is properly configured..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "Error: This is not a git repository. Please initialize git first with 'git init'"
    exit 1
fi

echo "1. Checking current .gitignore content:"
echo "----------------------------------------"
cat .gitignore
echo ""
echo "----------------------------------------"

echo "2. Checking git status:"
echo "----------------------"
git status
echo ""
echo "----------------------"

echo "3. Checking if .venv is ignored:"
echo "-------------------------------"
if git check-ignore -q .venv/; then
    echo ".venv/ is properly ignored"
else
    echo ".venv/ is NOT ignored - this is a problem"
fi

echo ""
echo "4. Checking specific files that might be problematic:"
echo "----------------------------------------------------"
# Check some common virtual environment files
files_to_check=(".venv/bin/python" ".venv/lib/python*/site-packages" ".venv/pyvenv.cfg")

for file in "${files_to_check[@]}"; do
    if [ -e "$file" ]; then
        if git check-ignore -q "$file" 2>/dev/null; then
            echo "$file is properly ignored"
        else
            echo "$file is NOT ignored"
        fi
    else
        echo "$file does not exist"
    fi
done

echo ""
echo "5. If you see files that should be ignored but aren't:"
echo "-----------------------------------------------------"
echo "Run these commands to fix the issue:"
echo "  git rm -r --cached .venv/  # Remove .venv from git tracking"
echo "  git add .gitignore         # Add updated .gitignore"
echo "  git commit -m \"Update .gitignore and remove .venv from tracking\""