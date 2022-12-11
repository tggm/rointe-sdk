#!/bin/sh

echo "Uploading...."

python3 -m twine upload dist/rointe-sdk-1.3.0.tar.gz -r pypi --verbose
