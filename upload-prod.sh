#!/bin/sh

echo "Uploading...."

python3 -m twine upload dist/rointe-sdk-1.2.1.tar.gz -r pypi --verbose
