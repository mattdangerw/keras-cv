#!/bin/bash

base_dir=$(dirname $(dirname $0))

rm -rf ${base_dir}/keras_cv.egg-info/
rm -rf ${base_dir}/keras_cv/**/__pycache__
rm -rf ${base_dir}/keras_cv/__pycache__
