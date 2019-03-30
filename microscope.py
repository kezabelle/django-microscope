# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import functools
from functools import partial
from decimal import Decimal
from uuid import UUID
import logging
import os
import sys
from collections import Iterable, Sized
from itertools import chain
import django
from django.conf import settings, LazySettings  # type: ignore
from django.core.exceptions import ImproperlyConfigured  # type: ignore
from django.utils import six

try:
    from django.urls import path, re_path
except ImportError:
    from django.conf.urls import url as re_path

    path = None
from django.utils.six import integer_types, string_types  # type: ignore
from django.utils.functional import SimpleLazyObject as SLO  # type: ignore
from django.utils.module_loading import import_string  # type: ignore
from environ import Env  # type: ignore

try:
    # noinspection PyUnresolvedReferences
    from typing import (
        TYPE_CHECKING,
        Any,
        Set,
        AnyStr,
        Union,
        List,
        Dict,
        Tuple,
        Optional,
        Type,
        Sequence,
    )
except ImportError:
    TYPE_CHECKING = False
try:
    from json import JSONDecodeError  # type: ignore
except ImportError:

    class JSONDecodeError(NotImplementedError):  # type: ignore
        pass


try:
    from importlib.abc import MetaPathFinder
except ImportError:
    MetaPathFinder = object  # type: ignore

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    import django  # type: ignore


__all__ = ["app", "config", "run", "env", "urlconf", "routes", "setup"]
logger = logging.getLogger(__name__)
# logging without having yet called basicConfig (or setting up
# django's logging ... which won't necessarily have happened yet either) just
# spews out jazz about no configured handlers instead of printing anything.
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


class TrackedEnv(Env):
    def __init__(self, **scheme):
        # type: (dict) -> None
        super(TrackedEnv, self).__init__(**scheme)
        self.seen_settings = set()  # type: Set[str]

    def get_value(self, var, *args, **kwargs):  # type: ignore
        val = super(TrackedEnv, self).get_value(var, *args, **kwargs)
        if var in self.ENVIRON:
            self.seen_settings.add(var)
        return val

    def __str__(self):  # type: ignore
        return ", ".join(sorted(self.seen_settings))

    def __unicode__(self):  # type: ignore
        # noinspection PyUnresolvedReferences
        return unicode(self.__str__())

    def __repr__(self):  # type: ignore
        return "<Env of {0!s}>".format(self)

    def __bool__(self):
        return len(self.seen_settings) > 0


env = TrackedEnv()

# noinspection PyClassHasNoInit
class SimpleLazyObject(SLO):
    def __str__(self):  # type: ignore
        name = self._setupfunc.__name__
        main = getattr(self._setupfunc, "__code__", None)
        main = getattr(main, "co_filename", "__main__")
        return "{prefix!s} -> {func!s}()".format(func=name, prefix=main)

    def __unicode__(self):  # type: ignore
        # noinspection PyUnresolvedReferences
        return unicode(self.__str__())

    def __hash__(self):  # type: ignore
        return hash(tuple(self))


def flatten(items):
    """ https://stackoverflow.com/a/40857703 """
    for x in items:
        if isinstance(x, Iterable) and not (
            isinstance(x, six.string_types) or isinstance(x, six.binary_type)
        ):
            for item in flatten(x):
                yield item
        else:
            yield x


def urlconf(dotted_path):
    # type: (str) -> partial[Any]
    lazy = functools.partial(import_string, dotted_path)
    lazy.__name__ = "microscope.urlconf('{}')".format(dotted_path)  # type: ignore
    lazy.__doc__ = "Deferred importer for another set of urlpatterns"
    return lazy


