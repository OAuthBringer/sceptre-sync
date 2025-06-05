from setuptools import setup, find_packages

setup(
    name="sceptre_sync",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "ruamel.yaml>=0.17.0",
        "jsonschema>=3.2.0",
    ],
    entry_points={
        "console_scripts": [
            "sceptre-sync=sceptre_sync.cli:main",
        ],
    },
    author="Jon Staples",
    author_email="example@example.com",
    description="A utility for synchronizing configuration parameters between Sceptre Config files",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
