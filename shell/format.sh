#!/bin/bash -e

base_dir=$(dirname $(dirname $0))

isort --sl ${base_dir}
black ${base_dir}
