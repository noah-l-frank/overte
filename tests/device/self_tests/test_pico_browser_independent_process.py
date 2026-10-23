"""Original Parent and separate Actor share original analytical product sources.

Real host processes, HTTP/stream IO, files and existing owners; all actual
product, GPU, Qt, OS and native clock producers are explicit fixture seams.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import unittest
import uuid
from types import MethodType

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.tablet_web_binding import PicoTabletWebBinding
from feature_journeys.scenarios import VERSION
from fixture.chat_observer_process import LinuxChatObserverProcess
from self_tests import test_pico_tablet_web_stereo_flow as existing
from self_tests import test_pico_browser_capture_retirement as capture_existing
from self_tests.pico_browser_process_fixture import ProductSources

WORKER='''import json,sys
sys.path.insert(0,DEVICE_PATH)
from types import MethodType
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.tablet_web_binding import PicoTabletWebBinding
from adapters.pico4.browser_actor_graph import PicoBrowserActorExport
from adapters.pico4.feature_observer import run
from feature_journeys.phase_fixture import PhaseRetired
from self_tests.pico_browser_process_fixture import IndependentBrowserSources
config=PrivateFeatureState(sys.argv[2]).read();target=IndependentBrowserSources(config['sources']);clock=target.clock
# Only execution scheduling is controlled here; the production loop acquires
# all original product/phase sources, owns publication/export and consumes ACK.
def gate(_seconds=0):
    action=sys.stdin.readline().strip()
    if action not in ('publish','retire','consume'):raise ValueError('No other independent fixture scheduling operation')
def feature(self,*args,**kwargs):
    actor=PicoTabletWebBinding.feature(self,*args,**kwargs);publish=actor.publish
    def observed():
        value=publish();print(json.dumps(dict(kind='publication',sample=value),separators=(',',':')),flush=True);return value
    actor.publish=observed;return actor
target.feature=MethodType(feature,target)
original_return=PicoBrowserActorExport.publish_return
def returned(self):
    value=original_return(self);print(json.dumps(dict(kind='retired')),flush=True);return value
PicoBrowserActorExport.publish_return=returned
print(json.dumps(dict(kind='ready')),flush=True)
try:
 gate()
 result=run(target,dict(area='tablet-web',target='target',runId=config['sources']['run'],fixtureUrl=config['fixtureBase'],
    actorToken=config['actorToken'],artifactRoot=config['sources']['artifacts'],foreignFixtureUrl=config['sources']['foreign'],
    originalRequestId=config['request'],durationSeconds=1800),monotonic=clock.now,sleep=gate)
 if result!=0:raise AssertionError('Original production observer did not consume Parent return')
 print(json.dumps(dict(kind='consumed')),flush=True)
 if sys.stdin.readline().strip()!='exit':raise ValueError('Original terminal fixture was not released')
finally:target.close()
'''


class PicoBrowserIndependentProcessTests(unittest.TestCase):
    def setUp(self):
        h=existing.PicoTabletWebStereoFlowTests();h.setUp();self.addCleanup(h.doCleanups)
        self.f,self.model=h.fixture,h.model
        self.batches=[];self.raw='';self.batch_sequence=0;self.mutate=None;self.lose=False
        self.f.target._tablet_web_retired_captures_observer=self.reader
        self.addCleanup(self.close_capture)
        self.sources=ProductSources(self.f,self.model);self.addCleanup(self.sources.close)
        self.entry=self.f.path/'browser-original-source-worker.py'
        self.entry.write_text(WORKER.replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[1]))));self.entry.chmod(0o600)
        self.request=uuid.uuid4().hex;self.marker=uuid.uuid4().hex
        self.config=PrivateFeatureState(self.f.path/'browser-original-source-config.json')
        self.config.write(dict(sources=self.sources.configuration(),fixtureBase=self.f.url,actorToken=self.f.actor_token,request=self.request),None)
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(self.config.path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={'PYTHONDONTWRITEBYTECODE':'1','OVT_BROWSER_SOURCE_WORKER_OWNER':self.marker})
        self.addCleanup(self.close_worker);self.receive('ready',timeout=10)
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        def owned(pid):
            path=Path('/proc')/str(pid)
            try:
                with (path/'environ').open('rb') as stream:raw=stream.read(65537)
                return len(raw)<=65536 and path.stat().st_uid==os.geteuid() and raw.split(b'\0').count(
                    ('OVT_BROWSER_SOURCE_WORKER_OWNER='+self.marker).encode())==1
            except FileNotFoundError:return False
        self.process=LinuxChatObserverProcess(identity,self.entry,self.config.path,
            hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest(),hashlib.sha256(self.entry.read_bytes()).hexdigest(),owned)
        self.addCleanup(self.process.close)

    reader=capture_existing.PicoBrowserCaptureRetirementTests.reader

    def close_capture(self):
        owner=self.f.primary.remote_capture_retirement
        if owner is not None:self.assertTrue(owner.catalog.close_host())

    def close_worker(self):
        if not self.worker.stdin.closed:self.worker.stdin.close()
        self.worker.wait(timeout=10)
        for stream in (self.worker.stdout,self.worker.stderr):stream.close()

    def receive(self,kind,*,timeout=25):
        self.assertTrue(select.select([self.worker.stdout],[],[],timeout)[0]);raw=self.worker.stdout.readline()
        if not raw:
            self.worker.wait(timeout=5)
            self.fail('Original independent worker ended: '+self.worker.stderr.read(32768).decode('utf-8','replace'))
        result=json.loads(raw);self.assertEqual(kind,result['kind']);return result

    def command(self,action,kind=None):
        self.worker.stdin.write((action+'\n').encode());self.worker.stdin.flush()
        if kind is not None:return self.receive(kind)

    def observe(self):
        return self.f.primary.observe(dict(contractVersion=VERSION,runId=self.f.run,afterSequence=0))

    def returned(self):
        target=self.f.target
        target.check_flow=MethodType(PicoTabletWebBinding.check_flow,target)
        lock=target.lock
        def original_lock(_target,source_lock=None):
            self.assertEqual('target',_target);self.assertTrue(source_lock is None or source_lock is lock);return lock
        target._lock=original_lock
        with lock.held():owner=self.f.primary.owner()
        expected=dict(runId=self.f.run,fixtureUrl=self.f.fixture_url,foreignFixtureUrl=self.f.primary.foreign_url,
            artifactRoot=str(self.f.artifacts),sceneUrl=target.scene_url,binding=owner['binding'],ownerToken=owner['ownerToken'],
            producerHostProcessIdentity=self.process.process_identity,originalRequestId=self.request)
        return PicoTabletWebBinding._tablet_web_actor_return(target,'target',self.f.primary,self.process,expected)

    def original_return(self):
        f=self.f;f.activate();f.primary.prepare();self.observe();self.command('publish','publication')
        f.act('open');primary=self.observe();actor=self.command('publish','publication')['sample']
        self.assertTrue(primary['state']['open']);self.assertEqual(primary['state'],actor['state'])
        self.assertNotEqual(primary['artifacts'][0]['name'],actor['artifacts'][0]['name'])
        f.act('close');self.observe();self.command('publish','publication')
        f.activate('cleanup');f.primary.cleanup(dict(contractVersion=VERSION,runId=f.run))
        for _ in range(14):self.observe();self.command('publish','publication');f.clock.sleep(.25)
        f.client.close();return self.consume_original_return()

    def consume_original_return(self):
        self.command('retire','retired');owner=self.returned();owner.acknowledge()
        queries=len(self.sources.calls);self.command('consume','consumed')
        # The production loop retains its real host-monotonic deadline after
        # export. Only this analytical fixture transports that local clock over
        # RPC; no product/candidate/epoch/source query may occur after export.
        self.assertTrue(all(action=='host' for action in self.sources.calls[queries:]))
        self.command('exit');self.worker.wait(timeout=5);result=owner.finish()
        self.assertTrue(owner.complete);self.assertEqual(result,owner.receipt());return owner

    def test_original_parent_and_separate_actor_open_close_quiet_then_typed_original_factory_return(self):
        owner=self.original_return();f=self.f
        captures=f.primary.retire_returned_actor_captures(owner);capture=f.primary.remote_capture_retirement
        self.assertTrue(capture.completed);self.assertEqual(captures,capture.receipt());self.assertTrue(captures['complete'])
        self.assertEqual({'primary','actor'},{row['owner']['role'] for row in capture.proofs})
        self.assertGreaterEqual(len(capture.frames),3);self.assertGreaterEqual(len(self.batches),3)
        self.assertTrue(owner.close_host())
        self.assertIs(f.primary.adapter,f.target);self.assertIsNone(f.actor.actor_retirement)
        self.assertTrue(all(store.path.exists() for store in owner.stores.values()))
        self.assertTrue(f.primary.store.path.exists());self.assertFalse(captures.get('deviceAcceptance',False))

    def test_complete_shared_journey_then_original_independent_return_and_all_capture_retirement(self):
        from copy import deepcopy
        from feature_journeys.engine import Journey
        from feature_journeys.evidence import read_private_artifact
        from feature_journeys.stereo_browser_evidence import PROFILE
        from self_tests.test_stereo_navigation_evidence import POLICY
        f=self.f;reports=[];policy=deepcopy(POLICY);policy['profile']=PROFILE
        def invoke(operation,values):return getattr(f.primary,operation.rsplit('.',1)[1])(values)
        def witness():self.command('publish','publication');return f.client.observe()
        journey=Journey('tablet-web',f.run,f.fixture_url,invoke=invoke,witness=witness,activate=f.client.activate,
            read_artifact=lambda name:read_private_artifact(f.artifacts,name),image_policy=dict(screen=policy),
            continuity=lambda *_args:None,monotonic=f.clock.now,epoch_ms=f.clock.epoch,sleep=f.clock.sleep,report=reports.append)
        journey.execute();self.assertEqual(28,len(journey.phases));self.assertTrue(reports[-1]['sequenceCompleted'])
        self.assertTrue(reports[-1]['cleanupSucceeded']);self.assertFalse(reports[-1]['deviceAcceptance'])
        if f.run in f.server.browser_resources.runs:f.client.close()
        owner=self.consume_original_return();captures=f.primary.retire_returned_actor_captures(owner)
        self.assertTrue(captures['complete']);capture=f.primary.remote_capture_retirement
        self.assertTrue(capture.completed);self.assertEqual(captures,capture.receipt());self.assertTrue(owner.close_host())
        self.assertGreater(len(capture.proofs),2);self.assertEqual({'primary','actor'},{row['owner']['role'] for row in capture.proofs})
        self.assertTrue(all(row['store'].path.exists() for row in capture.catalog.rows.values()))
        with self.assertRaises((ValueError,RuntimeError)):f.primary.finalize()

    def test_changed_original_actor_png_refuses_remote_capture_before_any_native_query(self):
        owner=self.original_return();image=next(iter(owner.graph.images.values()))['png']
        path=self.f.artifacts/image['name'];replacement=path.with_name('changed-original-image.png')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError):self.f.primary.retire_returned_actor_captures(owner)
        self.assertEqual([],self.batches);capture=self.f.primary.remote_capture_retirement
        self.assertTrue(capture.failed);self.assertFalse(capture.completed);self.assertTrue(path.exists())
        self.assertTrue(all(store.path.exists() for store in owner.stores.values()))

    def test_uncertain_original_capture_reply_keeps_intent_and_cannot_replay_or_adopt_cold(self):
        owner=self.original_return();self.lose=True
        with self.assertRaises(NativeUIError):self.f.primary.retire_returned_actor_captures(owner)
        capture=self.f.primary.remote_capture_retirement;self.assertTrue(capture.failed);self.assertFalse(capture.completed)
        self.assertEqual(1,len(self.batches));value=capture.store.read();self.assertEqual('reading',value['phase'])
        self.assertIsNotNone(value['pending']);before=len(self.batches)
        with self.assertRaises(NativeUIError):self.f.primary.retire_returned_actor_captures(owner)
        with self.assertRaises(NativeUIError):capture.receipt()
        self.assertEqual(before,len(self.batches));self.assertTrue(capture.catalog.rows)
        self.assertTrue(all(row['store'].path.exists() for row in capture.catalog.rows.values()))


if __name__=='__main__':unittest.main()