class Routes(list):
    def add(self, item):
        self.append(item)

    def __call__(self):
        return tuple(self)

    def _decorator(self, handler, url, view, name=None, kwargs=None):
        @functools.wraps(view)
        def decorator(view):
            if hasattr(view, "as_view") and callable(view.as_view):
                view = view.as_view()
            decorated = handler(url, view, name=name, kwargs=kwargs)
            self.add(decorated)
            return view

        return decorator

    if path is None:

        def path(self, url, view=None, name=None, kwargs=None):
            raise NotImplementedError(
                "This version of Django doesn't have django.urls.path(...)"
            )

    else:

        def path(self, url, view=None, name=None, kwargs=None):
            if callable(url) and name is None and kwargs is None:
                raise ValueError(
                    "Used @routes.path instead of @routes.path('path/', 'viewname', kwargs={...})"
                )
            return self._decorator(
                url=url, name=name, view=view, kwargs=kwargs, handler=path
            )

    def regex(self, url, view=None, name=None, kwargs=None):
        if callable(url) and name is None and kwargs is None:
            raise ValueError(
                "Used @routes.regex instead of @routes.regex('^path$', 'viewname', kwargs={...})"
            )
        return self._decorator(
            url=url, name=name, view=view, kwargs=kwargs, handler=re_path
        )


routes = Routes()
routes.__name__ = "microscope.routes"


# noinspection PyPep8Naming
def config(name_hint=None, file_hint=None, **DEFAULTS):
    # type: (Optional[str], Optional[str], Dict[str, Any]) -> LazySettings
    if settings.configured:
        raise RuntimeError(
            "config() has already been called, OR django.conf.settings.configure() was already called"
        )
    setup(name_hint, file_hint)

    options = {}  # type: Dict[str, Any]
    try:
        intended_urls = DEFAULTS.pop("ROOT_URLCONF")
    except KeyError:
        raise ImproperlyConfigured("I need a ROOT_URLCONF to work properly ...")
    if not callable(intended_urls):
        raise ImproperlyConfigured(
            "I need a function or whatever for ROOT_URLCONF, currently"
        )

    urlpatterns = SimpleLazyObject(intended_urls)
    options["ROOT_URLCONF"] = urlpatterns

    def cant_handle_complex(var, default):
        # type: (Any, Any) -> Any
        logger.error("Can't currently read %s from the env", var)
        return default

    for key, value in DEFAULTS.items():
        option_type = type(value)

        if isinstance(value, bool):
            env_func = env.bool
        elif isinstance(value, string_types):
            env_func = env.str
        elif isinstance(value, integer_types):
            env_func = env.int
        elif isinstance(value, float):
            env_func = env.float
        elif isinstance(value, Decimal):
            env_func = partial(env.get_value, cast=Decimal)
        elif isinstance(value, UUID):
            env_func = partial(env.get_value, cast=UUID)
        elif isinstance(value, Iterable) and isinstance(value, Sized):
            # can't be a string now.
            # noinspection PyTypeChecker
            flattened = tuple(flatten(value))
            if len(value) != len(flattened):
                env_func = env.json  # changed length, must be nested or whatever.
            else:
                if issubclass(option_type, list):
                    env_func = env.list
                elif issubclass(option_type, tuple):
                    env_func = env.tuple
                elif issubclass(option_type, dict):
                    env_func = env.dict  # type: ignore
                elif issubclass(option_type, set):
                    env_func = partial(env.get_value, cast=frozenset)
                else:
                    env_func = env.json
        else:
            env_func = cant_handle_complex  # type: ignore

        value = env_func(var=key, default=value)

        if not isinstance(value, bool) and not value:
            logger.warning("config value %s=%s evaluates as falsey", key, value)
        options[key] = value
        del env_func, value
    settings.configure(**options)
    del options
    return settings


class BoundaryWarning(MetaPathFinder):
    # http://xion.org.pl/2012/05/06/hacking-python-imports/
    __slots__ = (
        "root_location",
        "app_location",
        "root_location_length",
        "app_location_length",
        "already_warned",
        "ok_roots",
    )

    def __init__(self, root_location, this_app):
        # type: (str, str) -> None
        self.root_location = root_location
        self.root_location_length = len(root_location)
        self.app_location = this_app
        self.app_location_length = len(this_app)
        self.already_warned = set()  # type: Set[Tuple[str, str, str]]
        self.ok_roots = tuple(
            {
                self.app_location,
                # site-packages?
                os.path.dirname(os.path.dirname(django.__file__)),
                # stdlib/builtin *module*
                os.path.dirname(os.__file__),
                # stdlib/builtin *package*
                os.path.dirname(os.path.dirname(logging.__file__)),
            }
        )

    def find_module(self, fullname, path=None):
        if path is None:
            return None
        for package_path in path:
            # Check our expected roots to see if we're within a sanctioned location.
            # Under py2, this may yield more results than desired for packages outside
            # the roots, if they don't use `from __future__ import absolute_import`
            # as they'll look for package local files first...
            if package_path.startswith(self.ok_roots):
                continue
            else:
                msgparts = (fullname, "".join(path), self.app_location)
                if msgparts not in self.already_warned:
                    logger.error(
                        "Attempted import `%s` (%s) which is outside of %s", *msgparts
                    )
                    self.already_warned.add(msgparts)
        return None


