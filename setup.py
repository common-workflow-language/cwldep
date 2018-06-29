#!/usr/bin/env python
from __future__ import absolute_import

import os
import sys

from setuptools import setup

SETUP_DIR = os.path.dirname(__file__)
README = os.path.join(SETUP_DIR, 'README.md')

setup(name='cwldep',
      version='1.0',
      description='Common workflow language dependency manager',
      long_description=open(README).read(),
      author='Common workflow language working group',
      author_email='common-workflow-language@googlegroups.com',
      url="https://github.com/common-workflow-language/cwldep",
      download_url="https://github.com/common-workflow-language/cwldep",
      license='Apache 2.0',
      packages=["cwldep"],
      include_package_data=True,
      install_requires=['cwltool', 'python-dateutil'],
      test_suite='tests',
      entry_points={
          'console_scripts': ["cwldep=cwldep:main"]
      },
      tests_require=['mock >= 2.0.0',],
      zip_safe=True,
      python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, <4'
)
