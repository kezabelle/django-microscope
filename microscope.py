# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import
from functools import partial
from decimal import Decimal
from uuid import UUID
import logging
import os
import sys
from collections import Iterable, Sized
from itertools import chain
from django.conf import settings, LazySettings  # type: ignore
from django.core.exceptions import ImproperlyConfigured  # type: ignore
from django.utils.six import integer_types, string_types  # type: ignore
from django.utils.functional import SimpleLazyObject as Lazy  # type: ignore
from django.utils.module_loading import import_string  # type: ignore
from environ import Env  # type: ignore

try:
    # noinspection PyUnresolvedReferences
    from typing import TYPE_CHECKING, Any, Set, AnyStr, Union, List, Dict, Tuple
except ImportError:
    TYPE_CHECKING = False
try:
    from json import JSONDecodeError  # type: ignore
except ImportError:

    class JSONDecodeError(NotImplementedError):  # type: ignore
        pass


if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    import django  # type: ignore


__all__ = ["app", "config", "run", "env"]
logger = logging.getLogger(__name__)


class TrackedEnv(Env):
    def __init__(self, **scheme):
        super(TrackedEnv, self).__init__(**scheme)
        self.seen_settings = set()

    def get_value(self, var, *args, **kwargs):
        val = super(TrackedEnv, self).get_value(var, *args, **kwargs)
        if var in self.ENVIRON:
            self.seen_settings.add(var)
        return val

    def __str__(self):
        return ", ".join(sorted(self.seen_settings))

    def __unicode__(self):
        # noinspection PyUnresolvedReferences
        return unicode(self.__str__())

    def __repr__(self):
        return "<Env of {0!s}>".format(self)


env = TrackedEnv()


# noinspection PyClassHasNoInit
class SimpleLazyObject(Lazy):
    def __str__(self):
        name = self._setupfunc.__name__
        main = getattr(self._setupfunc, "__code__", None)
        main = getattr(main, "co_filename", "__main__")
        return "{prefix!s} -> {func!s}()".format(func=name, prefix=main)

    def __unicode__(self):
        # noinspection PyUnresolvedReferences
        return unicode(self.__str__())

    def __hash__(self):
        return hash(tuple(self))


def flatten(items):
    """ https://stackoverflow.com/a/40857703 """
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            for item in flatten(x):
                yield item
        else:
            yield x


def urlconf(dotted_path):
    # type: (str) -> list
    return import_string(dotted_path)


# noinspection PyPep8Naming
def config(**DEFAULTS):
    # type: (Dict[str, Any]) -> LazySettings
    if settings.configured:
        raise RuntimeError(
            "config() has already been called, OR django.conf.settings.configure() was already called"
        )

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


class BoundaryWarning(object):
    # http://xion.org.pl/2012/05/06/hacking-python-imports/
    __slots__ = (
        "root_location",
        "app_location",
        "root_location_length",
        "app_location_length",
        "already_warned",
    )

    def __init__(self, root_location, this_app):
        # type: (str, str) -> None
        self.root_location = root_location
        self.root_location_length = len(root_location)
        self.app_location = this_app
        self.app_location_length = len(this_app)
        self.already_warned = set()  # type: Set[Tuple[str, str, str]]

    def find_module(self, fullname, path=None):
        # type: (str, Union[List[str], None]) -> None
        if path is None:
            return None
        package_root, _, remainder = fullname.partition(".")
        package_root_length = len(package_root)
        for package_path in path:
            root = package_path[0 : self.root_location_length]
            this_module = package_path[0 : self.app_location_length]
            within_root = root == self.root_location
            not_this_app = this_module != self.app_location
            related_module = this_module[-package_root_length:] == package_root
            if within_root and not_this_app and related_module:
                msgparts = (fullname, "".join(path), self.app_location)
                if msgparts not in self.already_warned:
                    logger.error(
                        "Attempted import `%s` (%s) which is outside of %s", *msgparts
                    )
                    self.already_warned.add(msgparts)
        return None


def app():
    join = os.path.join
    exists = os.path.exists
    abspath = os.path.abspath
    dirname = os.path.dirname

    # noinspection PyProtectedMember
    frame = sys._getframe()
    # noinspection PyUnusedLocal
    this_file = frame.f_code.co_filename

    # Walk backwards through the frames until we find the __name__, which should
    # also give us the filename running the script.
    runner = None
    name = None
    parent_frame = frame
    while parent_frame.f_locals:
        if "__name__" in parent_frame.f_locals:
            runner = parent_frame.f_code.co_filename  # type: str
            name = parent_frame.f_locals["__name__"]  # type: str
            break
        parent_frame = parent_frame.f_back
    assert (
        runner is not None
    ), "Couldn't figure out which file had __name__ == '__main__'"
    assert name is not None, "Couldn't figure out if __name__ == '__main__'"

    root = abspath(runner)
    app_dir = abspath(dirname(root))
    app_parent = abspath(dirname(app_dir))
    if not settings.configured:
        raise RuntimeError("config() has not been called")

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
    del runner, root, app_heuristics, appish_files, appish_dirs, in_app
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
def run(**DEFAULTS):
    # type: (Dict[str, Any]) -> Union[None, 'django.core.handlers.wsgi.WSGIHandler']
    config(**DEFAULTS)
    return app()
