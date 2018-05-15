import re


class TextMatch(object):
    """
    Provides a suite of text matching methods
    """

    @classmethod
    def dict_call(cls, test, text, expression):
        """
        Allows test methods to be called easily from variables
        """
        return {
            'equals': cls.equals,
            'startswith': cls.startswith,
            'endswith': cls.endswith,
            'contains': cls.contains,
            're_search': cls.re_search,
            'contains_or_endswith': cls.contains_or_endswith,
            'anything': cls.anything,
            'nothing': cls.nothing
        }[test](text, expression)

    @staticmethod
    def equals(text, expression):
        """Text equivalence test"""
        if isinstance(expression, str):
            return text == expression
        else:
            return text in expression

    @staticmethod
    def startswith(text, expression):
        """Text starts with test"""
        return text.startswith(expression)

    @staticmethod
    def endswith(text, expression):
        """Text ends with test"""
        return text.endswith(expression)

    @staticmethod
    def contains(text, expression):
        """Text contains test"""
        return expression in text

    @staticmethod
    def anything(text, expression):
        """Always returns True"""
        return True

    @staticmethod
    def nothing(text, expression):
        """Always returns False"""
        return False

    @staticmethod
    def contains_or_endswith(text, expression, with_pad=False):
        """Text contains test"""
        if with_pad:
            if TextMatch.endswith(text, ' {}'.format(expression)):
                return True
            elif TextMatch.contains(text, ' {} '.format(expression)):
                return True
        else:
            if TextMatch.endswith(text, expression):
                return True
            elif TextMatch.contains(text, expression):
                return True
        return False

    @staticmethod
    def re_search(text, expression):
        """
        Test regex match. This method is comparatively
        very slow and should be avoided where possible.
        """
        return re.search(expression, text) is not None
