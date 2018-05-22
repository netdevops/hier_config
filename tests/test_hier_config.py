import unittest
import tempfile
import os
import yaml

from hier_config import HConfig


class TestHConfig(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.host_a = 'example.rtr'
        cls.os = 'ios'
        cls.options_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'test_options_ios.yml',
        )
        cls.tags_file = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'test_tags_ios.yml',
        )
        cls.tags = yaml.load(open(cls.tags_file))
        cls.options = yaml.load(open(cls.options_file))

    def test_merge(self):
        pass

    def test_load_from_file(self):
        hier = HConfig(self.host_a, self.os, self.options)
        config = 'interface vlan2\n ip address 1.1.1.1 255.255.255.0'
        with tempfile.NamedTemporaryFile(mode='r+') as myfile:
            myfile.file.write(config)
            myfile.file.flush()
            hier.load_from_file(myfile.name)
        self.assertEqual(2, len(list(hier.all_children())))

    def test_load_from_config_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        config = 'interface vlan2\n ip address 1.1.1.1 255.255.255.0'
        hier.load_from_string(config)
        self.assertEqual(2, len(list(hier.all_children())))

    def test_dump_and_load_from_dump_and_compare(self):
        hier_pre_dump = HConfig(self.host_a, self.os, self.options)
        a1 = hier_pre_dump.add_child('a1')
        b2 = a1.add_child('b2')
        b2.order_weight = 400
        b2.tags.add('test')
        b2.comments.add('test comment')
        b2.new_in_config = True
        dump = hier_pre_dump.dump()

        hier_post_dump = HConfig(self.host_a, self.os, self.options)
        hier_post_dump.load_from_dump(dump)

        self.assertEqual(hier_pre_dump, hier_post_dump)

    def test_add_tags(self):
        hier = HConfig(self.host_a, self.os, self.options)
        tag_rules = [{
            'lineage': [{'equals': 'interface vlan2'}],
            'add_tags': 'test'}]
        child = hier.add_child('interface vlan2')
        hier.add_tags(tag_rules)
        self.assertEqual({'test'}, child.tags)

    def test_all_children_sorted_by_lineage_rules(self):
        pass

    def test_add_ancestor_copy_of(self):
        pass

    def test_has_children(self):
        pass

    def test_depth(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        ip_address = interface.add_child(
            'ip address 192.168.1.1 255.255.255.0')
        self.assertEqual(2, ip_address.depth())

    def test_get_child(self):
        hier = HConfig(self.host_a, self.os, self.options)
        hier.add_child('interface vlan2')
        child = hier.get_child('equals', 'interface vlan2')
        self.assertEqual('interface vlan2', child.text)

    def test_get_child_deep(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        interface.add_child('ip address 192.168.1.1 255.255.255.0')
        child = hier.get_child_deep([
            ('equals', 'interface vlan2'),
            ('equals', 'ip address 192.168.1.1 255.255.255.0')])
        self.assertIsNotNone(child)

    def test_get_children(self):
        hier = HConfig(self.host_a, self.os, self.options)
        hier.add_child('interface vlan2')
        hier.add_child('interface vlan3')
        children = hier.get_children('startswith', 'interface')
        self.assertEqual(2, len(list(children)))

    def test_move(self):
        pass

    def test_del_child_by_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        hier.add_child('interface vlan2')
        hier.del_child_by_text('interface vlan2')
        self.assertEqual(0, len(list(hier.all_children())))

    def test_def_child(self):
        pass

    def test_rebuild_children_dict(self):
        pass

    def test_add_children(self):
        pass

    def test_add_child(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        self.assertEqual(1, interface.depth())
        self.assertEqual('interface vlan2', interface.text)
        self.assertFalse(isinstance(interface, list))

    def test_add_deep_copy_of(self):
        pass

    def test_lineage(self):
        pass

    def test_path(self):
        pass

    def test_cisco_style_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        ip_address = interface.add_child(
            'ip address 192.168.1.1 255.255.255.0')
        self.assertEqual(
            '  ip address 192.168.1.1 255.255.255.0',
            ip_address.cisco_style_text())
        self.assertNotEqual(
            ' ip address 192.168.1.1 255.255.255.0',
            ip_address.cisco_style_text())
        self.assertTrue(isinstance(ip_address.cisco_style_text(), str))
        self.assertFalse(isinstance(ip_address.cisco_style_text(), list))

    def test_all_children_sorted_untagged(self):
        pass

    def test_all_children_sorted_by_tags(self):
        pass

    def test_all_children_sorted(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        interface.add_child('standby 1 ip 10.15.11.1')
        self.assertEqual(2, len(list(hier.all_children_sorted())))

    def test_all_children(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        interface.add_child('standby 1 ip 10.15.11.1')
        self.assertEqual(2, len(list(hier.all_children())))

    def test_delete(self):
        pass

    def test_set_order_weight(self):
        hier = HConfig(self.host_a, self.os, self.options)
        child = hier.add_child('no vlan filter')
        hier.set_order_weight()
        self.assertEqual(child.order_weight, 700)

    def test_add_sectional_exiting(self):
        hier = HConfig(self.host_a, self.os, self.options)
        bgp = hier.add_child('router bgp 12200')
        template = bgp.add_child('template peer-policy')
        hier.add_sectional_exiting()
        sectional_exit = template.get_child('equals', 'exit-peer-policy')
        self.assertIsNotNone(sectional_exit)

    def test_to_tag_spec(self):
        pass

    def test_ancestor_append_tags(self):
        pass

    def test_ancestor_remove_tags(self):
        pass

    def test_deep_append_tags(self):
        pass

    def test_deep_remove_tags(self):
        pass

    def test_append_tags(self):
        pass

    def test_remove_tags(self):
        pass

    def test_with_tags(self):
        pass

    def test_negate(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        interface.negate()
        self.assertEqual('no interface vlan2', interface.text)

    def test_config_to_get_to(self):
        running_config_hier = HConfig(self.host_a, self.os, self.options)
        running_config_hier.add_child('interface vlan2')
        compiled_config_hier = HConfig(self.host_a, self.os, self.options)
        compiled_config_hier.add_child('interface vlan3')
        remediation_config_hier = running_config_hier.config_to_get_to(
            compiled_config_hier)
        self.assertEqual(2, len(list(remediation_config_hier.all_children())))

    def test_is_idempotent_command(self):
        pass

    def test_sectional_overwrite_no_negate_check(self):
        pass

    def test_sectional_overwrite_check(self):
        pass

    def test_overwrite_with(self):
        pass

    def test_add_shallow_copy_of(self):
        pass

    def test_line_inclusion_test(self):
        pass

    def test_lineage_test(self):
        pass


if __name__ == "__main__":
    unittest.main()
