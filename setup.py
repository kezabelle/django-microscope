#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
from setuptools import setup

if sys.version_info[0] == 2:
    # get the Py3K compatible `encoding=` for opening files.
    from io import open


HERE = os.path.abspath(os.path.dirname(__file__))


def make_readme(root_path):
    consider_files = ("README.rst", "LICENSE", "CHANGELOG", "CONTRIBUTORS")
    for filename in consider_files:
        filepath = os.path.realpath(os.path.join(root_path, filename))
        if os.path.isfile(filepath):
            with open(filepath, mode="r", encoding="utf-8") as f:
                yield f.read()


LICENSE = "BSD License"
URL = "https://github.com/kezabelle/django-microscope/"
LONG_DESCRIPTION = "\r\n\r\n----\r\n\r\n".join(make_readme(HERE))
SHORT_DESCRIPTION = "Turn a Django app into a Django project so it can run as a microservice or whatever"
KEYWORDS = ("django", "django-microscope", "manage.py", "microservice", "microscope")

setup(
    name="django-microscope",
    version="0.1.1",
    author="Keryn Knight",
    author_email="django-microscope@kerynknight.com",
    maintainer="Keryn Knight",
    maintainer_email="django-microscope@kerynknight.com",
    description=SHORT_DESCRIPTION[0:200],
    long_description=LONG_DESCRIPTION,
    packages=[],
    py_modules=["microscope"],
    include_package_data=True,
    install_requires=["Django>=1.9", "django-environ>=0.4.4"],
    tests_require=[],
    zip_safe=False,
    keywords=" ".join(KEYWORDS),
    license=LICENSE,
    url=URL,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: {}".format(LICENSE),
        "Natural Language :: English",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Framework :: Django",
    ],
)
