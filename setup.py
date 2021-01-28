#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2020 Scrapfly SAS and Contributors. All Rights Reserved.
#                         Johann Saunier <johann@scrapfly.io>
#
# Licensed under the BSD 2-Clause License (the "License"); you may not use this
# file except in compliance with the License. You may obtain a copy of the
# License at https://opensource.org/licenses/BSD-2-Clause

import pathlib
import re
import sys
from setuptools import find_packages, setup

if sys.version_info < (3, 6):
    raise RuntimeError("Scrapfly SDK requires Python 3.6+")

HERE = pathlib.Path(__file__).parent

MODULE = 'scrapfly'
PACKAGE = 'scrapfly-sdk'

txt = (HERE / MODULE / '__init__.py').read_text('utf-8')

try:
    version = re.findall(r"^__version__ = '([^']+)'\r?$", txt, re.M)[0]
except IndexError:
    raise RuntimeError('Unable to determine version.')

install_requires = [
    'decorator>=4.2.0',
    'requests>=2.25.0',
    'python-dateutil>=2.1,<3.0.0',
    'loguru>=0.5',
    'urllib3>=1.26.0',
    'backoff>=1.10.0'
]

def read(f):
    return (HERE / f).read_text('utf-8').strip()

EXTRA_DEPENDENCIES = {
    'develop': [
        'bumpversion',
        'isort',
        'readme_renderer',
        'twine',
        'setuptools >= 39.2.0',
        'wheel',
        'pdoc3'
    ],
    'scrapy': [
        'scrapy >= 2.4.0'
    ],
    'speedups': [
        'brotli',
        'cchardet',
        'msgpack'
    ],
    'concurrency': [
        'asyncio-pool'
    ],
    'all': [
        'asyncio-pool',
        'brotli',
        'cchardet',
        'msgpack',
        'scrapy >= 2.4.0'
    ]
}

setup(
    name=PACKAGE,
    version=version,
    description='Scrapfly SDK for Scrapfly',
    keywords=['scraping', 'web scraping', 'data', 'extraction', 'scrapfly', 'sdk', 'cloud', 'scrapy'],
    author='Scrapfly',
    author_email='tech@scrapfly.io',
    license='BSD',
    url='https://github.com/scrapfly/python-sdk',
    long_description=read('README.md'),
    long_description_content_type="text/markdown",
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet'
    ],
    project_urls={
        'Company': 'https://scrapfly.io',
        'Documentation': 'https://scrapfly.io/docs',
        'Source': 'https://github.com/scrapfly/python-sdk',
    },
    packages=find_packages(),
    python_requires='>=3.6',
    install_requires=install_requires,
    extras_require=EXTRA_DEPENDENCIES,
    include_package_data=True,
)
