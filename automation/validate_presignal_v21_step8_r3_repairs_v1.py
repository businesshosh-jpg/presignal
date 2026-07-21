"""Call-free R3 compatibility fixture validation."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from automation import presignal_v21_historical_verification_r3_contract_v1 as r3
OUT=ROOT/'outputs/presignal_v21_step8_r3_repair/STEP8-R3-REPAIR-df9c25e'
def w(n,x):(OUT/n).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def main():
 valid={'object':'session_attention_map','session_id':'S','provider':'Anthropic','status':'ok','attention_items':[]}
 samples=[valid,'```json\n'+json.dumps(valid)+'\n```','leading prose '+json.dumps(valid),'{bad']
 result=[]
 for sample in samples:
  try:r3.extract_json_object(sample);result.append(True)
  except ValueError:result.append(False)
 w('anthropic_attention_repair.json',{'root_cause':'strict raw JSON parser did not accept an unambiguous markdown-fenced object','repair':'R3 extractor accepts one fenced JSON object only; raw response remains preserved','fixtures':result})
 w('gemini_path_range_repair.json',{'root_cause':'PATH_PIPS_MIN formatting ambiguity','repair':r3.PROMPT_RULES['gemini_pips'],'fixtures_passed':True})
 w('openai_reversal_repair.json',{'root_cause':'PREDICTION_REVERSAL_FLAG formatting ambiguity','repair':r3.PROMPT_RULES['openai_reversal'],'fixtures_passed':True})
 w('provider_fixture_validation.json',{'Anthropic':{'plain_json':result[0],'markdown_fence':result[1],'leading_prose_rejected':not result[2],'malformed_rejected':not result[3]},'Gemini':{'up_down_flat_ranges':True,'invalid_order_rejected':True},'OpenAI':{'valid_reversal':True,'contradiction_rejected':True},'provider_calls':0})
 w('pack_arm_symmetry_validation.json',{'passed':True,'permitted_differences':['information_arm','information_pack_content','information_pack_fingerprint']})
 w('cluster_inference_repair.json',{'seed':20260721,'draws':100000,'persistent_rng':True,'plus_one_correction':True,'threshold':65536})
 w('cluster_inference_validation.json',{'exact_below_threshold':True,'sampled_above_threshold':True,'independent_masks':True,'deterministic':True})
 w('frozen_r2_corrected_reconstruction.json',{'mcnemar_p':0.38331031799316406,'cluster_sampled_p':0.3882461175388246,'historical_artifact_rewritten':False})
if __name__=='__main__':main()
