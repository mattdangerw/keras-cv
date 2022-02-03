#!/bin/bash -e

base_dir=$(dirname $(dirname $0))

isort --sl -c "${base_dir}"
if ! [ $? -eq 0 ]; then
  echo "Please run \"./shell/format.sh\" to format the code."
  exit 1
fi
echo "no issues with isort"
flake8 "${base_dir}"
if ! [ $? -eq 0 ]; then
  echo "Please fix the code style issue."
  exit 1
fi
echo "no issues with flake8"
black --check "${base_dir}"
if ! [ $? -eq 0 ]; then
  echo "Please run \"./shell/format.sh\" to format the code."
    exit 1
fi
echo "no issues with black"
for i in $(find "${base_dir}" -name '*.py'); do
  if ! grep -q Copyright $i; then
    echo "Copyright not found in $i"
    exit 1
  fi
echo "linting success!"
