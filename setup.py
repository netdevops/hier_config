#!/usr/bin/env python
import os

from setuptools import setup, find_packages


os.environ["MPLCONFIGDIR"] = "."

__version__ = "2.0.0"

description = (
    "A network configuration comparison tool, used to build remediation configurations."
)

setup(
    name="hier_config",
    version=__version__,
    description=description,
    long_description=description,
    url="https://netdevops.io/hier_config/",
    license="MIT",
    packages=find_packages(exclude=["docs", "tests"]),
    author="Andrew Edwards, Jan Brooks, James Williams",
    author_email=", ".join(
        [
            "andrew.edwards@rackspace.com",
            "jan.brooks@rackspace.com",
            "james.williams@networktocode.com",
        ]
    ),
    keywords="hier_config",
    python_requires=">=3.8",
    install_requires=["pyyaml"],
    extras_require={
        "testing": [
            "pytest",
            "mypy",
            "pylint",
            "pytest-cov",
            "pytest-black",
            "pytest-runner",
            "pytest-flake8",
            # There were issues encountered when trying to use the below modules
            # ERROR: pytest-pylint 0.18.0 has requirement pytest>=5.4, but you'll have pytest 5.2.1 which is incompatible.
            # "pytest-pylint",
            # I need to figure out how to ignore all other directories except for hier_config
            # "pytest-mypy",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Telecommunications Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        # "Programming Language :: Python :: 3.10",
        "Natural Language :: English",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
)
