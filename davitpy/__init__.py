# Copyright (C) 2012  VT SuperDARN Lab
# Full license can be found in LICENSE.txt
"""
*********************
**Module**: davipty
*********************
Module for everything SuperDARN

**Modules**:
    * :mod:`davipty.pydarn`: superdarn data I/O and plotting utilities
"""

# Most of the rc stuff in this file was taken/adapted from matplotlib code:
# https://github.com/matplotlib

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six
import os
import sys
import io
import locale
import re
import warnings
import contextlib
from itertools import chain

from davitpy.rcsetup import defaultParams

__version__ = str('0.3')

_error_details_fmt = 'line #%d\n\t"%s"\n\tin file "%s"'

# TO DO
# Add some try: except: statements for python packages that davitpy requires


def _is_writable_dir(p):
    """
    p is a string pointing to a putative writable dir -- return True p
    is such a string, else False
    """
    try:
        p + ''  # test is string like
    except TypeError:
        return False

    # Test whether the operating system thinks it's a writable directory.
    # Note that this check is necessary on Google App Engine, because the
    # subsequent check will succeed even though p may not be writable.
    if not os.access(p, os.W_OK) or not os.path.isdir(p):
        return False

    # Also test that it is actually possible to write to a file here.
    try:
        t = tempfile.TemporaryFile(dir=p)
        try:
            t.write(b'1')
        finally:
            t.close()
    except:
        return False

    return True

URL_REGEX = re.compile(r'http://|https://|ftp://|file://|file:\\')

def is_url(filename):
    """Return True if string is an http, ftp, or file URL path."""
    return URL_REGEX.match(filename) is not None

def _url_lines(f):
    # Compatibility for urlopen in python 3, which yields bytes.
    for line in f:
        yield line.decode('utf8')

@contextlib.contextmanager
def _open_file_or_url(fname):
    if is_url(fname):
        f = urlopen(fname)
        yield _url_lines(f)
        f.close()
    else:
        with io.open(fname, encoding=locale.getdefaultlocale()[1]) as f:
            yield f

def _get_home():
    """Find user's home directory if possible.
    Otherwise, returns None.
    :see:
        http://mail.python.org/pipermail/python-list/2005-February/325395.html
    """
    try:
        if six.PY2 and sys.platform == 'win32':
            path = os.path.expanduser(b"~").decode(sys.getfilesystemencoding())
        else:
            path = os.path.expanduser("~")
    except ImportError:
        # This happens on Google App Engine (pwd module is not present).
        pass
    else:
        if os.path.isdir(path):
            return path
    for evar in ('HOME', 'USERPROFILE', 'TMP'):
        path = os.environ.get(evar)
        if path is not None and os.path.isdir(path):
            return path
    return None

def get_home():
    return _get_home()


def _create_tmp_config_dir():
    """
    If the config directory can not be created, create a temporary
    directory.
    Returns None if a writable temporary directory could not be created.
    """
    import getpass
    import tempfile

    try:
        tempdir = tempfile.gettempdir()
    except NotImplementedError:
        # Some restricted platforms (such as Google App Engine) do not provide
        # gettempdir.
        return None
    tempdir = os.path.join(tempdir, 'davitpy-%s' % getpass.getuser())
    os.environ['DAVITCONFIGDIR'] = tempdir

    return tempdir

def _get_xdg_config_dir():
    """
    Returns the XDG configuration directory, according to the `XDG
    base directory spec
    <http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html>`_.
    """
    path = os.environ.get('XDG_CONFIG_HOME')
    if path is None:
        path = get_home()
        if path is not None:
            path = os.path.join(path, '.config')
    return path

def _get_xdg_cache_dir():
    """
    Returns the XDG cache directory, according to the `XDG
    base directory spec
    <http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html>`_.
    """
    path = os.environ.get('XDG_CACHE_HOME')
    if path is None:
        path = get_home()
        if path is not None:
            path = os.path.join(path, '.cache')
    return path

def mkdirs(newdir, mode=0o777):
    """
    make directory *newdir* recursively, and set *mode*.  Equivalent to ::
        > mkdir -p NEWDIR
        > chmod MODE NEWDIR
    """
    try:
        if not os.path.exists(newdir):
            parts = os.path.split(newdir)
            for i in range(1, len(parts) + 1):
                thispart = os.path.join(*parts[:i])
                if not os.path.exists(thispart):
                    os.makedirs(thispart, mode)

    except OSError as err:
        # Reraise the error unless it's about an already existing directory
        if err.errno != errno.EEXIST or not os.path.isdir(newdir):
            raise

