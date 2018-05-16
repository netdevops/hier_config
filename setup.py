#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages
from hier_config import __version__

setup(
    name="Hierarchical Configuration",
    description="A router and switch configuration intention tool, used to build remediation configurations.",
    version=__version__,
    packages=find_packages(),
    author="Andrew Edwards, Jan Brooks, James Williams",
    email="andrew.edwards@rackspace.com, jan.brooks@rackspace.com, james.williams@rackspace.com",
    classifiers = [
      'Programming Language :: Python :: 3.6',
      'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
