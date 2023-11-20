#
#    Copyright (c) 2009-2023 Tom Keffer <tkeffer@gmail.com> and Matthew Wall
#
#    See the file LICENSE.txt for your rights.
#
class Printer(object):
    def __init__(self, verbosity=0, fd=None):
        self.verbosity = verbosity
        if fd is None:
            import sys
            fd = sys.stdout
        self.fd = fd

    def out(self, msg, level=0):
        if self.verbosity >= level:
            print("%s%s" % ('  ' * (level - 1), msg), file=self.fd)
