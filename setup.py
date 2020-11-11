#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="hier_config",
    version="2.0.0",
    description="A router and switch configuration intention tool, used to build remediation configurations.",
    long_description="A router and switch configuration intention tool, used to build remediation configurations.",
    url="https://netdevops.io/hier_config/",
    license="MIT",
    packages=find_packages(exclude=["docs", "tests"]),
    author="Andrew Edwards, Jan Brooks, James Williams",
    author_email="andrew.edwards@rackspace.com, jan.brooks@rackspace.com, james.williams@rackspace.com",
    keywords="hier_config",
    python_requires=">=3.7",
    install_requires=["PyYAML", "pep8", "pytest"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Telecommunications Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Natural Language :: English",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking",
    ],
)
