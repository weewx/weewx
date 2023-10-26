#
#      Copyright (c) 2019-2021 Tom Keffer <tkeffer@gmail.com>
#
#      See the file LICENSE.txt for your full rights.
#

#
#
#    See the file LICENSE.txt for your rights.
#
"""Register a minimal subparser for purposes of providing a response to 'weectl --help'. """


def add_subparser(subparsers):
    subparsers.add_parser('device', help="Manage your hardware.")