class Setup(object):
    __slots__ = ("name", "runner", "in_app", "done")

    def __init__(self):
        self.name = None  # type: Optional[str]
        self.runner = None  # type: Optional[str]
        self.in_app = False  # type: bool
        self.done = False  # type: bool

    def __call__(self, name, runner):
        # type: (Optional[str], Optional[str]) -> Tuple[str, str]
        if self.done is True:
            assert self.name is not None
            assert self.runner is not None
            return self.name, self.runner
        self.name, self.runner = self.get_name_runner(name, runner)
        assert (
            self.runner is not None
        ), "Couldn't figure out which file had __name__ == '__main__'"
        assert self.name is not None, "Couldn't figure out if __name__ == '__main__'"
        self.in_app = self.determine_if_in_app_root(self.runner)
        self.done = True
        return self.name, self.runner

    def determine_if_in_app_root(self, runner):
        # type: (str) -> bool
        join = os.path.join
        exists = os.path.exists
        abspath = os.path.abspath
        dirname = os.path.dirname
        root = abspath(runner)
        app_dir = abspath(dirname(root))
        app_parent = abspath(dirname(app_dir))
        # If it looks like a normal Django app, and it might be downstream of a
        # project folder (eg: project/appname) then we may need to add the
        # parent dir (eg: project) to the path.
        # To try and make sure this doesn't bring in a whole load of
        # inter-dependencies, we insert a class which raises a warning if an import
        # into another app within the parent dir (eg: project/app2) occurs.
        app_heuristics = ("admin", "apps", "forms", "models", "views", "urls")
        appish_files = (
            join(app_dir, "{0!s}.py".format(heuristic)) for heuristic in app_heuristics
        )
        appish_dirs = (
            join(app_dir, heuristic, "__init__.py") for heuristic in app_heuristics
        )
        in_app = any(exists(path) for path in chain(appish_files, appish_dirs))
        if in_app:
            sys.meta_path.insert(0, BoundaryWarning(app_parent, app_dir))
            if app_parent not in sys.path:
                sys.path.insert(0, app_parent)
            return True
        return False

    def get_name_runner(self, name=None, runner=None):
        # type: (Optional[str], Optional[str]) -> Tuple[Optional[str], Optional[str]]
        if name is None or runner is None:
            runner = None
            name = None
            parent_frame = sys._getframe()
            while parent_frame.f_locals:
                if "__name__" in parent_frame.f_locals:
                    runner = parent_frame.f_code.co_filename
                    name = parent_frame.f_locals["__name__"]
                    break
                parent_frame = parent_frame.f_back
        return name, runner


setup = Setup()


def app(name_hint=None, file_hint=None):
    # type: (Optional[str], Optional[str]) -> Optional['django.core.handlers.wsgi.WSGIHandler']
    if not settings.configured:
        raise RuntimeError("config() has not been called")
    name, runner = setup(name_hint, file_hint)

    if env:
        logger.info("Read %s from environment variables", env)

    if name == "__main__":
        if len(sys.argv) > 1 and sys.argv[1] == "diffsettings":
            sys.stderr.write(
                "Yeah, that doesn't work, see https://code.djangoproject.com/ticket/29236\n"
            )
            sys.exit(1)

        from django.core.management import execute_from_command_line  # type: ignore

        execute_from_command_line(sys.argv)
        return None

    from django.core.wsgi import get_wsgi_application  # type: ignore

    return get_wsgi_application()


# noinspection PyPep8Naming
def run(name_hint=None, file_hint=None, **DEFAULTS):
    # type: (Optional[str], Optional[str], Dict[str, Any]) -> Optional['django.core.handlers.wsgi.WSGIHandler']
    name, runner = setup(name_hint, file_hint)
    config(name_hint=name, file_hint=runner, **DEFAULTS)
    return app(name_hint=name, file_hint=runner)
