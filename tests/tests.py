#!/usr/bin/env python

import unittest
import sys


def all_tests():
    from test_pep8 import TestPep8
    from test_host import TestHost
    from test_hier_config import TestHConfig
    from test_text_match import TestTextMatch
    from test_helpers import TestHelpers

    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPep8))
    suite.addTest(unittest.makeSuite(TestHost))
    suite.addTest(unittest.makeSuite(TestHConfig))
    suite.addTest(unittest.makeSuite(TestTextMatch))
    suite.addTest(unittest.makeSuite(TestHelpers))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    status = runner.run(all_tests())

    if status.failures or status.errors:
        sys.exit(1)
    else:
        sys.exit(0)
