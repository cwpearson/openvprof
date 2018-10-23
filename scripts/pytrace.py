import sys
import os
import time

from ctypes import cdll
import ctypes

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

lib = None
for path in [
    'libnvToolsExt.dylib',
    '/usr/local/cuda/lib/libnvToolsExt.dylib',
    'libnvToolsExt.so',
    '/usr/local/cuda/lib/libnvToolsExt.so',
]:
    try:
        lib = cdll.LoadLibrary(path)
    except OSError as e:
        print("unable to load {}: {}".format(path, e), file=sys.stderr)
        lib = None
    else:
        print("loaded {}".format(path), file=sys.stderr)
    if lib:
        break


def _nvtxRangePush(s):
    if lib:
        lib.nvtxRangePushA(ctypes.c_char_p(str.encode(s)))


def _nvtxRangePop():
    if lib:
        lib.nvtxRangePop()


records = []


def tracefunc(frame, event, arg):
    ts = time.time()
    hs = hash(frame)
    if event == "call":
        records.append(('call', frame.f_code.co_name, ts, hs))
        _nvtxRangePush("test")
        # print("-" * indent[0] + "> call function",
        #       frame.f_code.co_name, int(time.time() * 1e9), hash(frame))
    elif event == "return":
        _nvtxRangePop()
        records.append(('exit', frame.f_code.co_name, ts, hs))
        # print("<" + "-" * indent[0], "exit function",
        #       frame.f_code.co_name, int(time.time() * 1e9), hash(frame))
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


def _err_exit(msg):
    sys.stderr.write("%s: %s\n" % (sys.argv[0], msg))
    sys.exit(1)


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
        _err_exit("Cannot run file %r because: %s" % (sys.argv[0], err))
    except SystemExit:
        pass

    with open('pytrace.csv', 'w') as fp:
        for r in records:
            fp.write(",".join([str(e) for e in r])+'\n')


if __name__ == '__main__':
    main()
