#! /usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from microscope import run

def urls():
    return []

application = run(
    DEBUG=True,
    ROOT_URLCONF=urls,
)
