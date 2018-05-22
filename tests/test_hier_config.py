import unittest
import tempfile
import os
import yaml
import types

from hier_config import HConfig


class TestHConfig(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.host_a = 'example1.rtr'
        cls.host_b = 'example2.rtr'
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
        cls.running_cfg = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'running_config.conf',
        )
        cls.compiled_cfg = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'files',
            'compiled_config.conf',
        )

        with open(cls.tags_file) as f:
            cls.tags = yaml.load(f.read())

        with open(cls.options_file) as f:
            cls.options = yaml.load(f.read())

    def test_merge(self):
        hier1 = HConfig(self.host_a, self.os, self.options)
        hier1.add_child('interface Vlan2')
        hier2 = HConfig(self.host_b, self.os, self.options)
        hier2.add_child('interface Vlan3')

        self.assertEqual(1, len(list(hier1.all_children())))
        self.assertEqual(1, len(list(hier2.all_children())))

        hier1.merge(hier2)

        self.assertEqual(2, len(list(hier1.all_children())))

    def test_load_from_file(self):
        hier = HConfig(self.host_a, self.os, self.options)
        config = 'interface Vlan2\n ip address 1.1.1.1 255.255.255.0'

        with tempfile.NamedTemporaryFile(mode='r+') as myfile:
            myfile.file.write(config)
            myfile.file.flush()
            hier.load_from_file(myfile.name)

        self.assertEqual(2, len(list(hier.all_children())))

    def test_load_from_config_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        config = 'interface Vlan2\n ip address 1.1.1.1 255.255.255.0'

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
            'lineage': [{'equals': 'interface Vlan2'}],
            'add_tags': 'test'}]
        child = hier.add_child('interface Vlan2')

        hier.add_tags(tag_rules)

        self.assertEqual({'test'}, child.tags)

    def test_all_children_sorted_by_lineage_rules(self):
        hier = HConfig(self.host_a, self.os, self.options)
        svi = hier.add_child('interface Vlan2')
        svi.add_child('description switch-mgmt-10.0.2.0/24')

        mgmt = hier.add_child('interface FastEthernet0')
        mgmt.add_child('description mgmt-192.168.0.0/24')

        self.assertEqual(4, len(list(hier.all_children())))
        self.assertTrue(isinstance(hier.all_children(), types.GeneratorType))

        self.assertEqual(2, len(list(hier.all_children_sorted_with_lineage_rules(self.tags))))
        self.assertTrue(isinstance(hier.all_children_sorted_with_lineage_rules(self.tags), types.GeneratorType))

    def test_add_ancestor_copy_of(self):
        pass

    def test_has_children(self):
        hier = HConfig(self.host_a, self.os, self.options)
        self.assertFalse(hier.has_children())
        hier.add_child('interface Vlan2')
        self.assertTrue(hier.has_children())

    def test_depth(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface Vlan2')
        ip_address = interface.add_child(
            'ip address 192.168.1.1 255.255.255.0')
        self.assertEqual(2, ip_address.depth())

    def test_get_child(self):
        hier = HConfig(self.host_a, self.os, self.options)
        hier.add_child('interface vlan2')
        child = hier.get_child('equals', 'interface Vlan2')
        self.assertEqual('interface vlan2', child.text)

    def test_get_child_deep(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface Vlan2')
        interface.add_child('ip address 192.168.1.1 255.255.255.0')
        child = hier.get_child_deep([
            ('equals', 'interface vlan2'),
            ('equals', 'ip address 192.168.1.1 255.255.255.0')])
        self.assertIsNotNone(child)

    def test_get_children(self):
        hier = HConfig(self.host_a, self.os, self.options)
        hier.add_child('interface Vlan2')
        hier.add_child('interface Vlan3')
        children = hier.get_children('startswith', 'interface')
        self.assertEqual(2, len(list(children)))

    def test_move(self):
        hier1 = HConfig(self.host_a, self.os, self.options)
        interface1 = hier1.add_child('interface Vlan2')
        interface1.add_child('192.168.0.1/30')

        self.assertEqual(2, len(list(hier1.all_children())))

        hier2 = HConfig(self.host_b, self.os, self.options)

        self.assertEqual(0, len(list(hier2.all_children())))

        interface1.move(hier2)

        self.assertEqual(0, len(list(hier1.all_children())))
        self.assertEqual(2, len(list(hier2.all_children())))

    def test_del_child_by_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        hier.add_child('interface Vlan2')
        hier.del_child_by_text('interface Vlan2')

        self.assertEqual(0, len(list(hier.all_children())))

    def test_del_child(self):
        hier1 = HConfig(self.host_a, self.os, self.options)
        hier1.add_child('interface Vlan2')

        self.assertEqual(1, len(list(hier1.all_children())))

        hier1.del_child(hier1.get_child('startswith', 'interface'))

        self.assertEqual(0, len(list(hier1.all_children())))

    def test_rebuild_children_dict(self):
        pass

    def test_add_children(self):
        pass

    def test_add_child(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface Vlan2')
        self.assertEqual(1, interface.depth())
        self.assertEqual('interface Vlan2', interface.text)
        self.assertFalse(isinstance(interface, list))

    def test_add_deep_copy_of(self):
        pass

    def test_lineage(self):
        pass

    def test_path(self):
        pass

    def test_cisco_style_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface Vlan2')
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
        interface = hier.add_child('interface Vlan2')
        interface.add_child('standby 1 ip 10.15.11.1')
        self.assertEqual(2, len(list(hier.all_children_sorted())))

    def test_all_children(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface Vlan2')
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
        bgp = hier.add_child('router bgp 64500')
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
        interface = hier.add_child('interface Vlan2')
        interface.negate()
        self.assertEqual('no interface Vlan2', interface.text)

    def test_config_to_get_to(self):
        running_config_hier = HConfig(self.host_a, self.os, self.options)
        running_config_hier.add_child('interface Vlan2')
        compiled_config_hier = HConfig(self.host_a, self.os, self.options)
        compiled_config_hier.add_child('interface Vlan3')
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
