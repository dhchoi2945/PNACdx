from pgcheck.t01 import check_t01
from pgcheck.validator import validate
from tests.helpers import ExportCase


class T01Tests(ExportCase):
    def test_expected_t01_passes(self):
        report = check_t01(self.dataset())
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(report.status, "PASS")

    def assert_t01_fails(self, data):
        report = check_t01(data)
        self.assertFalse(report.ok, report.as_dict())
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(report.issues)

    def test_two_loads_keep_different_vdd_connections(self):
        data = self.dataset()
        self.edge(data, "instance:load1", "VDD")["net_id"] = "net:root:VDD_A"
        self.assertTrue(validate(data).ok, validate(data).as_dict())
        self.assert_t01_fails(data)

    def test_gnd_must_be_shared_on_vss_a(self):
        data = self.dataset()
        self.edge(data, "instance:load1", "VSS")["net_id"] = "net:root:VDD_B"
        self.assertTrue(validate(data).ok)
        self.assert_t01_fails(data)

    def test_signal_connection_is_checked(self):
        data = self.dataset()
        self.edge(data, "instance:load0", "EN")["net_id"] = "net:root:VSS_A"
        self.assertTrue(validate(data).ok)
        self.assert_t01_fails(data)

    def test_each_expected_edge_is_checked_independently(self):
        for instance in ("instance:load0", "instance:load1"):
            for port in ("VDD", "VSS", "EN"):
                with self.subTest(instance=instance, port=port):
                    data = self.dataset()
                    self.edge(data, instance, port).update(status="unconnected", net_id=None)
                    self.assertTrue(validate(data).ok)
                    self.assert_t01_fails(data)

    def test_child_local_port_to_net_mapping_is_checked(self):
        data = self.dataset()
        self.edge(data, "instance:load0", "VDD", "cell_port")["net_id"] = "net:load0:VSS"
        self.assertTrue(validate(data).ok)
        self.assert_t01_fails(data)

    def test_top_local_port_to_net_mapping_is_checked(self):
        data = self.dataset()
        self.edge(data, "instance:root", "VDD_A", "cell_port")["net_id"] = "net:root:VDD_B"
        self.assertTrue(validate(data).ok)
        self.assert_t01_fails(data)

    def test_direction_values_must_match_the_independent_oracle(self):
        for cell_index in (0, 1):
            for terminal_index in range(len(self.dataset().cells[cell_index]["terminals"])):
                with self.subTest(cell=cell_index, terminal=terminal_index):
                    data = self.dataset()
                    terminal = data.cells[cell_index]["terminals"][terminal_index]
                    terminal["direction"] = "output"
                    self.assertTrue(validate(data).ok)
                    self.assert_t01_fails(data)

    def test_placed_symbol_and_selected_schematic_are_checked(self):
        data = self.dataset()
        data.instances[1]["master"]["view"] = "schematic"
        self.assertTrue(validate(data).ok)
        self.assert_t01_fails(data)

    def test_top_identity_is_checked(self):
        data = self.dataset()
        data.cells[0]["cell"] = "OTHER_TOP"
        data.instances[0]["master"]["cell"] = "OTHER_TOP"
        data.instances[0]["selected"]["cell"] = "OTHER_TOP"
        data.manifest["top"]["cell"] = "OTHER_TOP"
        self.assertTrue(validate(data).ok)
        self.assert_t01_fails(data)

    def test_child_names_are_checked(self):
        data = self.dataset()
        data.instances[1]["name"] = "U_WRONG"
        self.assert_t01_fails(data)

    def test_missing_child_does_not_pass(self):
        data = self.dataset()
        data.instances.pop()
        self.refresh_counts(data)
        self.assert_t01_fails(data)

    def test_unresolved_cannot_pass_t01(self):
        data = self.dataset()
        self.unresolved_edge(data)
        self.assert_t01_fails(data)

    def test_optional_placement_is_not_a_t01_gate(self):
        data = self.dataset()
        for occurrence in data.instances:
            occurrence["placement"] = None
        self.assertTrue(check_t01(data).ok, check_t01(data).as_dict())
