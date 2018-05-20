#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages
from hier_config import __version__

setup(
    name="hier_config",
    version=__version__,
    description="A router and switch configuration intention tool, used to build remediation configurations.",
    long_description="A router and switch configuration intention tool, used to build remediation configurations.",
    url="https://netdevops.io/hier_config/",
    license="MTI",
    packages=find_packages(exclude=['docs', 'tests']),
    author="Andrew Edwards, Jan Brooks, James Williams",
    author_email="andrew.edwards@rackspace.com, jan.brooks@rackspace.com, james.williams@rackspace.com",
    keywords = "hier_config",
    python_requires='~=3.6',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Natural Language :: English',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
    ]
)
