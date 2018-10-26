import time
import tensorflow
import sys


if len(sys.argv) > 1:
    num = int(sys.argv[1])
else:
    num = 2_000


class Fooer(object):
    def static_foo(i):
        pass

    def method_foo(self, i):
        pass


builtin_foo = time.time
try:
    package_foo = tensorflow.keras.layers.Flatten
except:
    def package_foo():
        pass
f = Fooer()

print(time.time())

acc = 0
for i in range(num):
    builtin_foo()
    Fooer.static_foo(i)
    f.method_foo(i)
    # package_foo()

print(time.time())
