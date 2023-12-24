#!/bin/sh

echo "Uploading...."

python3 -m twine upload dist/rointe-sdk-1.5.0.tar.gz -r pypi --verbose
