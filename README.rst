django-microscope
================================

:author: Keryn Knight
:version: 0.1.0

Convert a `Django`_ app into a standalone `Django`_ project so you can run it
independently as a microservice or what-have-you.

Configuration options given to ``run()`` are defaults, and may be replaced by
environment variables thanks to `django-environ`_

If your app crosses boundaries into another application via imports, you should
hopefully get warnings. Figuring out how to do that was mostly why I did this. I'd
never encountered `sys.meta_path`_ before.

Alternatives
------------

If you're starting a **new** app and want the proper micro experience, you
maybe want `django-micro`_ instead. It has magic involved too, but different magic!

Usage
-----

Create yourself a ``manage.py`` file in your app's folder (eg: where your
``views.py``, ``models.py`` are) and do something like this...

.. code:: python

    from microscope import run
    from django.conf.urls import url  # or path etc.

    def urls():
        from myapp.views import MyView
        return [url('^$', MyView.as_view())]

    application = run(
        DEBUG=True,
        ROOT_URLCONF=urls
    )

Running it
----------

It'll probably work, right? ``python manage.py [command]`` should all be OK.
You could probably go even more minimal with `dj-cmd`_ so you can do ``dj r``

Gunicorn
^^^^^^^^

``gunicorn manage`` and ``gunicorn manage:application`` should both work fine,
as should ``DEBUG=0 gunicorn manage`` to change the setting by env-var.

UWSGI
^^^^^

Whatever madness of command-line arguments or ini configuration invokes uwsgi for
you probably works; eg: ``uwsgi --http :8080 --wsgi-file `pwd`/manage.py --virtualenv $VIRTUAL_ENV``

Environment variables should be fine?

mod_wsgi
^^^^^^^^

It'd probably work, but environment variable substitution for settings won't work
at all, I don't think.

URL configuration
-----------------

the ``ROOT_URLCONF`` has to be a callable (function or object implementing ``__call__``)
to defer execution of imports related to userland code, which almost certainly
depends on settings having already been configured. It's also because
your existing ``urls.py`` for the app may not be where you want the mountpoints
when running it standalone vs as part of a monolith project.

You'll eagerly get an ``ImproperlyConfigured`` exception when starting the app, if your
``ROOT_URLCONF`` is missing or not-callable.

Don't worry, it's only called at startup, not on every request!

If you **do** want to use another file, ``microscope.urlconf('dotted.path.to.urls')``
may help

.. code:: python

    from microscope import run, urlconf
    application = run(ROOT_URLCONF=urlconf('path.to.urls'))

Tests
-----

Literally none. If you have `honcho`_ you can do ``honcho -f demo_project.procfile start``
to start the ``demo_project.py`` (equivalent of ``manage.py``) using ``runserver``,
``gunicorn`` and ``uwsgi`` on ports **8000**, **8001** and **8002** respectively.

The license
-----------

It's the `FreeBSD`_. There's should be a ``LICENSE`` file in the root of the repository, and in any archives.

.. _FreeBSD: http://en.wikipedia.org/wiki/BSD_licenses#2-clause_license_.28.22Simplified_BSD_License.22_or_.22FreeBSD_License.22.29
.. _Django: https://docs.djangoproject.com/en/stable/
.. _django-environ: https://github.com/joke2k/django-environ
.. _honcho: https://honcho.readthedocs.io/
.. _sys.meta_path: https://docs.python.org/3/library/sys.html#sys.meta_path
.. _django-micro: https://github.com/zenwalker/django-micro
.. _dj-cmd: https://github.com/nigma/dj-cmd
