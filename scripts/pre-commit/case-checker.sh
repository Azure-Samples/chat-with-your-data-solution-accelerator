#!/bin/sh

check_snake_case() {
  if echo $1 | grep -qE '^[a-z0-9_]+$'; then
    return 0
  else
    return 1
  fi
}

SNAKE_CASE=0

for file in "$@"; do
 # echo "Checking file $file"
  filename=$(basename "$file" .py)
  if ! check_snake_case "$filename" ; then
    echo "$file is not in snake case"
    SNAKE_CASE=1
  fi
done

if [ "$SNAKE_CASE" -ne 0 ]; then
    exit 1
fi

exit 0
