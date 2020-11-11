import tempfile
import os
import types

import pytest

from hier_config import HConfig, Host


class TestHConfig:
    @pytest.fixture(autouse=True)
    def setup(self, options_ios):
        self.os = "ios"
        self.host_a = Host("example1.rtr", self.os, options_ios)
        self.host_b = Host("example2.rtr", self.os, options_ios)

    def test_bool(self):
        config = HConfig(host=self.host_a)
        assert not config
        config.add_child("test")
        assert config

    def test_merge(self):
        hier1 = HConfig(host=self.host_a)
        hier1.add_child("interface Vlan2")
        hier2 = HConfig(host=self.host_b)
        hier2.add_child("interface Vlan3")

        assert 1 == len(list(hier1.all_children()))
        assert 1 == len(list(hier2.all_children()))

        hier1.merge(hier2)

        assert 2 == len(list(hier1.all_children()))

    def test_load_from_file(self):
        hier = HConfig(host=self.host_a)
        config = "interface Vlan2\n ip address 1.1.1.1 255.255.255.0"

        with tempfile.NamedTemporaryFile(mode="r+", delete=False) as myfile:
            myfile.file.write(config)
            myfile.file.flush()
            myfile.close()
            hier.load_from_file(myfile.name)
            os.remove(myfile.name)

        assert 2 == len(list(hier.all_children()))

    def test_load_from_config_text(self):
        hier = HConfig(host=self.host_a)
        config = "interface Vlan2\n ip address 1.1.1.1 255.255.255.0"

        hier.load_from_string(config)
        assert 2 == len(list(hier.all_children()))

    def test_dump_and_load_from_dump_and_compare(self):
        hier_pre_dump = HConfig(host=self.host_a)
        a1 = hier_pre_dump.add_child("a1")
        b2 = a1.add_child("b2")

        b2.order_weight = 400
        b2.tags.add("test")
        b2.comments.add("test comment")
        b2.new_in_config = True

        dump = hier_pre_dump.dump()

        hier_post_dump = HConfig(host=self.host_a)
        hier_post_dump.load_from_dump(dump)

        assert hier_pre_dump == hier_post_dump

    def test_add_tags(self):
        hier = HConfig(host=self.host_a)
        tag_rules = [{"lineage": [{"equals": "interface Vlan2"}], "add_tags": "test"}]
        child = hier.add_child("interface Vlan2")

        hier.add_tags(tag_rules)

        assert {"test"} == child.tags

    def test_all_children_sorted_by_lineage_rules(self, tags_ios):
        hier = HConfig(host=self.host_a)
        svi = hier.add_child("interface Vlan2")
        svi.add_child("description switch-mgmt-10.0.2.0/24")

        mgmt = hier.add_child("interface FastEthernet0")
        mgmt.add_child("description mgmt-192.168.0.0/24")

        assert 4 == len(list(hier.all_children()))
        assert isinstance(hier.all_children(), types.GeneratorType)

        assert 2 == len(list(hier.all_children_sorted_with_lineage_rules(tags_ios)))

        assert isinstance(
            hier.all_children_sorted_with_lineage_rules(tags_ios), types.GeneratorType,
        )

    def test_add_ancestor_copy_of(self):
        hier1 = HConfig(host=self.host_a)
        interface = hier1.add_child("interface Vlan2")
        interface.add_children(
            ["description switch-mgmt-192.168.1.0/24", "ip address 192.168.1.0/24"]
        )
        hier1.add_ancestor_copy_of(interface)

        assert 3 == len(list(hier1.all_children()))
        assert isinstance(hier1.all_children(), types.GeneratorType)

    def test_has_children(self):
        hier = HConfig(host=self.host_a)
        assert not hier.has_children()
        hier.add_child("interface Vlan2")
        assert hier.has_children()

    def test_depth(self):
        hier = HConfig(host=self.host_a)
        interface = hier.add_child("interface Vlan2")
        ip_address = interface.add_child("ip address 192.168.1.1 255.255.255.0")
        assert 2 == ip_address.depth()

    def test_get_child(self):
        hier = HConfig(host=self.host_a)
        hier.add_child("interface Vlan2")
        child = hier.get_child("equals", "interface Vlan2")
        assert "interface Vlan2" == child.text

    def test_get_child_deep(self):
        hier = HConfig(host=self.host_a)
        interface = hier.add_child("interface Vlan2")
        interface.add_child("ip address 192.168.1.1 255.255.255.0")
        child = hier.get_child_deep(
            [
                ("equals", "interface Vlan2"),
                ("equals", "ip address 192.168.1.1 255.255.255.0"),
            ]
        )
        assert child is not None

    def test_get_children(self):
        hier = HConfig(host=self.host_a)
        hier.add_child("interface Vlan2")
        hier.add_child("interface Vlan3")
        children = hier.get_children("startswith", "interface")
        assert 2 == len(list(children))

    def test_move(self):
        hier1 = HConfig(host=self.host_a)
        interface1 = hier1.add_child("interface Vlan2")
        interface1.add_child("192.168.0.1/30")

        assert 2 == len(list(hier1.all_children()))

        hier2 = HConfig(host=self.host_b)

        assert 0 == len(list(hier2.all_children()))

        interface1.move(hier2)

        assert 0 == len(list(hier1.all_children()))
        assert 2 == len(list(hier2.all_children()))

    def test_del_child_by_text(self):
        hier = HConfig(host=self.host_a)
        hier.add_child("interface Vlan2")
        hier.del_child_by_text("interface Vlan2")

        assert 0 == len(list(hier.all_children()))

    def test_del_child(self):
        hier1 = HConfig(host=self.host_a)
        hier1.add_child("interface Vlan2")

        assert 1 == len(list(hier1.all_children()))

        hier1.del_child(hier1.get_child("startswith", "interface"))

        assert 0 == len(list(hier1.all_children()))

    def test_rebuild_children_dict(self):
        hier1 = HConfig(host=self.host_a)
        interface = hier1.add_child("interface Vlan2")
        interface.add_children(
            ["description switch-mgmt-192.168.1.0/24", "ip address 192.168.1.0/24"]
        )
        delta_a = hier1
        hier1.rebuild_children_dict()
        delta_b = hier1

        assert list(delta_a.all_children()) == list(delta_b.all_children())

    def test_add_children(self):
        interface_items1 = [
            "description switch-mgmt 192.168.1.0/24",
            "ip address 192.168.1.1/24",
        ]
        hier1 = HConfig(host=self.host_a)
        interface1 = hier1.add_child("interface Vlan2")
        interface1.add_children(interface_items1)

        assert 3 == len(list(hier1.all_children()))

        interface_items2 = ["description switch-mgmt 192.168.1.0/24"]
        hier2 = HConfig(host=self.host_a)
        interface2 = hier2.add_child("interface Vlan2")
        interface2.add_children(interface_items2)

        assert 2 == len(list(hier2.all_children()))

    def test_add_child(self):
        hier = HConfig(host=self.host_a)
        interface = hier.add_child("interface Vlan2")
        assert 1 == interface.depth()
        assert "interface Vlan2" == interface.text
        assert not isinstance(interface, list)

    def test_add_deep_copy_of(self):
        hier1 = HConfig(host=self.host_a)
        interface1 = hier1.add_child("interface Vlan2")
        interface1.add_children(
            ["description switch-mgmt-192.168.1.0/24", "ip address 192.168.1.0/24"]
        )

        hier2 = HConfig(host=self.host_b)
        hier2.add_deep_copy_of(interface1)

        assert 3 == len(list(hier2.all_children()))
        assert isinstance(hier2.all_children(), types.GeneratorType)

    def test_lineage(self):
        pass

    def test_path(self):
        pass

    def test_cisco_style_text(self):
        hier = HConfig(host=self.host_a)
        interface = hier.add_child("interface Vlan2")
        ip_address = interface.add_child("ip address 192.168.1.1 255.255.255.0")
        assert "  ip address 192.168.1.1 255.255.255.0" == ip_address.cisco_style_text()
        assert isinstance(ip_address.cisco_style_text(), str)
        assert not isinstance(ip_address.cisco_style_text(), list)

    def test_all_children_sorted_untagged(self):
        config = HConfig(host=self.host_a)
        interface = config.add_child("interface Vlan2")
        ip_address_a = interface.add_child("ip address 192.168.1.1/24")
        ip_address_a.append_tags("a")
        ip_address_none = interface.add_child("ip address 192.168.2.1/24")

        assert ip_address_none is list(config.all_children_sorted_untagged())[1]
        assert 2 == len(list(config.all_children_sorted_untagged()))
        assert ip_address_none is list(config.all_children_sorted_untagged())[1]

    def test_all_children_sorted_by_tags(self):
        config = HConfig(host=self.host_a)
        interface = config.add_child("interface Vlan2")
        ip_address_a = interface.add_child("ip address 192.168.1.1/24")
        ip_address_a.append_tags("a")
        ip_address_ab = interface.add_child("ip address 192.168.2.1/24")
        ip_address_ab.append_tags(["a", "b"])

        assert 1 == len(list(config.all_children_sorted_by_tags({"a"}, {"b"})))
        assert ip_address_a is list(config.all_children_sorted_by_tags({"a"}, {"b"}))[0]
        assert 3 == len(list(config.all_children_sorted_by_tags({"a"}, set())))
        assert 0 == len(list(config.all_children_sorted_by_tags(set(), {"a"})))
        assert 0 == len(list(config.all_children_sorted_by_tags(set(), set())))

    def test_all_children_sorted(self):
        hier = HConfig(host=self.host_a)
        interface = hier.add_child("interface Vlan2")
        interface.add_child("standby 1 ip 10.15.11.1")
        assert 2 == len(list(hier.all_children_sorted()))

    def test_all_children(self):
        hier = HConfig(host=self.host_a)
        interface = hier.add_child("interface Vlan2")
        interface.add_child("standby 1 ip 10.15.11.1")
        assert 2 == len(list(hier.all_children()))

    def test_delete(self):
        pass

    def test_set_order_weight(self):
        hier = HConfig(host=self.host_a)
        child = hier.add_child("no vlan filter")
        hier.set_order_weight()
        assert child.order_weight == 700

    def test_add_sectional_exiting(self):
        hier = HConfig(host=self.host_a)
        bgp = hier.add_child("router bgp 64500")
        template = bgp.add_child("template peer-policy")
        hier.add_sectional_exiting()
        sectional_exit = template.get_child("equals", "exit-peer-policy")
        assert sectional_exit is not None

    def test_to_tag_spec(self):
        pass

    def test_tags(self):
        config = HConfig(host=self.host_a)
        interface = config.add_child("interface Vlan2")
        ip_address = interface.add_child("ip address 192.168.1.1/24")
        assert None in interface.tags
        assert None in ip_address.tags
        ip_address.append_tags("a")
        assert "a" in interface.tags
        assert "a" in ip_address.tags
        assert "b" not in interface.tags
        assert "b" not in ip_address.tags

    def test_append_tags(self):
        config = HConfig(host=self.host_a)
        interface = config.add_child("interface Vlan2")
        ip_address = interface.add_child("ip address 192.168.1.1/24")
        ip_address.append_tags("test_tag")
        assert "test_tag" in config.tags
        assert "test_tag" in interface.tags
        assert "test_tag" in ip_address.tags

    def test_remove_tags(self):
        config = HConfig(host=self.host_a)
        interface = config.add_child("interface Vlan2")
        ip_address = interface.add_child("ip address 192.168.1.1/24")
        ip_address.append_tags("test_tag")
        assert "test_tag" in config.tags
        assert "test_tag" in interface.tags
        assert "test_tag" in ip_address.tags
        ip_address.remove_tags("test_tag")
        assert "test_tag" not in config.tags
        assert "test_tag" not in interface.tags
        assert "test_tag" not in ip_address.tags

    def test_with_tags(self):
        pass

    def test_negate(self):
        hier = HConfig(host=self.host_a)
        interface = hier.add_child("interface Vlan2")
        interface.negate()
        assert "no interface Vlan2" == interface.text

    def test_config_to_get_to(self):
        running_config_hier = HConfig(host=self.host_a)
        interface = running_config_hier.add_child("interface Vlan2")
        interface.add_child("ip address 192.168.1.1/24")
        generated_config_hier = HConfig(host=self.host_a)
        generated_config_hier.add_child("interface Vlan3")
        remediation_config_hier = running_config_hier.config_to_get_to(
            generated_config_hier
        )
        assert 2 == len(list(remediation_config_hier.all_children()))

    def test_config_to_get_to_right(self):
        running_config_hier = HConfig(host=self.host_a)
        running_config_hier.add_child("do not add me")
        generated_config_hier = HConfig(host=self.host_a)
        generated_config_hier.add_child("do not add me")
        generated_config_hier.add_child("add me")
        delta = HConfig(host=self.host_a)
        running_config_hier._config_to_get_to_right(generated_config_hier, delta)
        assert "do not add me" not in delta
        assert "add me" in delta

    def test_sectional_overwrite_no_negate_check(self):
        pass

    def test_sectional_overwrite_check(self):
        pass

    def test_overwrite_with(self):
        pass

    def test_add_shallow_copy_of(self):
        pass

    def test_line_inclusion_test(self):
        config = HConfig(host=self.host_a)
        interface = config.add_child("interface Vlan2")
        ip_address_ab = interface.add_child("ip address 192.168.2.1/24")
        ip_address_ab.append_tags(["a", "b"])

        assert not ip_address_ab.line_inclusion_test({"a"}, {"b"})
        assert not ip_address_ab.line_inclusion_test(set(), {"a"})
        assert ip_address_ab.line_inclusion_test({"a"}, set())
        assert not ip_address_ab.line_inclusion_test(set(), set())

    def test_lineage_test(self):
        pass

    def test_difference1(self):
        rc = ["a", " a1", " a2", " a3", "b"]
        step = ["a", " a1", " a2", " a3", " a4", " a5", "b", "c", "d", " d1"]
        rc_hier = HConfig(host=self.host_a)
        rc_hier.load_from_string("\n".join(rc))
        step_hier = HConfig(host=self.host_a)
        step_hier.load_from_string("\n".join(step))

        difference = step_hier.difference(rc_hier)
        difference_children = list(
            c.cisco_style_text() for c in difference.all_children_sorted()
        )
        # breakpoint()

        assert len(difference_children) == 6
        assert "c" in difference
        assert "d" in difference
        assert "a4" in difference.get_child("equals", "a")
        assert "a5" in difference.get_child("equals", "a")
        assert "d1" in difference.get_child("equals", "d")

    def test_difference2(self, options_ios):
        host = Host(hostname="test_host", os="ios", hconfig_options=options_ios)
        rc = ["a", " a1", " a2", " a3", "b"]
        step = ["a", " a1", " a2", " a3", " a4", " a5", "b", "c", "d", " d1"]
        rc_hier = HConfig(host=host)
        rc_hier.load_from_string("\n".join(rc))
        step_hier = HConfig(host=host)
        step_hier.load_from_string("\n".join(step))

        difference = step_hier.difference(rc_hier)
        difference_children = list(
            c.cisco_style_text() for c in difference.all_children_sorted()
        )
        assert len(difference_children) == 6