def _get_config_or_cache_dir(xdg_base):
    configdir = os.environ.get('DAVITCONFIGDIR')
    if configdir is not None:
        configdir = os.path.abspath(configdir)
        if not os.path.exists(configdir):
            mkdirs(configdir)

        if not _is_writable_dir(configdir):
            return _create_tmp_config_dir()
        return configdir

    p = None
    h = get_home()
    if h is not None:
        p = os.path.join(h, '.davitpy')
    if (sys.platform.startswith('linux') and xdg_base):
        p = os.path.join(xdg_base, 'davitpy')

    if p is not None:
        if os.path.exists(p):
            if _is_writable_dir(p):
                return p
        else:
            try:
                mkdirs(p)
            except OSError:
                pass
            else:
                return p

    return _create_tmp_config_dir()

def _get_configdir():
    """
    Return the string representing the configuration directory.
    The directory is chosen as follows:
    1. If the DAVITPYCONFIGDIR environment variable is supplied, choose that.
    2a. On Linux, if `$HOME/.matplotlib` exists, choose that, but warn that
        that is the old location.  Barring that, follow the XDG specification
        and look first in `$XDG_CONFIG_HOME`, if defined, or `$HOME/.config`.
    2b. On other platforms, choose `$HOME/.davitpy`.
    3. If the chosen directory exists and is writable, use that as the
       configuration directory.
    4. If possible, create a temporary directory, and use it as the
       configuration directory.
    5. A writable directory could not be found or created; return None.
    """
    return _get_config_or_cache_dir(_get_xdg_config_dir())

def _decode_filesystem_path(path):
    if isinstance(path, bytes):
        return path.decode(sys.getfilesystemencoding())
    else:
        return path

def _get_data_path():

    if 'DAVITPYDATA' in os.environ:
        path = os.environ['DAVITPYDATA']
        if not os.path.isdir(path):
            raise RuntimeError('Path in environment DAVITPYDATA not a '
                               'directory')
        return path
    _file = _decode_filesystem_path(__file__)
    path = os.sep.join([os.path.dirname(_file)])
    if os.path.isdir(path):
        return path

    # setuptools' namespace_packages may highjack this init file
    # so need to try something known to be in matplotlib, not basemap

    import davitpy.rcsetup
    _file = _decode_filesystem_path(davitpy.rcsetup.__file__)
    path = os.sep.join([os.path.dirname(_file)])

    print(path)
    if os.path.isdir(path):
        return path

    # py2exe zips pure python, so still need special check
    if getattr(sys, 'frozen', None):
        exe_path = os.path.dirname(sys.executable)
        path = os.path.join(exe_path)
        if os.path.isdir(path):
            return path

        # Try again assuming we need to step up one more directory
        path = os.path.join(os.path.split(exe_path)[0])
        if os.path.isdir(path):
            return path

        # Try again assuming sys.path[0] is a dir not a exe
        path = os.path.join(sys.path[0])
        if os.path.isdir(path):
            return path

    raise RuntimeError('Could not find the davitpy data files')

def get_data_path():
    return _get_data_path()

def _get_data_path_cached():
    if defaultParams['datapath'][0] is None:
        defaultParams['datapath'][0] = _get_data_path()
    return defaultParams['datapath'][0]



def davitpy_fname():
    """
    Get the location of the config file.
    The file location is determined in the following order
    - `$PWD/davitpyrc`
    - environment variable `DAVITPYRC`
    - `$DAVITCONFIGDIR/davitpy`
    - On Linux,
          - `$HOME/.davitpy/davitpyrc`, if it exists
          - or `$XDG_CONFIG_HOME/davitpy/davitpyrc` (if
            $XDG_CONFIG_HOME is defined)
          - or `$HOME/.config/davitpy/davitpyrc` (if
            $XDG_CONFIG_HOME is not defined)
    - On other platforms,
         - `$HOME/.davitpy/davitpyrc` if `$HOME` is defined.
    - Lastly, it looks in `$DAVITPYDATA/davitpyrc` for a
      system-defined copy.
    """
    if six.PY2:
        cwd = os.getcwdu()
    else:
        cwd = os.getcwd()
    fname = os.path.join(cwd, 'davitpyrc')
    if os.path.exists(fname):
        return fname

    if 'DAVITPYRC' in os.environ:
        path = os.environ['DAVITPYRC']
        if os.path.exists(path):
            fname = os.path.join(path, 'davitpyrc')
            if os.path.exists(fname):
                return fname

    configdir = _get_configdir()
    if configdir is not None:
        fname = os.path.join(configdir, 'davitpyrc')
        if os.path.exists(fname):
            home = get_home()
            if (sys.platform.startswith('linux') and
                home is not None and
                os.path.exists(os.path.join(
                    home, '.davitpy', 'davitpyrc'))):
                warnings.warn(
                    "Found davitpy configuration in ~/.davitpy/. "
                    "To conform with the XDG base directory standard, "
                    "this configuration location has been deprecated "
                    "on Linux, and the new location is now %s/davitpy/. "
                    "Please move your configuration there to ensure that "
                    "davitpy will continue to find it in the future." %
                    _get_xdg_config_dir())
                return os.path.join(
                    home, '.davitpy', 'davitpyrc')
            return fname

    path = get_data_path()  # guaranteed to exist or raise
    fname = os.path.join(path, 'davitpyrc')
    if not os.path.exists(fname):
        warnings.warn('Could not find davitpyrc; using defaults')

    return fname

