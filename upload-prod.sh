#!/bin/sh
echo "Uploading...."

python3 -m twine upload dist/rointe_sdk-1.6.0.tar.gz -r pypi --verbose
