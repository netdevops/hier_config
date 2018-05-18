#!/usr/bin/env python3

import unittest


def all_tests():
    from test_hier_config import TestHierarchicalConfigurationRoot
    from test_text_match import TestTextMatch

    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestHierarchicalConfigurationRoot))
    suite.addTest(unittest.makeSuite(TestTextMatch))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    runner.run(all_tests())
