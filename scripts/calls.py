import time


class Fooer(object):
    def foo(i):
        pass
        # print(i)


print(time.time())

acc = 0
for i in range(1000000):
    Fooer.foo(i)

print(time.time())
