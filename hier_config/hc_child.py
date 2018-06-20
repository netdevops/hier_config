from hier_config.base import HConfigBase

import hier_config.helpers as H


class HConfigChild(HConfigBase):

    def __init__(self, parent, text):
        super(HConfigChild, self).__init__()
        self.parent = parent
        self._text = text.strip()
        self.real_indent_level = None
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
        return 'HConfigChild(HConfigChild, {})'.format(self.text)

    def __str__(self):
        return self.text

    def __lt__(self, other):
        return self.order_weight < other.order_weight

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

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def root(self):
        """ returns the HConfig object at the base of the tree """

        return self.parent.root

    @property
    def logs(self):
        return self.root.logs

    @property
    def host(self):
        return self.root.host

    @property
    def options(self):
        return self.root.options

    def depth(self):
        return self.parent.depth() + 1

    def move(self, new_parent):
        """
        move one HConfigChild object to different HConfig parent object

        .. code:: python

            hier1 = HConfig(host=host)
            interface1 = hier1.add_child('interface Vlan2')
            interface1.add_child('ip address 10.0.0.1 255.255.255.252')

            hier2 = Hconfig(host)

            interface1.move(hier2)

        :param new_parent: HConfigChild object -> type list
        :return: None

        """

        new_parent.children.append(self)
        new_parent.rebuild_children_dict()
        self.delete()

    def lineage(self):
        """
        Return the lineage of parent objects, up to but excluding the root

        """

        if self.root is self.parent:
            yield self
        else:
            for parent in self.parent.lineage():
                yield parent
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

    def delete(self):
        """ Delete the current object from its parent """

        # TODO find a way to remove this when sub-classing in HCRoot
        self.parent.del_child(self)

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

        :return: boolean

        """

        if self.host.os in {'iosxr'}:
            if self.parent is not self.root:
                acl = ('ipv4 access-list ', 'ipv6 access-list ')
                if self.parent.text.startswith(acl):
                    return True
        return False

    def is_idempotent_command(self, other_children):
        """
        Determine if self.text is an idempotent change.

        :param other_children: HConfigChild object -> type list
        :return: boolean

        """

        # Blacklist commands from matching as idempotent
        for rule in self.options[
                'idempotent_commands_blacklist']:
            if self.lineage_test(rule, True):
                return False

        # Handles idempotent acl entry identification
        if self._idempotent_acl_check():
            if self.host.os in {'iosxr'}:
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
            return not bool(self.tags.intersection(set_exclude_tags))
