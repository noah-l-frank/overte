"""Original provider/actual kernel custody, no audio hardware or full cleanup claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest,uuid,json
from unittest.mock import patch
from self_tests.pico_audio_source_batch_fixture import AuthBundleFixture
from adapters.pico4.audio_pc_originals import AudioPCActorOriginals
class BatchTests(unittest.TestCase):
 def fixture(self):
  f=AuthBundleFixture();self.addCleanup(f.doCleanups);f.setUp();self.pc=f.fixture;return self.pc
 def test_nine_original_queries_one_transport_call_and_all_distinct_nonces(self):
  pc=self.fixture();self.assertEqual(4,pc.actor.version);ids=tuple(uuid.uuid4().hex for _ in range(9));before=len(pc.pc.requests)
  peer=pc.pc.peer();batch=peer.sources(ids)
  self.assertEqual(1,len(pc.pc.requests)-before);self.assertEqual(9,len(batch['packets']))
  self.assertEqual(list(ids),[p['captureId'] for p in batch['packets']])
  self.assertEqual(9,len({p['requestId'] for p in batch['packets']}));self.assertTrue(all(p['source'] is None for p in batch['packets']))
 def test_duplicate_or_tenth_capture_refuses_before_transport(self):
  pc=self.fixture();peer=pc.pc.peer();ticket=uuid.uuid4().hex;before=len(pc.pc.requests)
  for ids in ((ticket,ticket),tuple(uuid.uuid4().hex for _ in range(10))):
   with self.assertRaises(Exception):peer.sources(ids)
  self.assertEqual(before,len(pc.pc.requests))
 def test_wrong_capture_and_reused_inner_nonce_refuse_original_batch(self):
  pc=self.fixture();ids=tuple(uuid.uuid4().hex for _ in range(2));original=pc.pc.call
  for defect in ('capture','nonce'):
   def changed(root,action,**fields):
    packet=original(root,action,**fields)
    if action=='preview-source-batch':
     if defect=='capture':packet['packets'][1]['captureId']=uuid.uuid4().hex
     else:packet['packets'][1]['requestId']=packet['packets'][0]['requestId']
    return packet
   peer=pc.pc.peer();peer.call=changed
   with self.assertRaises(Exception):peer.sources(ids)
 def test_batch_cannot_read_unretired_recorder_or_replay_input(self):
  pc=self.fixture();actor=pc.actor;ticket=uuid.uuid4().hex
  actor.arm(ticket,3.25,wait_ready=False);before=len(pc.pc.requests)
  with actor.held(),self.assertRaises(Exception):actor._sources((ticket,))
  self.assertEqual(before,len(pc.pc.requests));self.assertEqual(1,len(actor.jobs))
  pc.pc.advance(3.3);actor.wait_saved(ticket);actor.retire_recorders()
 def test_actual_retired_worker_batch_advances_one_history_and_passive_original_per_poll(self):
  pc=self.fixture();actor=pc.actor;ticket=uuid.uuid4().hex
  actor.arm(ticket,3.25,wait_ready=False);pc.pc.advance(3.3);actor.wait_saved(ticket);actor.retire_recorders()
  before=len(actor.frames);reads=actor.raws.state['reads'];requested=len(pc.pc.requests)
  with actor.held():first=actor._sources((ticket,))
  self.assertEqual(before+1,len(actor.frames));self.assertEqual(reads+1,actor.raws.state['reads']);self.assertEqual(requested+1,len(pc.pc.requests))
  self.assertEqual('retired',first[ticket]['source']['state']);self.assertIsNone(actor.executor)
  reader=AudioPCActorOriginals(actor.store.path);self.addCleanup(reader.close)
  self.assertEqual(first,reader.original(len(actor.frames)-1)['packets'])
  with actor.held():second=actor._sources((ticket,))
  self.assertGreater(second[ticket]['sequence'],first[ticket]['sequence']);self.assertNotEqual(second[ticket]['requestId'],first[ticket]['requestId'])

 def test_next_arm_reads_all_completed_originals_once_without_future_success_authority(self):
  pc=self.fixture();actor=pc.actor;first=uuid.uuid4().hex;second=uuid.uuid4().hex
  actor.arm(first,3.25,wait_ready=False);pc.pc.advance(3.3);actor.wait_saved(first)
  before=len(pc.pc.requests);actor.arm(second,3.25,wait_ready=False)
  requests=pc.pc.requests[before:];batches=[r for r in requests if r['action']=='preview-source-batch']
  self.assertEqual(1,len(batches));self.assertEqual(first,batches[0]['fields']['capture_ids'])
  self.assertEqual(0,len([r for r in requests if r['action']=='preview-source' and r['fields']['capture_id']==first]))
  previous=actor.packet_for(actor.job(first));self.assertEqual('completed',previous['source']['state'])
  self.assertEqual(actor.job(first)['request'],previous['source']['armRequestId'])
  pc.pc.advance(3.3);actor.wait_saved(second);actor.retire_recorders()

 def test_completed_future_with_missing_actual_batch_source_fails_before_new_capture_and_stays_sticky(self):
  pc=self.fixture();actor=pc.actor;first=uuid.uuid4().hex;second=uuid.uuid4().hex
  actor.arm(first,3.25,wait_ready=False);pc.pc.advance(3.3);actor.wait_saved(first)
  self.assertTrue(actor.jobs[first].done());original=pc.pc.worker.run
  def missing(request):
   packet=original(request)
   if request['action']=='preview-source-batch':packet['packets'][0]['source']=None
   return packet
  pc.pc.worker.run=missing
  with self.assertRaises(Exception):actor.arm(second,3.25,wait_ready=False)
  error=actor.source_batch_failure;self.assertIsNotNone(error);self.assertIsNotNone(error[1]);self.assertTrue(actor.raws.stopped)
  self.assertNotIn(second,actor.jobs);before=len(pc.pc.requests)
  with self.assertRaises(Exception):actor.arm(second,3.25,wait_ready=False)
  self.assertEqual(before,len(pc.pc.requests));self.assertIs(error,actor.source_batch_failure)

 def test_measured_shared_authority_wire_reconstructs_all_nine_originals_and_saves_actual_bytes(self):
  pc=self.fixture();ids=tuple(uuid.uuid4().hex for _ in range(9));wire=pc.pc.worker.run(dict(action='preview-source-batch',capture_ids=','.join(ids),request_id=uuid.uuid4().hex))
  from adapters.pico4.audio_pc_batch import packets
  full=packets(wire);self.assertEqual(9,len(full));self.assertEqual(list(ids),[p['captureId'] for p in full])
  expanded=dict(audioPreviewSourceBatchVersion=1,requestId=wire['requestId'],packets=full)
  saving=len(json.dumps(expanded))-len(json.dumps(wire));self.assertGreater(saving,4096)
  for row,value in zip(wire['packets'],full):self.assertEqual(value,dict(wire['authority'],**row))
  for defect in ('missing','overlap'):
   changed=deepcopy(wire)
   if defect=='missing':changed.pop('authority')
   else:changed['packets'][0]['provider']=deepcopy(wire['authority']['provider'])
   with self.assertRaises(Exception):packets(changed)
