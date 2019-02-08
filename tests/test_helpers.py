import unittest


class TestHelpers(unittest.TestCase):

    def test_to_list(self):
        from hier_config.helpers import to_list
        self.assertEqual(to_list({1, 2, 3}), [1, 2, 3])
        self.assertEqual(to_list((1, 2, 3)), [1, 2, 3])
        self.assertEqual(to_list([1, 2, 3]), [1, 2, 3])
        self.assertEqual(to_list(x for x in [1, 2, 3]), [1, 2, 3])
        self.assertEqual(to_list(None), [None])
        self.assertEqual(to_list(''), [])
        self.assertEqual(to_list([]), [])
        self.assertEqual(to_list(False), [])
        self.assertEqual(to_list('asdf'), ['asdf'])
