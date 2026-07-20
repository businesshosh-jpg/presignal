import unittest
from pathlib import Path
from automation import continue_presignal_v21_step8_r2_historical_replication_v1 as c
class ContinuationTests(unittest.TestCase):
 def test_next_population_is_canonical_and_disjoint(self):
  run=Path(c.ROOT/'outputs/presignal_v21_step8_r2_historical_replication'/c.PARENT_RUN)
  _,eligible,_,_=c.parent.recover_population(); prior=c.existing_episode_ids(run); nxt=[x for x in eligible if x['episode_id'] not in prior][:20]
  self.assertEqual(len(prior),80);self.assertTrue(nxt);self.assertEqual(nxt,sorted(nxt,key=lambda x:(x['release_ts'],x['session_id'],x['episode_id'])))
  self.assertFalse({x['episode_id'] for x in nxt}&prior)
 def test_cluster_sign_flip_is_exact_then_fixed_seed_sampled(self):
  def record(episode_id, a, e):
   return {'episode_id':episode_id,'provider':'OpenAI','completion':'COMPLETE_PAIRED','pack_a_evaluation':{'direction_15m_ok':a,'overall_path_score':0.5},'pack_e_evaluation':{'direction_15m_ok':e,'overall_path_score':0.5}}
  exact=c.analyze([record('E1',True,False),record('E2',False,True)])
  self.assertEqual(exact['episode_cluster_permutation']['method'],'EXACT_ENUMERATION')
  sampled_rows=[record('E%03d'%i, i%2==0, i%3==0) for i in range(17)]
  first=c.analyze(sampled_rows); second=c.analyze(sampled_rows)
  self.assertEqual(first['episode_cluster_permutation']['method'],'FIXED_SEED_MONTE_CARLO')
  self.assertEqual(first['episode_cluster_permutation'],second['episode_cluster_permutation'])
if __name__=='__main__':unittest.main()