class RcParams(dict):

    """
    A dictionary object including validation
    validating functions are defined and associated with rc parameters in
    :mod:`davitpy.rcsetup`
    """

    validate = dict((key, converter) for key, (default, converter) in
                    six.iteritems(defaultParams))
    msg_depr = "%s is deprecated and replaced with %s; please use the latter."
    msg_depr_ignore = "%s is deprecated and ignored. Use %s"

    # validate values on the way in
    def __init__(self, *args, **kwargs):
        for k, v in six.iteritems(dict(*args, **kwargs)):
            self[k] = v

    def __setitem__(self, key, val):
        try:
            if key in _deprecated_map:
                alt_key, alt_val = _deprecated_map[key]
                warnings.warn(self.msg_depr % (key, alt_key))
                key = alt_key
                val = alt_val(val)
            elif key in _deprecated_ignore_map:
                alt = _deprecated_ignore_map[key]
                warnings.warn(self.msg_depr_ignore % (key, alt))
                return
            try:
                cval = self.validate[key](val)
            except ValueError as ve:
                raise ValueError("Key %s: %s" % (key, str(ve)))
            dict.__setitem__(self, key, cval)
        except KeyError:
            raise KeyError('%s is not a valid rc parameter.\
See rcParams.keys() for a list of valid parameters.' % (key,))

    def __getitem__(self, key):
        if key in _deprecated_map:
            alt_key, alt_val = _deprecated_map[key]
            warnings.warn(self.msg_depr % (key, alt_key))
            key = alt_key
        elif key in _deprecated_ignore_map:
            alt = _deprecated_ignore_map[key]
            warnings.warn(self.msg_depr_ignore % (key, alt))
            key = alt
        return dict.__getitem__(self, key)

    # http://stackoverflow.com/questions/2390827
    # (how-to-properly-subclass-dict-and-override-get-set)
    # the default dict `update` does not use __setitem__
    # so rcParams.update(...) (such as in seaborn) side-steps
    # all of the validation over-ride update to force
    # through __setitem__
    def update(self, *args, **kwargs):
        for k, v in six.iteritems(dict(*args, **kwargs)):
            self[k] = v

    def __repr__(self):
        import pprint
        class_name = self.__class__.__name__
        indent = len(class_name) + 1
        repr_split = pprint.pformat(dict(self), indent=1,
                                    width=80 - indent).split('\n')
        repr_indented = ('\n' + ' ' * indent).join(repr_split)
        return '{0}({1})'.format(class_name, repr_indented)

    def __str__(self):
        return '\n'.join('{0}: {1}'.format(k, v)
                         for k, v in sorted(self.items()))

    def keys(self):
        """
        Return sorted list of keys.
        """
        k = list(dict.keys(self))
        k.sort()
        return k

    def values(self):
        """
        Return values in order of sorted keys.
        """
        return [self[k] for k in self.keys()]

    def find_all(self, pattern):
        """
        Return the subset of this RcParams dictionary whose keys match,
        using :func:`re.search`, the given ``pattern``.
        .. note::
            Changes to the returned dictionary are *not* propagated to
            the parent RcParams dictionary.
        """
        import re
        pattern_re = re.compile(pattern)
        return RcParams((key, value)
                        for key, value in self.items()
                        if pattern_re.search(key))


# This is the map to be used for deprecating parameters in the future
_deprecated_map = {
    #'name':   ('value', lambda x: x),
    }

_deprecated_ignore_map = {
    }

