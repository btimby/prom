"""PROfile Memory."""

import gc
import logging
import os
import sys
import signal
import time
import tempfile
import textwrap
import pickle

from os.path import exists as pathexists
from os.path import join as pathjoin

from docopt import docopt, DocoptExit
from schema import Schema, SchemaError


LOGGER = logging.getLogger(__name__)
FILE_NAME_TEMPLATE = '%(name)s-%(pid)i-%(ts)s.prom'
PATH_DEFAULT = tempfile.gettempdir()
SIG_DEFAULT = signal.SIGUSR1


def get_process_info():
    info = {
        'ts': time.time(),
        'pid': os.getpid(),
        'name': sys.argv[0],
    }
    return info


def install(sig=SIG_DEFAULT, **kwargs):
    """Installs the PromDump signal handler."""
    dump = PromDump(**kwargs)
    dump.install(sig)


def uninstall(sig=SIG_DEFAULT):
    """Reverts signal handler to the default."""
    signal.signal(sig, signal.SIG_DFL)


def obj_dump(obj):
    return str(obj)


class PromDump(object):
    def __init__(self, path=PATH_DEFAULT, name_template=FILE_NAME_TEMPLATE):
        self.path = path
        self.name_template = name_template

    def _handler(self, sig, *args):
        LOGGER.info('Received signal: %i, dumping', sig)
        try:
            self.dump()
        except Exception as e:
            LOGGER.exception(e)

    def install(self, sig=signal.SIGUSR1):
        LOGGER.info('Installing signal handler for signal: %i', sig)
        signal.signal(sig, self._handler)

    def dump(self):
        info = get_process_info()
        file_name = pathjoin(self.path, self.name_template % info)
        d = PromDumpFile(file_name)
        d.write()
        return d


class PromDumpFile(object):
    def __init__(self, path):
        self.path = path
        self.stats = None
        self.graph = None

    def load(self):
        LOGGER.debug('Loading memory graph from: %s', self.path)
        with open(self.path, 'rb') as f:
            self.stats, self.graph = pickle.load(f)

    def write(self):
        assert not pathexists(self.path), 'cannot overwrite %s' % self.path
        if self.graph is None:
            self.gather()

        LOGGER.debug('Saving memory graph to: %s', self.path)
        with open(self.path, 'wb') as f:
            pickle.dump((self.stats, self.graph), f)

    def gather(self):
        """Perform a GC and build memory graph."""
        LOGGER.debug('Forcing GC colection')
        gc.collect()

        # Attempt to log some GC stats.
        try:
            self.stats = gc.get_stats()

        except AttributeError:
            # get_stats() only exists in Python 3.4+, so we can continue
            # without stats if the function does not exist.
            pass

        LOGGER.debug('Gathering memory graph')
        objs = gc.get_objects()

        self.graph = {}
        for obj in objs:
            node = (
                obj_dump(obj),
                # Approximation:
                sys.getsizeof(obj),
                [id(o) for o in gc.get_referents(obj)],
                [id(o) for o in gc.get_referrers(obj)],
            )
            self.graph[id(obj)] = node

    def report(self, f=None):
        assert self.graph is not None, 'no memory graph'
        f = f or sys.stdout

        if self.stats is not None:
            f.write('Collection statitstics\n')
            for i, s in enumerate(self.stats):
                f.write('%i: %s\n' % (i, s))
            f.write('\n')

        f.write('Object graph\n')
        for i, (id, node) in enumerate(self.graph.items()):
            if i % 100 == 0:
                f.write('ID\tObject\n')
            obj, referents, referrers = node
            f.write('%i\t%s\n' % (id, obj))


def main(argv):
    """
    PROM - PROfile Memory.

    Usage:
        python -m prom <path>

    Options:
        <path>   The path to the prom dump file.
    """
    opt = docopt(textwrap.dedent(main.__doc__), argv)

    try:
        opt = Schema({
            '<path>': pathexists,
        }).validate(opt)

    except SchemaError as e:
        raise DocoptExit(e.args[0])

    d = PromDumpFile(opt['<path>'])
    d.report()


if __name__ == '__main__':
    main(sys.argv)
