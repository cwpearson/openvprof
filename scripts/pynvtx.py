#! /usr/bin/env python3

import sys
import os
import time
import logging
import ctypes

logging.basicConfig()
logger = logging.getLogger("pynvtx")
logger.setLevel(logging.DEBUG)


# https://docs.python.org/2/library/sys.html#sys.setprofile
# https://docs.python.org/2/library/inspect.html

try:
    import threading
except ImportError:
    _settrace = sys.setprofile

    def _unsettrace():
        sys.setprofile(None)
else:
    def _settrace(func):
        threading.setprofile(func)
        sys.setprofile(func)

    def _unsettrace():
        sys.setprofile(None)
        threading.setprofile(None)


# load the nvToolsExt library
NVTOOLSEXT_PATHS = [
    'libnvToolsExt.dylib',
    'libnvToolsExt.so',
    '/usr/local/cuda/lib/libnvToolsExt.dylib',
    '/usr/local/cuda/lib/libnvToolsExt.so',
]


lib = None
for path in NVTOOLSEXT_PATHS:
    try:
        lib = ctypes.cdll.LoadLibrary(path)
    except OSError as e:
        logger.debug(
            "failed to load Nvidia Tools Extensions from {}".format(path))
        lib = None
    else:
        logger.info("loaded Nvidia Tools Extensions from {}".format(path))
        break

if lib:
    def _nvtxRangePush(s):
        lib.nvtxRangePushA(ctypes.c_char_p(str.encode(s)))

    def _nvtxRangePop():
        lib.nvtxRangePop()
else:
    logger.error("couldn't load any of {}".format(NVTOOLSEXT_PATHS))

    def _nvtxRangePush(_): pass

    def _nvtxRangePop(): pass


def tracefunc(frame, event, arg):
    if event == "call":
        name = frame.f_code.co_name
        # don't record call of _unsettrace (won't see exit)
        if name == "_unsettrace":
            return tracefunc
        _nvtxRangePush(frame.f_code.co_name)
    elif event == "return":
        name = frame.f_code.co_name
        # don't record exit of _settrace (won't see call)
        if name == "_settrace":
            return tracefunc
        _nvtxRangePop()
    return tracefunc


def runctx(cmd, globals=None, locals=None):
    if globals is None:
        globals = {}
    if locals is None:
        locals = {}
    _settrace(tracefunc)
    try:
        exec(cmd, globals, locals)
    finally:
        _unsettrace()


def main():
    prog_argv = sys.argv[1:]
    sys.argv = prog_argv
    progname = prog_argv[0]
    sys.path[0] = os.path.split(progname)[0]

    try:
        with open(progname) as fp:
            code = compile(fp.read(), progname, 'exec')
            # try to emulate __main__ namespace as much as possible
            globs = {
                '__file__': progname,
                '__name__': '__main__',
                '__package__': None,
                '__cached__': None,
            }
            runctx(code, globs, globs)
    except IOError as err:
        logger.critical(
            "Cannot add nvToolsExt ranges to python file %r because: %s" % (sys.argv[0], err))
        sys.exit(1)
    except SystemExit:
        pass


if __name__ == '__main__':
    main()