_obsolete_set = set(['tk.pythoninspect', ])
_all_deprecated = set(chain(_deprecated_ignore_map,
                            _deprecated_map, _obsolete_set))


def rc_params(fail_on_error=False):
    """Return a :class:`davitpy.RcParams` instance from the
    default davitpy rc file.
    """
    fname = davitpy_fname()
    if not os.path.exists(fname):
        # this should never happen, default in mpl-data should always be found
        message = 'could not find rc file; returning defaults'
        ret = RcParams([(key, default) for key, (default, _) in
                        six.iteritems(defaultParams)
                        if key not in _all_deprecated])
        warnings.warn(message)
        return ret

    return rc_params_from_file(fname, fail_on_error)

def _rc_params_in_file(fname, fail_on_error=False):
    """Return :class:`matplotlib.RcParams` from the contents of the given file.
    Unlike `rc_params_from_file`, the configuration class only contains the
    parameters specified in the file (i.e. default values are not filled in).
    """
    cnt = 0
    rc_temp = {}
    with _open_file_or_url(fname) as fd:
        for line in fd:
            print
            cnt += 1
            strippedline = line.split('#', 1)[0].strip()
            if not strippedline:
                continue
            tup = strippedline.split(':', 1)
            if len(tup) != 2:
                error_details = _error_details_fmt % (cnt, line, fname)
                warnings.warn('Illegal %s' % error_details)
                continue
            key, val = tup
            key = key.strip()
            val = val.strip()
            if key in rc_temp:
                warnings.warn('Duplicate key in file "%s", line #%d' %
                              (fname, cnt))
            rc_temp[key] = (val, line, cnt)

    config = RcParams()

    #for key in ('verbose.level', 'verbose.fileo'):
    #    if key in rc_temp:
    #        val, line, cnt = rc_temp.pop(key)
    #        if fail_on_error:
    #            config[key] = val  # try to convert to proper type or raise
    #        else:
    #            try:
    #                config[key] = val  # try to convert to proper type or skip
    #            except Exception as msg:
    #                error_details = _error_details_fmt % (cnt, line, fname)
    #                warnings.warn('Bad val "%s" on %s\n\t%s' %
    #                              (val, error_details, msg))

    for key, (val, line, cnt) in six.iteritems(rc_temp):
        if key in defaultParams:
            if fail_on_error:
                config[key] = val  # try to convert to proper type or raise
            else:
                try:
                    config[key] = val  # try to convert to proper type or skip
                except Exception as msg:
                    error_details = _error_details_fmt % (cnt, line, fname)
                    warnings.warn('Bad val "%s" on %s\n\t%s' %
                                  (val, error_details, msg))
        elif key in _deprecated_ignore_map:
            warnings.warn('%s is deprecated. Update your davitpyrc to use '
                          '%s instead.' % (key, _deprecated_ignore_map[key]))

        else:
            print("""
                  Bad key "%s" on line %d in %s. You probably need to get an 
                  updated davitpyrc file from https://github.com/vtsuperdarn/davitpy
                  """ % (key, cnt, fname), file=sys.stderr)

    return config


def rc_params_from_file(fname, fail_on_error=False, use_default_template=True):
    """Return :class:`davitpy.RcParams` from the contents of the given file.
    Parameters
    ----------
    fname : str
        Name of file parsed for matplotlib settings.
    fail_on_error : bool
        If True, raise an error when the parser fails to convert a parameter.
    use_default_template : bool
        If True, initialize with default parameters before updating with those
        in the given file. If False, the configuration class only contains the
        parameters specified in the file. (Useful for updating dicts.)
    """
    config_from_file = _rc_params_in_file(fname, fail_on_error)

    if not use_default_template:
        return config_from_file

    iter_params = six.iteritems(defaultParams)
    config = RcParams([(key, default) for key, (default, _) in iter_params
                                      if key not in _all_deprecated])
    config.update(config_from_file)

    #verbose.set_level(config['verbose.level'])
    #verbose.set_fileo(config['verbose.fileo'])

    #if config['datapath'] is None:
    #    config['datapath'] = get_data_path()

    print('loaded rc file %s' % fname)

    return config


rcParams = rc_params()


#TO DO
#Change these try: excepts to trigger on proper exception, ie) except importError

try: from davitpy import pydarn
except Exception, e: 
  print('problem importing pydarn: ', e)

try: from davitpy import gme 
except Exception, e: 
  print('problem importing gme: ', e)

try: from davitpy import utils 
except Exception, e: 
  print('problem importing utils: ', e)

try: from davitpy import models 
except Exception, e: 
  print('problem importing models: ', e)

