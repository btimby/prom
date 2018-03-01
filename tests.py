import unittest
import signal
import types

from os.path import exists as pathexists

import prom


def _dummy(*args):
    pass


class PromInstallTestCase(unittest.TestCase):
    def setUp(self):
        prom.install()

    def tearDown(self):
        prom.uninstall()

    def test_install(self):
        handler = signal.signal(prom.SIG_DEFAULT, _dummy)
        self.assertIsInstance(handler, types.MethodType)
        self.assertIsInstance(handler.__self__, prom.PromDump)


class PromDumpFileTestCase(unittest.TestCase):
    def test_dump(self):
        d = prom.PromDump().dump()

        self.assertIsNotNone(d.graph)
        self.assertTrue(pathexists(d.path))


if __name__ == '__main__':
    unittest.main()
