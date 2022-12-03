"""Lib setup"""

from setuptools import find_packages, setup


def requirements():
    """Load requirements"""
    with open("requirements.txt") as fileobj:
        return [line.strip() for line in fileobj]


with open("README.md", encoding="utf-8") as fh:
    doc_long_description = fh.read()

# This call to setup() does all the work
setup(
    name="rointe-sdk",
    version="1.2.2",
    author="tggm",
    description="Python SDK for rointeconnect.com",
    long_description=doc_long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tggm/rointe-sdk",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements(),
    python_requires=">=3.7",
)
