"""Actual owned-FS snapshots and failing-publication receipts; no lab IO."""
import hashlib,json,os,signal,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
from debug_failure_hold import Policy
class TestStop(BaseException):pass
class SnapshotTests(unittest.TestCase):
 def policy(self,base):
  source=base/'source';source.mkdir(mode=0o700);policy=base/'publication-policy.json';policy.write_text(json.dumps({'schemaVersion':1,'literalFiles':{n:{'maxBytes':16777216,'required':True}for n in('summary.json','junit.xml','diagnostic-events.safe.jsonl')},'logDirectories':[],'maxFiles':10,'maxTotalBytes':16777216}));policy.chmod(0o600)
  config=base/'config.json';config.write_text(json.dumps(dict(schemaVersion=1,enabled=True,runId='host-snapshot-counter',nonce='f'*32,sourceRoot=str(source),privateRoot=str(base/'private'),publicStage=str(base/'public'),moduleIds=['domain-enter'],domainRequiredModules=[],publicationPolicy={'path':str(policy),'sha256':hashlib.sha256(policy.read_bytes()).hexdigest()})));config.chmod(0o600)
  return Policy(config,hashlib.sha256(config.read_bytes()).hexdigest(),sleeper=lambda _:(_ for _ in()).throw(TestStop()))
 def test_actual_external_memory_snapshot_preserves_raw_and_omits_private_identity(self):
  with tempfile.TemporaryDirectory()as temporary:
   base=Path(temporary);base.chmod(0o700);policy=self.policy(base);native=base/'owned-native';native.mkdir(mode=0o700);path=native/'memory.private.jsonl'
   raw=(json.dumps(dict(phase='on-hold',epochNs=123,monotonicNs=456,currentBytes=1024,maxBytes=6144,peakBytes=2048,reserveBytes=614,thresholdBytes=5530,events={'oom_kill':0},ownRssBytes=[dict(role='assignment-agent',pid=123,birth='4',uid=os.getuid(),pgid=123,state='T',parentPid=1,cgroup='/private/secret-cgroup',rssBytes=512,returncode=None)],controller={'argv':['private-token']},privateToken='never-public'))+'\n').encode();path.write_bytes(raw);path.chmod(0o600)
   result=policy.snapshot('memory',{'path':str(path),'scopeRoot':str(native),'kind':'memory'});public=result.read_bytes();self.assertNotIn(b'secret-cgroup',public);self.assertNotIn(b'private-token',public);self.assertNotIn(b'never-public',public);self.assertIn(b'1024',public)
   self.assertEqual(raw,path.read_bytes());self.assertEqual(raw,(policy.root/'snapshots/memory.private.log').read_bytes());receipt=json.loads((policy.root/'snapshots/memory.receipt.private.json').read_text());self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt['snapshotSha256']);self.assertEqual(len(raw),receipt['sourceBeforeBytes'])
 def test_full_log_publication_error_still_has_failing_core_marker_without_cleanup(self):
  with tempfile.TemporaryDirectory()as temporary:
   base=Path(temporary);base.chmod(0o700);policy=self.policy(base)
   def failed():raise OSError('controlled full-log publisher unavailable')
   policy.publish_full_logs=failed
   with patch('debug_failure_hold.signal.signal'),self.assertRaises(TestStop):policy.hold('MODULE_NONPASS',module_id='domain-enter')
   marker=json.loads((policy.stage/'debug-state.json').read_text());self.assertEqual('DEBUG_HOLD',marker['state']);summary=json.loads((policy.stage/'summary.json').read_text());self.assertEqual('error',summary['status']);self.assertEqual('DEBUG_LOG_CAPTURE_FAILED',summary['reason']);self.assertFalse(summary['cleanupPerformed']);self.assertIn(b'<error', (policy.stage/'junit.xml').read_bytes());self.assertTrue((policy.root/'HOLD.private.json').exists())
if __name__=='__main__':unittest.main()
