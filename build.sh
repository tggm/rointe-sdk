#!/bin/sh



python -m pip install --upgrade setuptools wheel twine
python setup.py sdist bdist_wheel

