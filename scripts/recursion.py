import sys
import time

if len(sys.argv) > 1:
   depth = int(sys.argv[1])
else:
   depth = 6

def foo(i):
    if i >= 2:
        foo(i-2)
    if i >= 1:
        foo(i-1)

print(time.time())

foo(depth)

print(time.time())
