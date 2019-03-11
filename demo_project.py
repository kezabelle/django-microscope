#! /usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.http import Http404

from microscope import run, routes


@routes.regex("^$")
def example(request):
    raise Http404("nope")


application = run(
    DEBUG=True,
    ROOT_URLCONF=routes,
    ALLOWED_HOSTS=(),
    __name__=__name__,
    __file__=__file__,
)
