#!/bin/sh

check_snake_case() {
  echo "Checking $1"
  if echo $1 | grep -qE '^[a-z0-9_]+$'; then
    return 0
  else
    return 1
  fi
}

# Get the list of all files 

FILES=$(find ../../code/ -type d \( -name "frontend" -o -name "dist" -o -name "pages" \) -prune -o -type f -name "*.py" ! -name "Admin.py")
echo "File: $FILES"

SNAKE_CASE=0

for file in $FILES; do
 # echo "Checking file $file"
  filename=$(basename "$file" .py)
  echo "Checking filename $filename"
  if check_snake_case "$filename" ; then
    echo "all good!!"
  else
    echo "Error!! File $filename is not in snake case"
    SNAKE_CASE=1
  fi
done

if [ "$SNAKE_CASE" -ne 0 ]; then
    exit 1
fi

exit 0