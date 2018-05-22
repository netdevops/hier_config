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

    def test_cisco_style_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        ip_address = interface.add_child(
            'ip address 192.168.1.1 255.255.255.0')
        self.assertEqual(
            '  ip address 192.168.1.1 255.255.255.0',
            ip_address.cisco_style_text())

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

    def test_add_child(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        self.assertEqual(1, interface.depth())

    def test_depth(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        ip_address = interface.add_child(
            'ip address 192.168.1.1 255.255.255.0')
        self.assertEqual(2, ip_address.depth())

    def test_add_sectional_exiting(self):
        hier = HConfig(self.host_a, self.os, self.options)
        bgp = hier.add_child('router bgp 12200')
        template = bgp.add_child('template peer-policy')
        hier.add_sectional_exiting()
        sectional_exit = template.get_child('equals', 'exit-peer-policy')
        self.assertIsNotNone(sectional_exit)

    def test_all_children(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        interface.add_child('standby 1 ip 10.15.11.1')
        self.assertEqual(2, len(list(hier.all_children())))

    def test_all_children_sorted(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        interface.add_child('standby 1 ip 10.15.11.1')
        self.assertEqual(2, len(list(hier.all_children_sorted())))

    def test_config_to_get_to(self):
        running_config_hier = HConfig(self.host_a, self.os, self.options)
        running_config_hier.add_child('interface vlan2')
        compiled_config_hier = HConfig(self.host_a, self.os, self.options)
        compiled_config_hier.add_child('interface vlan3')
        remediation_config_hier = running_config_hier.config_to_get_to(
            compiled_config_hier)
        self.assertEqual(2, len(list(remediation_config_hier.all_children())))

    def test_add_tags(self):
        hier = HConfig(self.host_a, self.os, self.options)
        tag_rules = [{
            'lineage': [{'equals': 'interface vlan2'}],
            'add_tags': 'test'}]
        child = hier.add_child('interface vlan2')
        hier.add_tags(tag_rules)
        self.assertEqual({'test'}, child.tags)

    def test_del_child_by_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        hier.add_child('interface vlan2')
        hier.del_child_by_text('interface vlan2')
        self.assertEqual(0, len(list(hier.all_children())))

    def test_from_config_text(self):
        hier = HConfig(self.host_a, self.os, self.options)
        config = 'interface vlan2\n ip address 1.1.1.1 255.255.255.0'
        hier.load_from_string(config)
        self.assertEqual(2, len(list(hier.all_children())))

    def test_from_file(self):
        hier = HConfig(self.host_a, self.os, self.options)
        config = 'interface vlan2\n ip address 1.1.1.1 255.255.255.0'
        with tempfile.NamedTemporaryFile(mode='r+') as myfile:
            myfile.file.write(config)
            myfile.file.flush()
            hier.load_from_file(myfile.name)
        self.assertEqual(2, len(list(hier.all_children())))

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

    def test_negate(self):
        hier = HConfig(self.host_a, self.os, self.options)
        interface = hier.add_child('interface vlan2')
        interface.negate()
        self.assertEqual('no interface vlan2', interface.text)

    def test_set_order_weight(self):
        hier = HConfig(self.host_a, self.os, self.options)
        child = hier.add_child('no vlan filter')
        hier.set_order_weight()
        self.assertEqual(child.order_weight, 700)


if __name__ == "__main__":
    unittest.main()
