import unittest
from automation import presignal_v21_historical_verification_r3_contract_v1 as r3
class R3RepairTests(unittest.TestCase):
 def test_json_extraction(self):
  obj={'x':1};self.assertEqual(r3.extract_json_object('```json\n{"x":1}\n```'),obj)
  with self.assertRaises(ValueError):r3.extract_json_object('prose {"x":1}')
 def test_contract_is_versioned(self):
  self.assertEqual(r3.spec()['parent_contract_version'],r3.PARENT_CONTRACT_VERSION)
if __name__=='__main__':unittest.main()
