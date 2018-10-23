import time


def foo(i):
    pass
    # print(i)


print(time.time())

acc = 0
for i in range(100000):
    foo(i)

print(time.time())
