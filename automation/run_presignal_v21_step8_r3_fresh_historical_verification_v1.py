"""R3 verification entrypoint. Only call-free --preflight is enabled here."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
def main():
 p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args()
 if a.execute:raise SystemExit('R3_EXECUTION_REQUIRES_SEPARATE_AUTHORIZATION')
 if not a.preflight:raise SystemExit('PRELIGHT_REQUIRED')
 print(json.dumps(binding.gate(),sort_keys=True))
if __name__=='__main__':main()
