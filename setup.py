import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="anaforatools",
    version="1.0.0",
    author="Steven Bethard",
    author_email="bethard@arizona.edu",
    description="Utilities for working with Anafora annotations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bethard/anaforatools",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
