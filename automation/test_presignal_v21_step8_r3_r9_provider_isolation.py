import unittest

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import presignal_v21_historical_verification_r3_compat_r5_contract_v1 as compat
from automation import repair_presignal_v21_step8_r3_r9_provider_isolation_v1 as r9


class R9ProviderIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r9.prepare()

    def test_attention_rank_is_strict_before_downstream_use(self):
        valid = [{"attention_rank": 0}, {"attention_rank": 12}]
        binding.validate_attention_rank(valid, compat.spec())
        for invalid in ("L", "high", -1, 1.5, None, True):
            with self.assertRaisesRegex(binding.BindingError, "INVALID_ATTENTION_RANK"):
                binding.validate_attention_rank([{"attention_rank": invalid}], compat.spec())

    def test_r5_contract_freezes_only_runtime_boundaries(self):
        spec = compat.spec()
        self.assertEqual(spec["parent_contract_version"], "presignal_event_path_contract_v1_historical_verification_r3_compat_r4")
        self.assertIn("attention_rank", compat.ATTENTION_RANK_RULE["field"])
        self.assertEqual(spec["prompt_template_fingerprint"], binding.compat_r4.spec()["prompt_template_fingerprint"])


if __name__ == "__main__":
    unittest.main()
