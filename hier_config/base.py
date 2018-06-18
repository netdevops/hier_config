from hier_config.text_match import TextMatch


class HConfigBase:

    def __init__(self):
        self.children = []
        self.children_dict = {}

    def add_children(self, lines):
        """
        Add child instances of HConfigChild

        :param lines: HConfigChild object -> type list
        :return: None

        """

        if isinstance(lines, str):
            lines = [lines]

        for line in lines:
            self.add_child(line)

    def add_child(self, text, alert_on_duplicate=False, idx=None, force_duplicate=False):
        """ Add a child instance of HConfigChild """

        if idx is None:
            idx = len(self.children)
        # if child does not exist
        if text not in self:
            from hier_config.hc_child import HConfigChild
            new_item = HConfigChild(self, text)
            self.children.insert(idx, new_item)
            self.children_dict[text] = new_item
            return new_item
        # if child does exist and is allowed to be installed as a duplicate
        elif self._duplicate_child_allowed_check() or force_duplicate:
            from hier_config.hc_child import HConfigChild
            new_item = HConfigChild(self, text)
            self.children.insert(idx, new_item)
            self.rebuild_children_dict()
            return new_item
        else:
            # If the child is already present and the parent does not allow
            # duplicate children, return the existing child
            # Ignore duplicate remarks in ACLs
            if alert_on_duplicate and not text.startswith('remark '):
                if self is self.root:
                    path = [text]
                else:
                    path = list(self.path()) + [text]
                self.logs.append("Found a duplicate section: {}".format(path))
            return self.get_child('equals', text)

    def add_deep_copy_of(self, child_to_add, merged=False):
        """
        Add a nested copy of a child to self

        :param child_to_add: type HConfigCHild
        :param merged: type boolean, default False

        :return: new_child

        """

        new_child = self.add_shallow_copy_of(child_to_add, merged=merged)
        for child in child_to_add.children:
            new_child.add_deep_copy_of(child, merged=merged)

        return new_child

    def all_children_sorted_untagged(self):
        """ Yield all children recursively that are untagged """

        for child in self.all_children_sorted():
            if not child.tags:
                yield child

    def all_children_sorted_by_tags(self, include_tags, exclude_tags):
        """ Yield all children recursively that match include/exlcude tags """

        for child in self.all_children_sorted():
            if child.line_inclusion_test(include_tags, exclude_tags):
                yield child

    def all_children_sorted(self):
        """ Recursively find and yield all children sorted at each hierarchy """

        for child in sorted(self.children):
            yield child
            for sub_child in child.all_children_sorted():
                yield sub_child

    def all_children(self):
        """ Recursively find and yield all children """

        for child in self.children:
            yield child
            for sub_child in child.all_children():
                yield sub_child

    def get_child(self, test, expression):
        """ Find a child by TextMatch rule. If it is not found, return None """

        if test == 'equals':
            return self.children_dict.get(expression, None)
        else:
            try:
                return next(self.get_children(test, expression))
            except StopIteration:
                return None

    def get_child_deep(self, test_expression_pairs):
        """
        Find a child recursively with a list of test/expression pairs

        e.g.

        .. code:: python

            result = hier_obj.get_child_deep([('equals', 'control-plane'),
                                              ('equals', 'service-policy input system-cpp-policy')])

        Returns:

            HConfigChild or None

        """

        test, expression = test_expression_pairs.pop(0)
        if test == 'equals':
            result = self.children_dict.get(expression, None)
            if result and test_expression_pairs:
                return result.get_child_deep(test_expression_pairs)
            return result
        else:
            try:
                result = next(self.get_children(test, expression))
                if result and test_expression_pairs:
                    return result.get_child_deep(test_expression_pairs)
                return result
            except StopIteration:
                return None

    def get_children(self, test, expression):
        """ Find all children matching a TextMatch rule and return them. """

        for child in self.children:
            if TextMatch.dict_call(test, child.text, expression):
                yield child

    def add_shallow_copy_of(self, child_to_add, merged=False):
        """ Add a nested copy of a child_to_add to self.children """

        new_child = self.add_child(child_to_add.text)

        if merged:
            new_child.instances.append({
                'hostname': child_to_add.host.hostname,
                'comments': child_to_add.comments,
                'tags': child_to_add.tags})
        new_child.comments.update(child_to_add.comments)
        new_child.tags.update(child_to_add.tags)
        new_child.order_weight = child_to_add.order_weight

        return new_child

    def rebuild_children_dict(self):
        """ Rebuild self.children_dict """

        self.children_dict = {}
        for child in self.children:
            self.children_dict[child.text] = self.children_dict.get(
                child.text, child)

    def lineage_test(self, rule, strip_negation=False):
        """ A generic test against a lineage of HConfigChild objects """

        if 'match_leaf' in rule and rule['match_leaf']:
            # stupid trick to make a generator with one item
            lineage_obj = (self for _ in [None])
            lineage_depth = 1
        else:
            lineage_obj = self.lineage()
            lineage_depth = self.depth()

        if not len(rule['lineage']) == lineage_depth:
            return False

        matches = 0

        for lineage_rule, section in zip(rule['lineage'], lineage_obj):
            object_rules, text_match_rules = self._explode_lineage_rule(
                lineage_rule)

            if not self._lineage_eval_object_rules(
                    object_rules, section):
                return False

            # This removes negations for each section but honestly,
            # we really only need to do this on the last one
            if strip_negation:
                if section.text.startswith('no '):
                    text = section.text[3:]
                elif section.text.startswith('default '):
                    text = section.text[8:]
                else:
                    text = section.text
            else:
                text = section.text

            if self._lineage_eval_text_match_rules(
                    text_match_rules, text):
                matches += 1
                continue
            else:
                return False

        return matches == len(rule['lineage'])

    def _duplicate_child_allowed_check(self):
        """ Determine if duplicate(identical text) children are allowed under the parent """

        for rule in self.options[
                'parent_allows_duplicate_child']:
            if self.lineage_test(rule):
                return True
        return False

    @staticmethod
    def _lineage_eval_text_match_rules(rules, text):
        """
        Evaluate a list of lineage text_match rules.

        Only one text_match rule must match in order to return True

        """

        for rule in rules:
            if TextMatch.dict_call(rule['test'], text, rule['expression']):
                return True
        return False

    @staticmethod
    def _explode_lineage_rule(rule):
        text_match_rules = list()
        object_rules = list()
        for k, v in rule.items():
            if k in ['new_in_config', 'negative_intersection_tags']:
                object_rules.append({'test': k, 'expression': v})
            elif isinstance(v, list):
                text_match_rules += [{'test': k, 'expression': e} for e in v]
            else:
                text_match_rules += [{'test': k, 'expression': v}]
        return object_rules, text_match_rules
