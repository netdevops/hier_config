import os
import pep8
import unittest


class TestPep8(unittest.TestCase):

    def test_pep8(self):
        style = pep8.StyleGuide()
        style.options.ignore += ('E501',)
        errors = 0
        python_files = set()

        for root, dirs, files in os.walk('hier_config'):
            for f in files:
                if os.path.isfile(os.path.join(root, f)):
                    if f.endswith('.py'):
                        python_files.add(os.path.join(root, f))
            errors += style.check_files(python_files).total_errors

        self.assertEqual(errors, 0, 'PEP8 style errors: {}'.format(errors))


if __name__ == "__main__":
    unittest.main(failfast=True)
