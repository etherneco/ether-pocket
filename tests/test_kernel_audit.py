import gzip
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("audit", Path(__file__).parents[1] / "scripts/audit-kernel.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class KernelAuditTests(unittest.TestCase):
    def test_reads_explicit_disabled_and_enabled_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.gz"
            path.write_bytes(gzip.compress(b"# CONFIG_VT is not set\nCONFIG_DRM_MSM=y\n"))
            result = audit.read_config(path)
            self.assertEqual(result["CONFIG_VT"], "n")
            self.assertEqual(result["CONFIG_DRM_MSM"], "y")

    def test_absent_prerequisites_are_not_accepted(self):
        result = audit.audit({"CONFIG_DRM_MSM": "y", "CONFIG_QCOM_KGSL": "y"})
        self.assertIn("CONFIG_VT", result["missing"])
        self.assertIn("CONFIG_DEVTMPFS", result["missing"])

    def test_enabled_prerequisites_pass_configuration_gate_only(self):
        result = audit.audit({key: "y" for key in audit.REQUIRED})
        self.assertFalse(result["missing"])
        self.assertIn("not complete", result["scope"])

    def test_live_kernel_evidence_exposes_confirmed_blockers(self):
        path = Path(__file__).parents[1] / "evidence/running-kernel-config.gz"
        result = audit.audit(audit.read_config(path))
        self.assertEqual(set(result["missing"]),
                         {"CONFIG_VT", "CONFIG_VT_CONSOLE", "CONFIG_DEVTMPFS", "CONFIG_SYSVIPC"})
        self.assertEqual(result["graphics"]["CONFIG_QCOM_KGSL"], "y")


if __name__ == "__main__":
    unittest.main()
