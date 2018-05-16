#!/usr/bin/env python3

import unittest

from test_hier_config.root import TestHierarchicalConfigurationRoot
from test_text_match import TestTextMatch


def all_tests():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestHierarchicalConfigurationRoot))
    suite.addTest(unittest.makeSuite(TestTextMatch))

    return suite

all_tests()
