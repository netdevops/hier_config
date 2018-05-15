import unittest

from hier_config.text_match import TextMatch


class TestTextMatch(unittest.TestCase):

    def setUp(self):
        self.text_match = TextMatch()
        self.text = '  ip address 192.168.100.1/24'
        self.expression1 = self.text
        self.expression2 = '  ip address'
        self.expression3 = 'ip access-list'
        self.expression4 = '/30'

    def test_equals(self):
        self.assertTrue(self.text_match.equals(
            text=self.text,
            expression=self.expression1)
        )
        self.assertFalse(self.text_match.equals(
            text=self.text,
            expression=self.expression2)
        )

    def test_startswith(self):
        o = self.text_match.startswith(self.text, self.expression2)
        self.assertTrue(self.text_match.startswith(
            text=self.text,
            expression=self.expression2)
        )
        self.assertFalse(self.text_match.startswith(
            text=self.text,
            expression=self.expression3)
        )

    def test_endswith(self):
        self.assertTrue(self.text_match.endswith(
            text=self.text,
            expression=self.expression1)
        )
        self.assertFalse(self.text_match.endswith(
            text=self.text,
            expression=self.expression4)
        )

    def test_contains(self):
        self.assertTrue(self.text_match.contains(
            text=self.text,
            expression=self.expression2)
        )
        self.assertFalse(self.text_match.contains(
            text=self.text,
            expression=self.expression3)
        )

    def test_re_search(self):
        self.assertTrue(self.text_match.re_search(
            text=self.text,
            expression=self.expression2)
        )
        self.assertFalse(self.text_match.re_search(
            text=self.text,
            expression=self.expression3)
        )

    def test_contains_or_endswith(self):
        self.assertTrue(self.text_match.contains_or_endswith(
            text=self.text,
            expression=self.expression1)
        )
        self.assertFalse(self.text_match.contains_or_endswith(
            text=self.text,
            expression=self.expression4)
        )

    def test_anything(self):
        self.assertTrue(self.text_match.anything(
            text=self.text,
            expression=self.expression1)
        )
        self.assertTrue(self.text_match.anything(
            text=self.text,
            expression=self.expression2)
        )

    def test_nothing(self):
        self.assertFalse(self.text_match.nothing(
            text=self.text,
            expression=self.expression1)
        )
        self.assertFalse(self.text_match.nothing(
            text=self.text,
            expression=self.expression2)
        )
        self.assertFalse(self.text_match.nothing(
            text=self.text,
            expression=self.expression3)
        )
        self.assertFalse(self.text_match.nothing(
            text=self.text,
            expression=self.expression4)
        )

if __name__ == "__main__":
    unittest.main()
