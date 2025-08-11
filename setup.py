#!/usr/bin/env python3
"""
Setup script for 200Model8CLI - OpenRouter CLI Agent
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="200Model8CLI",
    version="1.0.0",
    author="200Model8CLI Development Team",
    author_email="dev@200model8cli.com",
    description="A sophisticated CLI tool that uses OpenRouter's API to access multiple AI models with tool calling capabilities",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/200Model8CLI",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Tools",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "docs": [
            "sphinx>=6.0.0",
            "sphinx-rtd-theme>=1.2.0",
            "myst-parser>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "200model8cli=model8cli.cli:main",
            "m8cli=model8cli.cli:main",  # Short alias
        ],
    },
    include_package_data=True,
    package_data={
        "model8cli": [
            "templates/*.yaml",
            "templates/*.json",
            "config/*.yaml",
        ],
    },
    zip_safe=False,
)
