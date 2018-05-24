#!/usr/bin/env python

import unittest


def all_tests():
    from test_hier_config import TestHConfig
    from test_text_match import TestTextMatch

    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestHConfig))
    suite.addTest(unittest.makeSuite(TestTextMatch))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(all_tests())
