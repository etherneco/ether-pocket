import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location("x11", Path(__file__).parents[1] / "scripts/etherair-x11.py")
x11 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(x11)

QUERY = """Screen 0: minimum 16 x 16, current 3360 x 3120, maximum 32767 x 32767
DSI-2 connected primary 1440x3120+0+0 (normal left inverted right x axis y axis)
   1440x3120     60.00*+
DP-3 connected 1920x1080+1440+0 (normal left inverted right x axis y axis)
   1920x1080     60.00*+
   1280x720      60.00
Virtual-1 disconnected (normal left inverted right x axis y axis)
"""


class DisplayTests(unittest.TestCase):
    def test_preserves_real_qualcomm_dsc_mode_names(self):
        query = QUERY.replace("1440x3120     60.00*+", "1440x3120x60x187200 27.04*+")
        outputs = x11.parse_outputs(query)
        phone, _ = x11.choose_outputs(outputs)
        self.assertEqual(phone["current_mode"], "1440x3120x60x187200")
        mirror = x11.display_command(outputs, "mirror")
        self.assertEqual(mirror[-4:], ["--scale-from", "1440x3120", "--same-as", "DSI-2"])
        self.assertIn("1440x3120x60x187200", mirror)

    def test_discovers_names_and_edid_modes(self):
        outputs = x11.parse_outputs(QUERY)
        phone, external = x11.choose_outputs(outputs)
        self.assertEqual(phone["name"], "DSI-2")
        self.assertEqual(external["name"], "DP-3")
        self.assertEqual(external["modes"], ["1920x1080", "1280x720"])

    def test_extend_and_scaled_mirror(self):
        outputs = x11.parse_outputs(QUERY)
        extend = x11.display_command(outputs)
        self.assertEqual(extend[-2:], ["--right-of", "DSI-2"])
        mirror = x11.display_command(outputs, "mirror")
        self.assertEqual(mirror[-4:], ["--scale-from", "1440x3120", "--same-as", "DSI-2"])
        rotated = x11.display_command(outputs, "mirror", rotation="left")
        self.assertEqual(rotated[-4:], ["--scale-from", "3120x1440", "--same-as", "DSI-2"])

    def test_no_fabricated_1080_mode(self):
        output = {"name": "DP-9", "modes": ["1280x720"], "preferred": "1280x720"}
        self.assertEqual(x11.preferred_mode(output), "1280x720")
        output["preferred"] = None
        with self.assertRaises(RuntimeError):
            x11.preferred_mode(output)

    def test_multiple_external_outputs_need_selection(self):
        outputs = x11.parse_outputs(QUERY + "HDMI-4 connected\n   1920x1080 60.00+\n")
        with self.assertRaises(RuntimeError):
            x11.choose_outputs(outputs)
        self.assertEqual(x11.choose_outputs(outputs, external="HDMI-4")[1]["name"], "HDMI-4")

    def test_internal_must_be_discovered(self):
        outputs = x11.parse_outputs(QUERY.replace("DSI-2", "UnknownPanel"))
        with self.assertRaises(RuntimeError):
            x11.choose_outputs(outputs)
        self.assertEqual(x11.choose_outputs(outputs, internal="UnknownPanel")[0]["name"], "UnknownPanel")

    def test_unplug_disables_old_scanout(self):
        query = QUERY.replace("DP-3 connected", "DP-3 disconnected")
        command = x11.display_command(x11.parse_outputs(query))
        self.assertEqual(command[-3:], ["--output", "DP-3", "--off"])

    def test_touch_rotates_and_maps_to_panel_in_extended_desktop(self):
        matrix = x11.touch_matrix((1440, 3120, 0, 0), (3360, 3120), "left")
        self.assertAlmostEqual(matrix[1], -1440 / 3360)
        self.assertAlmostEqual(matrix[2], 1440 / 3360)
        self.assertEqual(matrix[3], 1)
        self.assertEqual(matrix[4], 0)

    def test_calibration_composes_with_rotation_and_offset(self):
        matrix = x11.touch_matrix((100, 200, 100, 0), (200, 200), "normal",
                                  (0.8, 0, 0.1, 0, 0.8, 0.1, 0, 0, 1))
        self.assertAlmostEqual(matrix[0], 0.4)
        self.assertAlmostEqual(matrix[2], 0.55)

    def test_software_and_unknown_are_not_claimed_accelerated(self):
        self.assertEqual(x11.renderer_status("OpenGL renderer string: llvmpipe"),
                         "software-rendering-limitation")
        self.assertEqual(x11.renderer_status("failed"), "unverified")
        self.assertEqual(x11.renderer_status("direct rendering: Yes\nOpenGL renderer string: FD640"),
                         "adreno-candidate-review-kernel-and-xorg-logs")

    def test_watch_retries_failed_configuration(self):
        args = SimpleNamespace(interval=3, layout="extend")
        with patch.object(x11, "snapshot", return_value=x11.parse_outputs(QUERY)), \
             patch.object(x11, "resume_clock", side_effect=[0, 0, 3]), \
             patch.object(x11, "apply_display", side_effect=[RuntimeError("probe failed"), None]) as apply, \
             patch.object(x11.time, "sleep", side_effect=[None, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                x11.watch(args)
            self.assertEqual(apply.call_count, 2)

    def test_watch_reapplies_after_resume_with_unchanged_connectors(self):
        args = SimpleNamespace(interval=3, layout="extend")
        with patch.object(x11, "snapshot", return_value=x11.parse_outputs(QUERY)), \
             patch.object(x11, "resume_clock", side_effect=[0, 0, 60]), \
             patch.object(x11, "apply_display") as apply, \
             patch.object(x11.time, "sleep", side_effect=[None, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                x11.watch(args)
            self.assertEqual(apply.call_count, 2)


if __name__ == "__main__":
    unittest.main()
