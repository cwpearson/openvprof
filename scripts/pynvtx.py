#! /usr/bin/env python3

import sys
import os
import time
import logging
import ctypes
import inspect
import traceback

logging.basicConfig()
logger = logging.getLogger("pynvtx")
logger.setLevel(logging.WARN)

DEPTH_LIMIT = None

# https://docs.python.org/2/library/sys.html#sys.setprofile
# https://docs.python.org/2/library/inspect.html
# https://gist.github.com/techtonik/2151727

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

# load the nvToolsExt library
LIBCUDART_PATHS = [
    'libcudart.dylib',
    'libcudart.so',
    '/usr/local/cuda/lib/libcudart.dylib',
    '/usr/local/cuda/lib/libcudart.so',
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


libcudart = None
for path in LIBCUDART_PATHS:
    try:
        libcudart = ctypes.cdll.LoadLibrary(path)
    except OSError as e:
        logger.debug(
            "failed to load CUDA Runtime from {}".format(path))
        libcudart = None
    else:
        logger.info("loaded CUDA Runtime from {}".format(path))
        break


def get_static_class(frame):
    """return the class name of a call frame in a static method"""
    # look in the parent stack frame for a line of code that looks like a static method definition, and use that if found
    function_name = frame.f_code.co_name
    stack_summary = traceback.extract_stack(frame)
    line = stack_summary[-2][3]
    class_end_idx = line.find("."+function_name+"(")
    if class_end_idx == -1:
        class_name = None
    else:
        class_name = line[0:class_end_idx]
    return class_name


def get_method_class(frame):
    """return the class name of 'self', or None"""
    # check the class of the self variable if it exists
    try:
        class_name = frame.f_locals['self'].__class__.__name__
    except KeyError:
        class_name = None
    return class_name


def tracefunc(frame, event, arg, depth=[0]):
    # if event == "c_call":
    #     # arg is the c function object
    #     print("C CALL")
    #     depth[0] += 1
    #     if DEPTH_LIMIT and depth[0] > DEPTH_LIMIT:
    #         return tracefunc
    #     function_name = arg.__name__
    #     # print(function_name)
    #     print(inspect.getmodule(arg))
    if event == "call":
        # arg is none
        name = []
        # print("CALL")
        module = inspect.getmodule(frame)
        # print(inspect.getmembers(module))

        if module:
            name.append(module.__name__)
        else:
            return tracefunc
        if 'self' in frame.f_locals:
            # I don't know any way to detect call from the object method
            # XXX: there seems to be no way to detect static method call - it will
            #      be just a function call
            name.append(frame.f_locals['self'].__class__.__name__)
        codename = frame.f_code.co_name
        if codename != '<module>':  # top level usually
            name.append(codename)  # function or a method
        print(depth[0] * " " + ".".join(name))
        depth[0] += 1
        if DEPTH_LIMIT and depth[0] > DEPTH_LIMIT:
            return tracefunc
        filename, lineno, function_name, code_context, index = inspect.getframeinfo(
            frame)
        # function_name = frame.f_code.co_name
        # print(inspect.getmodule(frame))
        if filename[-3:] != ".py":
            return tracefunc
        # print(filename)
        # print(inspect.getmodulename(filename))
        # print(inspect.getmodule(function))
        file_name = frame.f_code.co_filename
        # don't record call of _unsettrace (won't see exit)
        if function_name == "_unsettrace":
            return tracefunc
        #filename, lineno, function, code_context, index = inspect.getframeinfo(frame)
        range_name = file_name + "::" + function_name
        # logger.debug(range_name)
        _nvtxRangePush(range_name)
    # elif event == "c_return":
    #     # arg is the c function object
    #     frame_depth = depth[0]
    #     depth[0] -= 1
    #     if DEPTH_LIMIT and depth[0] > DEPTH_LIMIT:
    #         return tracefunc
    elif event == "return":
        frame_depth = depth[0]
        depth[0] -= 1
        if DEPTH_LIMIT and depth[0] > DEPTH_LIMIT:
            return tracefunc
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


class Tracer(object):
    def __init__(self, progname, prog_argv, depth=None):
        self.prog_name = progname
        self.prog_argv = prog_argv
        self.depth = depth
        self.libnvtoolsext = None
        self.libcudart = None
        # load the nvToolsExt and cudart libraries
        NVTOOLSEXT_PATHS = [
            'libnvToolsExt.dylib',
            'libnvToolsExt.so',
            '/usr/local/cuda/lib/libnvToolsExt.dylib',
            '/usr/local/cuda/lib/libnvToolsExt.so',
        ]
        for path in NVTOOLSEXT_PATHS:
            try:
                self.libnvtoolsext = ctypes.cdll.LoadLibrary(path)
            except OSError as e:
                logger.debug(
                    "failed to load Nvidia Tools Extensions from {}".format(path))
                self.libnvtoolsext = None
            else:
                logger.info(
                    "loaded Nvidia Tools Extensions from {}".format(path))
                break
        CUDART_PATHS = [
            'libcudart.dylib',
            'libcudart.so',
            '/usr/local/cuda/lib/libcudart.dylib',
            '/usr/local/cuda/lib/libcudart.so',
        ]
        for path in CUDART_PATHS:
            try:
                self.libcudart = ctypes.cdll.LoadLibrary(path)
            except OSError as e:
                logger.debug(
                    "failed to load CUDA Runtime from {}".format(path))
                self.libcudart = None
            else:
                logger.info(
                    "loaded CUDA Runtime from {}".format(path))
                break

        if self.libnvtoolsext:
            def _nvtxRangePush(self, s):
                self.libnvtoolsext.nvtxRangePushA(
                    ctypes.c_char_p(str.encode(s)))

            def _nvtxRangePop(self):
                self.libnvtoolsext.nvtxRangePop()
        else:
            logger.error("couldn't load any of {}".format(NVTOOLSEXT_PATHS))

            def _nvtxRangePush(self, _): pass

            def _nvtxRangePop(self): pass


def main():

    import argparse

    parser = argparse.ArgumentParser(
        description='Add Nvidia Tools Extensions ranges to python functions')
    parser.add_argument('--depth', type=int,
                        help='only push ranges to this stack depth')
    parser.add_argument('--debug', action='store_true',
                        help='print debug messages')
    parser.add_argument('--verbose', action='store_true',
                        help='print verbose messages')
    parser.add_argument('commands', nargs='+', help='commands help')

    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    if args.verbose:
        logger.setLevel(logging.INFO)
    if args.depth:
        if args.depth < 0:
            logger.critical('trace depth must be >=0')
            sys.exit(1)
        else:
            DEPTH_LIMIT = args.depth

    prog_argv = args.commands
    logger.debug("Tracing python argv[:] {}".format(prog_argv))
    sys.argv = prog_argv
    progname = prog_argv[0]
    sys.path[0] = os.path.split(progname)[0]

    t = Tracer(progname, prog_argv, depth=args.depth)

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
