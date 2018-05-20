#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages
from hier_config import __version__

setup(
    name="Hierarchical Configuration",
    version=__version__,
    description="A router and switch configuration intention tool, used to build remediation configurations.",
    long_description="A router and switch configuration intention tool, used to build remediation configurations.",
    url="https://netdevops.io/hier_config/",
    license="MTI",
    packages=find_packages(exclude=['docs', 'tests']),
    author="Andrew Edwards, Jan Brooks, James Williams",
    author_email="andrew.edwards@rackspace.com, jan.brooks@rackspace.com, james.williams@rackspace.com",
    keywords = "hieararchical configuration",
    python_requires='~=3.6',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ]
)
