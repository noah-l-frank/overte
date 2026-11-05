"""The original real PC CLI talks only to a short owned model fixture."""
import json,threading,unittest,uuid
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_peer import PicoAudioPeer
from self_tests import test_pico_audio_pc_start as pc_fixture
from voice_peer import runtime
from self_tests.pico_audio_source_batch_fixture import AuthBundleFixture
OriginalModelPC=pc_fixture.ModelPC
class HttpModelPC(OriginalModelPC):
 def __init__(self,test):
  super().__init__(test)
  self.http=ThreadingHTTPServer(('127.0.0.1',0),runtime.make_handler(self.worker))
  self.http_thread=threading.Thread(target=self.http.serve_forever,name='owned-pc-source-cli-fixture',daemon=True);self.http_thread.start()
  source=PrivateFeatureState(self.root/'session.json');old=source.read()
  source.write(dict(url='http://127.0.0.1:'+str(self.http.server_address[1]),token=self.worker.token),old)
 def peer(self):return PicoAudioPeer(self.config,None,lambda:True,epoch_ms=self.native.epoch)
 def close(self):
  try:super().close()
  finally:
   self.http.shutdown();self.http.server_close();self.http_thread.join(timeout=5)
   if self.http_thread.is_alive():raise RuntimeError('Owned PC CLI HTTP fixture did not close')
class CliBatchTests(unittest.TestCase):
 def test_actual_cli_preserves_nine_original_source_packets_in_the_original_actor_bank(self):
  fixture=AuthBundleFixture();self.addCleanup(fixture.doCleanups)
  with patch.object(pc_fixture,'ModelPC',HttpModelPC):fixture.setUp()
  self.pc=fixture.fixture;actor=self.pc.actor;ids=tuple(uuid.uuid4().hex for _ in range(9));reads=actor.raws.state['reads']
  with actor.held():
   actor._begin('cli-boundary-check',None);batch=actor.peer(actor._pc_reply).sources(ids)
   self.assertEqual(reads+1,actor.raws.state['reads']);reference=actor.state['pending']['raws'][-1]['rawReference']
   from adapters.pico4.audio_pc_batch import packets
   wire=json.loads(actor.raws.literal(reference));self.assertEqual(batch['packets'],packets(wire));self.assertEqual(batch['requestId'],wire['requestId']);self.assertEqual(9,len(batch['packets']))
   self.assertTrue(all(row['source'] is None for row in batch['packets']));self.assertEqual(list(ids),[row['captureId'] for row in batch['packets']])
   self.assertEqual(9,len({row['requestId'] for row in batch['packets']}))
   value=dict(actor.state);value['pending']=None;actor._save(value);actor.bound()
