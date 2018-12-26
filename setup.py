#!/usr/bin/env python

import os
import re
from typing import Any

from setuptools import setup


base_dir = os.path.dirname(__file__)

about = {}  # type: Any
with open(os.path.join(base_dir, "qslang", "__about__.py")) as f:
    exec(f.read(), about)

with open(os.path.join(base_dir, "README.md")) as f:
    long_description = f.read()

if False:
    with open(os.path.join(base_dir, "CHANGELOG.rst")) as f:
        # Remove :issue:`ddd` tags that breaks the description rendering
        changelog = re.sub(
            r":issue:`(\d+)`",
            r"`#\1 <https://github.com/pypa/pipfile/issues/\1>`__",
            f.read(),
        )
        long_description = "\n".join([long_description, changelog])


setup(name=about["__title__"],
      version=about["__version__"],
      description=about["__summary__"],
      long_description=long_description,
      author=about["__author__"],
      author_email=about["__email__"],
      url=about["__uri__"],
      packages=set(["qslang"]),
      install_requires=[],
      classifiers=[
          'Programming Language :: Python :: 3']
      )
