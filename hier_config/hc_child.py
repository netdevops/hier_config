from hier_config.text_match import TextMatch

import hier_config.helpers as H


class HConfigChild:

    def __init__(self, parent, text):
        self.parent = parent
        self._text = text.strip()
        self.hostname = self.root.hostname
        self.os = self.root.os
        self.options = self.root.options
        self.real_indent_level = None
        self.children = []
        self.children_dict = {}
        # The intent is for self.order_weight values to range from 1 to 999
        # with the default weight being 500
        self.order_weight = 500
        self.tags = set()
        self.comments = set()
        self.new_in_config = False
        self.instances = []

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        """
        Used for when self.text is changed after the object
        is instantiated to rebuild the children dictionary

        """

        self._text = value.strip()
        self.parent.rebuild_children_dict()

    def __repr__(self):
        if self.parent is self.root:
            return 'HConfigChild(HConfig, {})'.format(self.text)
        else:
            return 'HConfigChild(HConfigChild, {})'.format(self.text)

    def __str__(self):
        return self.text

    def __lt__(self, other):
        if self.order_weight < other.order_weight:
            return True
        else:
            return False

    def __len__(self):
        length = 0
        for _ in self.all_children():
            length += 1
        return length

    def __bool__(self):
        return True

    def __contains__(self, item):
        return str(item) in self.children_dict

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        attributes_to_compare = (
            'text',
            'tags',
            'comments',
            'new_in_config',
        )

        for attribute in attributes_to_compare:
            self_attribute = getattr(self, attribute)
            other_attribute = getattr(other, attribute)
            if self_attribute != other_attribute:
                return False

        if len(self.children) != len(other.children):
            return False

        for self_child, other_child in zip(sorted(self.children), sorted(other.children)):
            if self_child != other_child:
                return False

        return True

    @property
    def root(self):
        """ returns the HConfig object at the base of the tree """

        return self.parent.root

    @property
    def logs(self):
        return self.parent.logs

    @property
    def host(self):
        return self.parent.hostname

    @staticmethod
    def _lineage_eval_object_rules(rules, section):
        """
        Evaluate a list of lineage object rules.

        All object rules must match in order to return True

        """

        matches = 0
        for rule in rules:
            if rule['test'] == 'new_in_config':
                if rule['expression'] == section.new_in_config:
                    matches += 1
            elif rule['test'] == 'negative_intersection_tags':
                rule['expression'] = H.to_list(rule['expression'])
                if not set(rule['expression']).intersection(section.tags):
                    matches += 1
        if matches == len(rules):
            return True
        else:
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

    def has_children(self):
        return bool(self.children)

    def depth(self):
        return self.parent.depth() + 1

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
            else:
                return result
        else:
            try:
                result = next(self.get_children(test, expression))
                if result and test_expression_pairs:
                    return result.get_child_deep(test_expression_pairs)
                else:
                    return result
            except StopIteration:
                return None

    def get_children(self, test, expression):
        """ Find all children matching a TextMatch rule and return them. """

        for child in self.children:
            if TextMatch.dict_call(test, child.text, expression):
                yield child

    def move(self, new_parent):
        """
        move one HConfigChild object to different HConfig parent object

        .. code:: python

            hier1 = HConfig(hostname1, os, options)
            interface1 = hier1.add_child('interface Vlan2')
            interface1.add_child('ip address 10.0.0.1 255.255.255.252')

            hier2 = Hconfig(hostname2, os, options)

            interface1.move(hier2)

        :param HConfigChild: list
        :return: None

        """

        new_parent.children.append(self)
        new_parent.rebuild_children_dict()
        self.delete()

    def del_child_by_text(self, text):
        """ Delete all children with the provided text """

        if text in self.children_dict:
            self.children[:] = [c for c in self.children if c.text != text]
            self.rebuild_children_dict()

    def del_child(self, child):
        """
        Delete a child from self.children and self.children_dict

        .. code:: python
            hier = HConfig(hostname, os, options)
            hier.add_child('interface Vlan2')

            hier.del_child(hier.get_child('startswith', 'interface'))

        :param HConfigChild
        :return: None

        """

        try:
            self.children.remove(child)
        except ValueError:
            pass
        else:
            self.rebuild_children_dict()

    def rebuild_children_dict(self):
        """ Rebuild self.children_dict """

        self.children_dict = {}
        for child in self.children:
            self.children_dict[child.text] = self.children_dict.get(
                child.text, child)

    def add_children(self, lines):
        """ Add child instances of HConfigChild """

        for line in lines:
            self.add_child(line)

    def add_child(self, text, alert_on_duplicate=False, idx=None, force_duplicate=False):
        """ Add a child instance of HConfigChild """

        if idx is None:
            idx = len(self.children)
        # if child does not exist
        if text not in self:
            new_item = HConfigChild(self, text)
            self.children.insert(idx, new_item)
            self.children_dict[text] = new_item
            return new_item
        # if child does exist and is allowed to be installed as a duplicate
        elif self._duplicate_child_allowed_check() or force_duplicate:
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
        """ Add a nested copy of a child to self"""

        new_child = self.add_shallow_copy_of(child_to_add, merged=merged)
        for child in child_to_add.children:
            new_child.add_deep_copy_of(child, merged=merged)
        return new_child

    def lineage(self):
        """
        Return the lineage of parent objects, up to but excluding the root

        """

        if self.root is self.parent:
            yield self
        else:
            yield from self.parent.lineage()
            yield self

    def path(self):
        """
        Return a list of the text instance variables from self.lineage

        """

        for obj in self.lineage():
            yield obj.text

    def cisco_style_text(self, style='without_comments', tag=None):
        """ Return a Cisco style formated line i.e. indentation_level + text ! comments """

        comments = []
        if style == 'without_comments':
            pass
        elif style == 'merged':
            # count the number of instances that have the tag
            instance_count = 0
            instance_comments = set()
            for instance in self.instances:
                if tag is None or tag in instance['tags']:
                    instance_count += 1
                    instance_comments.update(instance['comments'])

            # should the word 'instance' be plural?
            word = 'instance' if instance_count == 1 else 'instances'

            comments.append('{} {}'.format(
                instance_count,
                word))
            comments.extend(instance_comments)
        elif style == 'with_comments':
            comments.extend(self.comments)

        return "{}{}{}".format(
            "  " * (self.depth() - 1),  # render the indentation
            self.text,
            ' !{}'.format(', '.join(sorted(comments))) if comments else '')

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
            yield from child.all_children_sorted()

    def all_children(self):
        """ Recursively find and yield all children """

        for child in self.children:
            yield child
            yield from child.all_children()

    def delete(self):
        """ Delete the current object from its parent """

        # TODO find a way to remove this when sub-classing in HCRoot
        self.parent.del_child(self)

    def set_order_weight(self):
        """
        Sets self.order integer on all children

        """

        for child in self.all_children():
            for rule in self.options['ordering']:
                if child.lineage_test(rule):
                    child.order_weight = rule['order']

    def add_sectional_exiting(self):
        """
        Adds the sectional exiting text as a child

        """

        # TODO why do we need to delete the delete the sub_child and then
        # recreate it?
        for child in self.all_children():
            for rule in self.options['sectional_exiting']:
                if child.lineage_test(rule):
                    if rule['exit_text'] in child:
                        child.del_child_by_text(rule['exit_text'])

                    new_child = child.add_child(rule['exit_text'])
                    new_child.order_weight = 999

    def to_tag_spec(self, tags):
        """
        Returns the configuration as a tag spec definition

        This is handy when you have a segment of config and need to
        generate a tag spec to tag configuration in another instance

        """

        tag_spec = []
        for child in self.all_children():
            if not child.children:
                child_spec = [{'equals': t} for t in child.path()]
                tag_spec.append({'section': child_spec, 'add_tags': tags})
        return tag_spec

    def ancestor_append_tags(self, tags):
        """
        Append tags to self.tags and for all ancestors

        """

        for ancestor in self.lineage():
            ancestor.append_tags(tags)

    def ancestor_remove_tags(self, tags):
        """
        Remove tags to self.tags and for all ancestors

        """

        for ancestor in self.lineage():
            ancestor.remove_tags(tags)

    def deep_append_tags(self, tags):
        """
        Append tags to self.tags and recursively for all children

        """

        self.append_tags(tags)
        for child in self.all_children():
            child.append_tags(tags)

    def deep_remove_tags(self, tags):
        """
        Remove tags from self.tags and recursively for all children

        """

        self.remove_tags(tags)
        for child in self.all_children():
            child.remove_tags(tags)

    def append_tags(self, tags):
        """
        Add tags to self.tags

        """

        tags = H.to_list(tags)
        # self._tags.update(tags)
        self.tags.update(tags)

    def remove_tags(self, tags):
        """
        Remove tags from self.tags

        """

        tags = H.to_list(tags)
        # self._tags.difference_update(tags)
        self.tags.difference_update(tags)

    def with_tags(self, tags, new_instance=None):
        """
        Returns a new instance containing only sub-objects
        with one of the tags in tags

        """

        from hier_config import HConfig
        if new_instance is None:
            new_instance = HConfig(
                self.hostname, self.os, self.options)

        for child in self.children:
            if tags.intersection(self.tags):
                new_child = new_instance.add_shallow_copy_of(child)
                child.with_tags(tags, new_instance=new_child)

        return new_instance

    def negate(self):
        """ Negate self.text """

        for rule in self.options['negation_negate_with']:
            if self.lineage_test(rule):
                self.text = rule['use']
                return self

        for rule in self.options['negation_default_when']:
            if self.lineage_test(rule):
                return self._default()

        return self._swap_negation()

    def config_to_get_to(self, target, delta=None):
        """
        Figures out what commands need to be executed to transition from self to target.
        self is the source data structure(i.e. the running_config),
        target is the destination(i.e. compiled_config)

        """

        from hier_config import HConfig
        if delta is None:
            delta = HConfig(
                self.hostname, self.os, self.options)

        self._config_to_get_to_left(target, delta)
        self._config_to_get_to_right(target, delta)

        return delta

    def _config_to_get_to_left(self, target, delta):
        # find self.children that are not in target.children - i.e. what needs to be negated or defaulted
        # Also, find out if another command in self.children will overwrite -
        # i.e. be idempotent
        for self_child in self.children:
            if self_child in target:
                continue
            elif self_child.is_idempotent_command(target.children):
                continue
            else:
                # in other but not self
                # add this node but not any children
                deleted = delta.add_child(self_child.text)
                deleted.negate()
                if self_child.children:
                    deleted.comments.add(
                        f"removes {len(self_child.children_dict) + 1} lines")

    def _config_to_get_to_right(self, target, delta):
        # find what would need to be added to source_config to get to self
        for target_child in target.children:
            # if the child exist, recurse into its children
            self_child = self.get_child('equals', target_child.text)
            if self_child:
                # This creates a new HConfigChild object just in case there are some delta children
                # Not very efficient, think of a way to not do this
                subtree = delta.add_child(target_child.text)
                self_child.config_to_get_to(target_child, subtree)
                if not subtree.children:
                    subtree.delete()
                # Do we need to rewrite the child and its children as well?
                elif self_child.sectional_overwrite_check():
                    target_child.overwrite_with(self_child, delta, True)
                elif self_child.sectional_overwrite_no_negate_check():
                    target_child.overwrite_with(self_child, delta, False)
            # else the child is absent, add it
            else:
                new_item = delta.add_deep_copy_of(target_child)
                # mark the new item and all of its children as new_in_config
                new_item.new_in_config = True
                for child in new_item.all_children():
                    child.new_in_config = True
                if new_item.children:
                    new_item.comments.add("new section")

    def _swap_negation(self):
        """ Swap negation of a self.text """

        if self.text.startswith('no '):
            self.text = self.text[3:]
        else:
            self.text = 'no ' + self.text
        return self

    def _default(self):
        """ Default self.text """

        if self.text.startswith('no '):
            self.text = 'default ' + self.text[3:]
        else:
            self.text = 'default ' + self.text
        return self

    def _idempotent_acl_check(self):
        """
        Handle conditional testing to determine if idempotent acl handling for iosxr should be used

        """

        if self.os in {'iosxr'}:
            if self.parent is not self.root:
                acl = ('ipv4 access-list ', 'ipv6 access-list ')
                if self.parent.text.startswith(acl):
                    return True
        return False

    def is_idempotent_command(self, other_children):
        """
        Determine if self.text is an idempotent change.

        """

        # Blacklist commands from matching as idempotent
        for rule in self.options[
                'idempotent_commands_blacklist']:
            if self.lineage_test(rule, True):
                return False

        # Handles idempotent acl entry identification
        if self._idempotent_acl_check():
            if self.os in {'iosxr'}:
                self_sn = self.text.split(' ', 1)[0]
                for other_child in other_children:
                    other_sn = other_child.text.split(' ', 1)[0]
                    if self_sn == other_sn:
                        return True

        # Idempotent command identification
        for rule in self.options['idempotent_commands']:
            if self.lineage_test(rule, True):
                for other_child in other_children:
                    if other_child.lineage_test(rule, True):
                        return True

        return False

    def sectional_overwrite_no_negate_check(self):
        """
        Check self's text to see if negation should be handled by
        overwriting the section without first negating it

        """

        for rule in self.options[
                'sectional_overwrite_no_negate']:
            if self.lineage_test(rule):
                return True
        return False

    def sectional_overwrite_check(self):
        """ Determines if self.text matches a sectional overwrite rule """

        for rule in self.options['sectional_overwrite']:
            if self.lineage_test(rule):
                return True
        return False

    def overwrite_with(self, other, delta, negate=True):
        """ Deletes delta.child[self.text], adds a deep copy of self to delta """

        if other.children != self.children:
            if negate:
                delta.del_child_by_text(self.text)
                deleted = delta.add_child(self.text).negate()
                deleted.comments.add("dropping section")
            if self.children:
                delta.del_child_by_text(self.text)
                new_item = delta.add_deep_copy_of(self)
                new_item.comments.add("re-create section")
        return delta

    def _duplicate_child_allowed_check(self):
        """ Determine if duplicate(identical text) children are allowed under the parent """

        for rule in self.options[
                'parent_allows_duplicate_child']:
            if self.lineage_test(rule):
                return True
        return False

    def add_shallow_copy_of(self, child_to_add, merged=False):
        """ Add a nested copy of a child_to_add to self.children """

        new_child = self.add_child(child_to_add.text)
        if merged:
            new_child.instances.append({
                'hostname': child_to_add.hostname,
                'comments': child_to_add.comments,
                'tags': child_to_add.tags})
        new_child.comments.update(child_to_add.comments)
        new_child.tags.update(child_to_add.tags)
        new_child.order_weight = child_to_add.order_weight

        return new_child

    def line_inclusion_test(self, include_tags, exclude_tags):
        """
        Given the line_tags, include_tags, and exclude_tags,
        determine if the line should be included

        """

        include_line = False
        if include_tags:
            set_include_tags = set(include_tags)
            include_line = bool(self.tags.intersection(set_include_tags))

        if include_line:
            set_exclude_tags = set(exclude_tags)
            if self.tags.intersection(set_exclude_tags):
                return False
            else:
                return True
        else:
            return False

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
            object_rules, text_match_rules = HConfigChild._explode_lineage_rule(
                lineage_rule)

            if not HConfigChild._lineage_eval_object_rules(
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

            if HConfigChild._lineage_eval_text_match_rules(
                    text_match_rules, text):
                matches += 1
                continue
            else:
                return False

        if matches == len(rule['lineage']):
            return True
        else:
            return False
