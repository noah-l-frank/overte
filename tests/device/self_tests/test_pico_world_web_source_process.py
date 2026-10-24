"""Same fourteen normal World steps and actual separate original source pass.

Product/Qt/V8/OS remain analytical producers. Child PID/program, HTTP receipts,
parent nonce consumption, kernel ESRCH and immutable files are actual host IO.
No whole/stereo/product-retirement result is asserted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.world_web_source_pass import WorldSourceReturn,EXPORT,CONSUMPTION
from fixture.chat_observer_process import LinuxChatObserverProcess
from self_tests import test_pico_world_web_normal_close as existing
from self_tests.pico_world_web_process_fixture import WorldProductSources

WORKER='''import os,json,sys
sys.path.insert(0,DEVICE_PATH)
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.world_web_binding import PicoWorldWebBinding
from adapters.pico4.world_web_source_pass import run,WorldSourcePass
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending
from feature_journeys.witness import Client
from self_tests.pico_world_web_process_fixture import IndependentWorldSources
config=PrivateFeatureState(sys.argv[2]).read();target=IndependentWorldSources(config['sources']);clock=target.clock
os.environ.update(OVERTE_E2E_SCENE_URL=target.scene_url,OVERTE_PICO_NORMAL_SCRIPTS='1',OVERTE_ANDROID_E2E_DEBUG='1',OVERTE_PICO_OPENXR_INPUT='1')
flow=PicoWorldWebBinding(target).prefix(target.selector,PhaseFixtureReader(Client(config['fixtureBase'],config['actorToken']),
    config['sources']['run'],'world-web',epoch_ms=clock.epoch,monotonic=clock.now),config['sources']['foreign'],role='actor',require_new_actor=True)
stereo=None
if config.get('stereo',False):
 from adapters.pico4.world_web_stereo_join import WorldStereoJoin
 stereo=WorldStereoJoin(flow,config['sources']['artifacts']);capture=stereo.capture
 def captured(before=None):
  value=capture(before);print(json.dumps(dict(kind='stereo',original=value),separators=(',',':')),flush=True);return value
 stereo.capture=captured
request=flow.source.client.request
def transport(path,*args,**kwargs):
 value=request(path,*args,**kwargs)
 if config['losePublication'] and path=='/runs/'+flow.run+'/samples':raise OSError('lost applied independent publication')
 return value
flow.source.client.request=transport
publish=flow.publish
def observed():
 try:value=publish()
 except PhasePending:
  print(json.dumps(dict(kind='pending')),flush=True);raise
 print(json.dumps(dict(kind='publication',sample=value),separators=(',',':')),flush=True);return value
flow.publish=observed
original=WorldSourcePass.publish_return
def returned(self):
 value=original(self);print(json.dumps(dict(kind='exported')),flush=True);return value
WorldSourcePass.publish_return=returned
def gate(_seconds=0):
 if sys.stdin.readline().strip() not in ('publish','consume'):raise ValueError('No ordinary target input can cross this scheduling channel')
print(json.dumps(dict(kind='ready')),flush=True)
try:
 gate();result=run(flow,config['request'],monotonic=clock.now,sleep=gate,duration=120,stereo=stereo)
 if result!=0:raise AssertionError('Original source pass did not consume Parent nonce')
 print(json.dumps(dict(kind='consumed')),flush=True)
 if sys.stdin.readline().strip()!='exit':raise ValueError('Original process release missing')
except BaseException as error:
 import traceback
 rows=[];current=error
 while current is not None and len(rows)<12:
  rows.append(dict(type=type(current).__name__,traceback=''.join(traceback.format_exception(type(current),current,current.__traceback__,chain=False))));current=current.__context__
 PrivateFeatureState(target.path/'first-worker-exception-chain.json').write(dict(errors=rows),None)
 raise
finally:target.close()
'''


class WorldWebSourceProcessTests(unittest.TestCase):
    run=existing.WorldWebNormalCloseTests.run
    stop=existing.WorldWebNormalCloseTests.stop
    activate=existing.WorldWebNormalCloseTests.activate
    call=existing.WorldWebNormalCloseTests.call
    cleanup_call=existing.WorldWebNormalCloseTests.cleanup_call
    def setUp(self):
        existing.WorldWebNormalCloseTests.setUp(self);self.sources=WorldProductSources(self);self.addCleanup(self.sources.close)
        self.request=uuid.uuid4().hex;self.marker=uuid.uuid4().hex;self.worker=None;self.process=None
        self.addCleanup(self.close_worker)
    def launch(self,*,lose=False,stereo=False):
        self.entry=self.root/'world-original-source-worker.py'
        self.entry.write_text(WORKER.replace('DEVICE_PATH',repr(str(Path(__file__).resolve().parents[1]))));self.entry.chmod(0o600)
        self.config=PrivateFeatureState(self.root/'world-original-source-config.json')
        self.config.write(dict(sources=self.sources.configuration(),fixtureBase=self.url,actorToken=self.actor.source.client.token,
            request=self.request,losePublication=lose,stereo=stereo),None)
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(self.config.path)],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PYTHONDONTWRITEBYTECODE':'1','OVT_WORLD_SOURCE_WORKER_OWNER':self.marker})
        self.receive('ready',timeout=10)
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        def owned(pid):
            path=Path('/proc')/str(pid)
            try:
                raw=(path/'environ').read_bytes()
                return len(raw)<=65536 and path.stat().st_uid==os.geteuid() and raw.split(b'\0').count(('OVT_WORLD_SOURCE_WORKER_OWNER='+self.marker).encode())==1
            except FileNotFoundError:return False
        self.process=LinuxChatObserverProcess(identity,self.entry,self.config.path,
            hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest(),hashlib.sha256(self.entry.read_bytes()).hexdigest(),owned)
    def close_worker(self):
        if self.worker is not None:
            if not self.worker.stdin.closed:self.worker.stdin.close()
            self.worker.wait(timeout=10)
            for name,stream in (('stdout',self.worker.stdout),('stderr',self.worker.stderr)):
                raw=stream.read();path=self.root/('retained-worker-'+name+'.txt');path.write_bytes(raw);path.chmod(0o600);stream.close()
        if self.process is not None:self.assertTrue(self.process.close())
    def receive(self,kind,*,timeout=25):
        self.assertTrue(select.select([self.worker.stdout],[],[],timeout)[0]);raw=self.worker.stdout.readline()
        if not raw:
            self.worker.wait(timeout=5);error=self.worker.stderr.read(32768);path=self.root/'first-worker-error.txt';path.write_bytes(error);path.chmod(0o600)
            self.fail(error.decode('utf-8','replace'))
        value=json.loads(raw);self.assertEqual(kind,value['kind']);return value
    def command(self,action,kind=None):
        self.worker.stdin.write((action+'\n').encode());self.worker.stdin.flush()
        if kind:return self.receive(kind)
    def original_pass(self):
        self.primary.prepare();self.primary.observe();self.launch();self.command('publish','publication')
        for index in range(14):
            call=self.call(index)
            if index==0:
                calls=list(self.sources.calls);files={path.name:path.read_bytes() for path in self.target.feature_root.iterdir()}
                self.command('publish','pending')
                self.assertFalse(set(self.sources.calls[len(calls):])&{'feature','diagnostic','browser','runtime','scripts','objects'})
                self.assertEqual(files,{path.name:path.read_bytes() for path in self.target.feature_root.iterdir()})
            self.primary.act(call);primary=self.primary.observe();actor=self.command('publish','publication')['sample']
            self.assertEqual(primary['state'],actor['state']);self.assertEqual([],actor['artifacts'])
        self.primary.normal_close(self.cleanup_call());self.primary.observe();last=self.command('publish','publication')['sample']
        self.receive('exported');self.assertIn('script:world-web-client',last['resources'])
        self.expected=dict(runId=self.run,fixtureUrl=self.fixture_url,foreignFixtureUrl=self.primary.foreign,prefixScope=deepcopy(self.primary.scope),
            binding=deepcopy(self.primary.state['binding']),ownerToken=self.primary.state['ownerToken'],
            producerHostProcessIdentity=self.process.process_identity,originalRequestId=self.request)
    def returned(self,**changes):
        return self.facade.source_return(self.target.selector,self.primary,self.process,{**self.expected,**changes})
    def test_actual_separate_actor_normal_fourteen_stop_consumed_parent_nonce_then_original_esrch(self):
        self.original_pass();owner=self.returned();self.assertEqual(16,owner.graph.history.last['sample']['sequence'])
        owner.acknowledge();before=len(self.sources.calls);self.command('consume','consumed')
        self.assertTrue(all(action=='host' for action in self.sources.calls[before:]))
        self.command('exit');self.worker.wait(timeout=5);receipt=owner.finish()
        self.assertEqual('ESRCH',receipt['result']['processReturn']['processAbsence']['errorSymbol'])
        self.assertEqual(['script:world-web-client'],receipt['result']['retainedResources'])
        self.assertFalse(owner.graph.vm.facts['retired']);self.assertEqual(receipt,owner.receipt())
        self.assertEqual(14,len(owner.graph.owner['completed']));self.assertTrue(all((self.target.feature_root/name).exists() for name in owner.graph.files))
    def test_foreign_return_scope_refuses_before_parent_nonce_or_original_unlink(self):
        self.original_pass();old={path.name:path.read_bytes() for path in self.target.feature_root.iterdir()}
        with self.assertRaises(NativeUIError):self.returned(originalRequestId=uuid.uuid4().hex)
        self.assertFalse((self.target.feature_root/CONSUMPTION).exists())
        self.assertEqual(old,{path.name:path.read_bytes() for path in self.target.feature_root.iterdir()})
    def test_same_bytes_new_original_inode_refuses_before_consumption(self):
        self.original_pass();root=self.target.feature_root;history=root/'pico-world-web-prefix-actor-sources.json'
        original=history.with_name('retained-before-replacement.json');history.rename(original)
        history.write_bytes(original.read_bytes());history.chmod(0o600)
        with self.assertRaises(NativeUIError):self.returned()
        self.assertTrue(original.exists());self.assertFalse((root/CONSUMPTION).exists());self.assertTrue((root/EXPORT).exists())
    def test_lost_applied_parent_nonce_uses_same_original_consumption_without_rewrite(self):
        self.original_pass();owner=self.returned();store=owner.receiver.ack_store;write=store.write;writes=[]
        def lost(value,previous):
            write(value,previous);writes.append(deepcopy(value));raise OSError('lost original Parent nonce write reply')
        with patch.object(store,'write',side_effect=lost):
            with self.assertRaises(OSError):owner.acknowledge()
            with self.assertRaises(NativeUIError):owner.acknowledge()
        self.assertEqual(1,len(writes));self.command('consume','consumed');self.command('exit');self.worker.wait(timeout=5)
        receipt=owner.finish();self.assertEqual(writes[0],owner.receiver.store.read()['consumption'])
        self.assertEqual('ESRCH',receipt['result']['processReturn']['processAbsence']['errorSymbol'])
        self.assertTrue((self.target.feature_root/EXPORT).exists())

    def test_foreign_parent_nonce_cannot_complete_original_parent_return_or_unlink_sources(self):
        self.original_pass();owner=self.returned();owner.acknowledge();store=owner.receiver.ack_store
        value=store.read();value['nonce']=uuid.uuid4().hex;store.write(value,store.read())
        names=set(owner.graph.files)|{EXPORT};old={name:(self.target.feature_root/name).read_bytes() for name in names}
        inventory={path.name for path in self.target.feature_root.iterdir()}
        self.command('consume','consumed');self.command('exit');self.worker.wait(timeout=5);self.assertEqual(0,self.worker.returncode)
        with self.assertRaises(NativeUIError):owner.finish()
        self.assertEqual(old,{name:(self.target.feature_root/name).read_bytes() for name in names})
        self.assertEqual(inventory,{path.name for path in self.target.feature_root.iterdir()})
        self.assertNotEqual(owner.receiver.intent['nonce'],owner.receiver.store.read()['consumption']['nonce'])
        self.assertEqual('consumption-issued',owner.store.read()['phase']);self.assertFalse(owner.complete)

    def test_actual_applied_lost_publication_exits_without_return_or_cold_resend(self):
        self.primary.prepare();self.primary.observe();self.launch(lose=True);self.command('publish');self.worker.wait(timeout=10)
        self.assertNotEqual(0,self.worker.returncode);root=self.target.feature_root
        self.assertFalse((root/EXPORT).exists());old={path.name:path.read_bytes() for path in root.iterdir()};count=len(self.sources.calls)
        cold=self.facade.prefix(self.target.selector,self.actor.source,self.foreign,role='actor',require_new_actor=True)
        with self.assertRaises(NativeUIError):cold.publish()
        self.assertEqual(old,{path.name:path.read_bytes() for path in root.iterdir()});self.assertEqual(count,len(self.sources.calls))


if __name__=='__main__':unittest.main()
