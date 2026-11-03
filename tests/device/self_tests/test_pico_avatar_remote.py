"""Original remote source composition with explicit Avatar/Qt/Rig/GPU models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

# Existing Rig fixtures keep their historical direct-execution import names.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4 import avatar_remote as remote
from adapters.pico4.avatar_remote_source import create
from adapters.pico4.avatar_remote_state import source_store, retained
from adapters.script_journey.history import canonical
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client, Journal
from self_tests.test_emote_rig_measurements import RigPackets
from self_tests.test_pico_emote_model_draws import ModelBoundary
from self_tests.test_native_avatar_render import avatar_source
from self_tests.test_native_feature_observation import probe_source

RUN = 'd'*32
SELF = '22222222-2222-4222-8222-222222222222'
SUBJECT = '11111111-1111-4111-8111-111111111111'
DOMAIN = '33333333-3333-4333-8333-333333333333'


class RemoteBoundary:
    """Reuse the existing actual camera/draw validators and Rig DTO producer."""
    def __init__(self, *, area='avatar-people'):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name); self.root.chmod(0o700)
        self.epoch = 20000; self.clock = 0.; self.okay = True; self.commands = []; self.sequence = 0
        self.sample = None; self.edit = None; self.raw_override = None; self.hosts = []; self.current = None
        self.binding = dict(sourceRevision='a'*40, artifactSha256='b'*64, processIdentity='31:original',
            sessionId=SELF, generation=0, targetFingerprint='c'*64)
        self.lock = ScriptSourceLock(self.root/'script-sources.lock')
        self.journal = Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex', return_value=RUN): self.journal.register(area)
        self.journal.activate(RUN, 'c'*32)
        client = Client('http://controlled.test/feature-fixture/v1', 'r'*64)
        client.request = lambda path, **args:self.journal.phase(RUN, args['phase_nonce'])
        self.phase = PhaseFixtureReader(client, RUN, area, epoch_ms=lambda:self.epoch, monotonic=lambda:self.clock)
        self.gpu = ModelBoundary(); self.rig = RigPackets().native(self.epoch, active=False, restore_epoch=19800)['animation']
        self.native = SimpleNamespace(send=self.send, clock_ms=lambda:self.epoch, guard=lambda:self.okay,
            monotonic=lambda:self.clock, sleep=self.sleep)
        self.adapter = SimpleNamespace(pico_configuration=(None,self.root),
            _avatar_parent_store=lambda target,run:PrivateFeatureState(self.root/('avatar-parent-owner-'+'a'*32+'-'+run+'.json')),
            _script_journey=lambda:SimpleNamespace(state_path=lambda target:self.root/'script-state.json'),
            _script_runtime=lambda target:(None,None,self.binding), _native_feature_observer=lambda target:self.native,
            adb=SimpleNamespace(read_debug_app_file=lambda *args,**kw:self.original()))

    def close(self):
        for owner in self.hosts:
            if not owner.close_host(): raise AssertionError('Original host descriptor remains uncertain')
        self.temporary.cleanup()
    def sleep(self, seconds): self.clock += seconds
    def client(self, session, epoch):
        identity = dict(domainId=DOMAIN, sessionId=session, connected=True,
            domainSession=dict(domainSessionVersion=1, instance=('9' if session==SELF else '8')*32,
                revision=1, connected=True, domainSha256=hashlib.sha256((RUN+':').encode()+uuid.UUID(DOMAIN).bytes).hexdigest(),
                connectionBirth=('7' if session==SELF else '6')*32, connectedEpochMs=10000))
        return dict(requestedEpochMs=epoch, capturedEpochMs=epoch, identity=identity)
    def packet(self, request, *, primary=False, epoch=None, legacy=False):
        epoch = self.epoch if epoch is None else epoch
        source = avatar_source(); subject = {k:deepcopy(v) for k,v in source.items()
            if k in ('modelInstance','rigId','loaded','visible','addedToScene','avatarShouldRender','geometry','pose')}
        subject.update(sessionId=SELF if primary else SUBJECT, avatarInstance=('5' if primary else '4')*32,
            rigId=self.rig['rigId'], rig=deepcopy(self.rig) if legacy else {})
        if not legacy:
            # Explicit remote committed-section/copy boundary model. This does
            # not execute the uncompiled AvatarData/Rig/OtherAvatar producer.
            raw=bytes([1,0,0])+struct.pack('<f',1.0)
            received=dict(kind='joint-data',sequence=max(1,self.sequence),subjectSessionId=subject['sessionId'],jointCount=1,
                parsedEpochMs=epoch-5,committedEpochMs=epoch-4,parseTimestampUs=(epoch-5)*1000,
                bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())
            subject['remoteJointPose']=dict(remoteJointPoseVersion=1,instance=('7' if primary else '6')*32,
                copySequence=max(1,self.sequence),copiedSequence=max(1,self.sequence),externalSequence=max(1,self.sequence),subjectSessionId=subject['sessionId'],
                avatarInstance=subject['avatarInstance'],modelInstance=subject['modelInstance'],rigId=subject['rigId'],
                geometryInstance=subject['geometry']['instance'],
                available=True,inputJointCount=1,skeletonJointCount=1,begunEpochMs=epoch-3,copiedEpochMs=epoch-2,
                capturedEpochMs=epoch-1,relativeJoints=[[0.,0.,0.,1.,.1,.2,.3]],joints=[[0.,0.,0.,1.,.1,.2,.3]],
                received=dict(jointData=received,defaultFlags=None))
        source = dict(picoRemoteAvatarVersion=1 if legacy else 2, runId=RUN,
            clientBefore=self.client(SUBJECT if primary else SELF,epoch), clientAfter=self.client(SUBJECT if primary else SELF,epoch),
            selfSessionId=SUBJECT if primary else SELF, subjectSessionId=SELF if primary else SUBJECT,
            subject=subject, worldRenderInstance=('3'*32 if primary else self.gpu.capture['instance']),
            cameraMode='third person', view=deepcopy(self.gpu.capture['source']['renderTrace']['recordedView']))
        return dict(schemaVersion=1,requestId=request['commandId'],instance=('e' if primary else 'f')*32,sequence=self.sequence,
            processId=31,requestedEpochMs=epoch,capturedEpochMs=epoch,source=source)
    def primary(self):
        self.sequence += 1
        return self.packet(dict(commandId='a'*32), primary=True)
    def send(self, request):
        if self.current is not None:
            value=self.current.store.read(); assert value['phase']=='reading' and value['pending']['request'] is not None
            assert self.current.rows[value['pending']['request']]['value']==request
        self.commands.append(deepcopy(request)); self.sequence += 1; self.sample=self.packet(request)
        if self.edit: self.edit(self.sample)
    def original(self): return self.raw_override if self.raw_override is not None else json.dumps(self.sample)
    def owner(self, primary=None):
        if primary is None: primary=self.primary()
        # Each cold reopening keeps the SAME immutable scope, not a new primary nonce.
        path=source_store(self.adapter,'explicit-model',RUN,area=self.phase.area)
        if path.read() is not None and self.hosts: primary=self.hosts[0].primary
        value=create(self.adapter,'explicit-model',self.phase,SUBJECT,self.lock,primary=primary)
        self.current=value; self.hosts.append(value); return value


class RemoteAvatarTests(unittest.TestCase):
    def setUp(self): self.model=RemoteBoundary(); self.addCleanup(self.model.close)

    def test_real_factory_retains_original_request_raw_phase_and_independent_client_without_input(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); packet=owner.read(); self.assertEqual(m.sample,packet)
            self.assertEqual(1,len(m.commands)); self.assertTrue(retained(m.adapter,'explicit-model'))
            self.assertEqual(SELF,packet['source']['selfSessionId']); self.assertEqual(SUBJECT,packet['source']['subject']['sessionId'])
            raw=owner.raw(owner.state['records'][0]['raw']); self.assertEqual(m.original(),raw)
            self.assertEqual(canonical(m.commands[0]),canonical(owner.rows[owner.state['records'][0]['request']]['value']))
            commands=list(m.commands); cold=m.owner(); self.assertEqual(owner.state,cold.state)
            self.assertEqual(commands,m.commands); self.assertEqual(packet,cold.packets[0])

    def test_unavailable_malformed_and_foreign_native_raw_stays_owned_before_refusal(self):
        for fault in ('unavailable','malformed','same-client','wrong-domain'):
            with self.subTest(fault=fault):
                m=RemoteBoundary(); self.addCleanup(m.close)
                if fault=='unavailable': m.edit=lambda value:value['source'].update(subject=None)
                if fault=='malformed': m.raw_override='{broken original native JSON'
                if fault=='same-client': m.edit=lambda value:value.update(instance='e'*32)
                if fault=='wrong-domain':
                    def wrong(value):
                        for key in ('clientBefore','clientAfter'):
                            identity=value['source'][key]['identity']; identity['domainId']='99999999-9999-4999-8999-999999999999'
                            identity['domainSession']['domainSha256']=hashlib.sha256((RUN+':').encode()+uuid.UUID(identity['domainId']).bytes).hexdigest()
                    m.edit=wrong
                with m.lock.held():
                    owner=m.owner()
                    with self.assertRaises(NativeUIError): owner.read()
                    self.assertEqual('failed',owner.store.read()['phase']); pending=owner.store.read()['pending']
                    self.assertTrue(pending['raw']); self.assertEqual(m.original(),owner.raw(pending['raw'][-1]))
                    commands=list(m.commands); cold=m.owner()
                    with self.assertRaises(NativeUIError): cold.read()
                    self.assertEqual(commands,m.commands)

    def test_actual_source_model_birth_replacement_is_not_adopted_after_first_measurement(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); owner.read(); m.edit=lambda value:value['source']['subject'].update(modelInstance='2'*32)
            with self.assertRaises(NativeUIError): owner.read()
            self.assertEqual('failed',owner.store.read()['phase']); self.assertEqual(2,len(m.commands))

    def test_original_raw_chunk_identical_replacement_refuses_before_next_native_query(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); owner.read(); path=owner.chunks._path(0); raw=path.read_bytes()
            alternate=m.root/'owned-test-replacement'; alternate.write_bytes(raw); alternate.chmod(0o600); alternate.replace(path)
            with self.assertRaises(NativeUIError): owner.read()
            self.assertEqual(1,len(m.commands)); self.assertEqual(raw,path.read_bytes())

    def test_changed_original_provider_phase_keeps_native_raw_without_current_observation(self):
        m=self.model
        # Use an actual allowed normal fixture stimulus from the original
        # provider inventory, not a fabricated successful remote state.
        from feature_journeys.scenarios import actions,expand
        from feature_journeys.fixtures import context
        stimulus=expand(actions('avatar-people')['avatar-url'][0],context(RUN))
        m.edit=lambda value:m.journal.activate(RUN,'b'*32,'avatar-url',stimulus)
        with m.lock.held():
            owner=m.owner()
            with self.assertRaises((NativeUIError,ValueError)): owner.read()
            self.assertEqual(1,len(m.commands)); self.assertEqual('failed',owner.store.read()['phase'])
            self.assertEqual(m.original(),owner.raw(owner.state['pending']['raw'][-1]))

    def test_unavailable_rig_original_is_retained_instead_of_inferred_from_model_or_draw(self):
        m=self.model; m.edit=lambda value:value['source']['subject'].update(remoteJointPose={})
        with m.lock.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError): owner.read()
            self.assertEqual('failed',owner.store.read()['phase'])
            raw=owner.raw(owner.state['pending']['raw'][-1]); self.assertEqual({},json.loads(raw)['source']['subject']['remoteJointPose'])

    def test_delayed_durable_request_retention_sends_zero_native_queries(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); original=owner.retain
            def retain_request(kind,value):
                original(kind,value)
                if kind=='request': m.clock+=2
            owner.retain=retain_request
            with self.assertRaises(NativeUIError): owner.read()
            self.assertEqual([],m.commands); self.assertEqual('failed',owner.store.read()['phase'])
            self.assertIsNotNone(owner.store.read()['pending']['request'])

    def test_delay_inside_original_predispatch_guard_sends_zero_with_frozen_native_epoch(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); original=owner.original_guard; delayed=[]
            def guard():
                valid=original(); root=owner.store.read()
                if root is not None and root['pending'] is not None and root['pending']['request'] is not None and not delayed:
                    delayed.append(True); m.clock+=2
                return valid
            owner.original_guard=guard
            with self.assertRaises(NativeUIError): owner.read()
            self.assertEqual([True],delayed); self.assertEqual([],m.commands)
            self.assertEqual('failed',owner.store.read()['phase'])

    def test_final_durable_save_delay_with_frozen_native_epoch_is_terminal_not_cold_ready(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); write=owner.file.write; delayed=[]
            def delayed_save(value,previous):
                write(value,previous)
                if value['phase']=='ready' and value['records'] and not delayed: delayed.append(True); m.clock+=2
            owner.file.write=delayed_save
            with self.assertRaises(NativeUIError): owner.read()
            self.assertEqual([True],delayed); self.assertEqual('failed',owner.store.read()['phase'])
            before=list(m.commands); cold=m.owner()
            with self.assertRaises(NativeUIError): cold.read()
            self.assertEqual(before,m.commands); self.assertEqual(1,len(cold.packets))

    def test_delay_inside_original_final_guard_keeps_completed_raw_failed_not_cold_success(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); original=owner.original_guard; delayed=[]
            def guard():
                valid=original(); root=owner.store.read()
                if root is not None and root['phase']=='ready' and root['records'] and not delayed:
                    delayed.append(True); m.clock+=2
                return valid
            owner.original_guard=guard
            with self.assertRaises(NativeUIError): owner.read()
            self.assertEqual([True],delayed); self.assertEqual('failed',owner.store.read()['phase'])
            before=list(m.commands); cold=m.owner()
            with self.assertRaises(NativeUIError): cold.read()
            self.assertEqual(before,m.commands); self.assertEqual(1,len(cold.packets))

    def test_original_120_second_budget_never_renews_on_cold_reconstruction(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); owner.read(); m.clock+=120.001
            raw=owner.store.path.read_bytes()
            with self.assertRaises(NativeUIError): owner.read()
            with self.assertRaises(NativeUIError): m.owner()
            self.assertEqual(1,len(m.commands)); self.assertEqual(raw,owner.store.path.read_bytes())

    def test_cold_original_host_clock_cannot_reverse_below_committed_record(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); m.clock=1.; owner.read(); original=owner.store.path.read_bytes()
            m.clock=.5
            with self.assertRaises(NativeUIError): m.owner()
            self.assertEqual(1,len(m.commands)); self.assertEqual(original,owner.store.path.read_bytes())

    def test_actual_other_host_can_restore_history_but_not_adopt_live_original_source(self):
        m=self.model
        with m.lock.held():
            owner=m.owner(); owner.read(); raw=owner.store.path.read_bytes()
            scope=dict(primary=owner.primary,packets=owner.packets)
        program=r'''
import json,sys
from pathlib import Path
from self_tests.test_pico_avatar_remote import RemoteBoundary
from adapters.pico4.avatar_remote import NativePicoRemoteAvatar
from adapters.normal_ui import NativeUIError
m=RemoteBoundary();m.root=Path(sys.argv[1]);scope=json.loads(sys.argv[2])
historical=NativePicoRemoteAvatar(m.send,m.original,lambda:m.epoch,lambda:True,31,retain=lambda *_args:None)
historical.restore(scope['packets'])
try:
 with m.lock.held():
  try:m.owner(scope['primary'])
  except NativeUIError:print(json.dumps(dict(refused=True,queries=len(m.commands),historical=historical.last==scope['packets'][-1])))
  else:raise AssertionError('New actual host adopted current producer ownership')
finally:m.close()
'''
        result=subprocess.run([sys.executable,'-c',program,str(m.root),json.dumps(scope)],capture_output=True,text=True,timeout=10,
            env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1])))
        report=m.root/'owned-test-child-result.json'
        report.write_text(json.dumps(dict(exitCode=result.returncode,stdout=result.stdout,stderr=result.stderr))); report.chmod(0o600)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(dict(refused=True,queries=0,historical=True),json.loads(result.stdout))
        with m.lock.held(): owner.guard(); self.assertEqual(raw,owner.store.path.read_bytes())

    def test_boolean_or_reordered_raw_reference_cannot_alias_original_chunk_indexes(self):
        m=self.model
        # The real remote producer no longer fabricates a large local-Rig
        # history. Preserve meaningful ordering coverage with actual multiple
        # fragments of the same valid JSON DTO, including original whitespace.
        m.original=lambda:json.dumps(m.sample,indent=8)
        with m.lock.held():
            owner=m.owner(); owner.read(); reference=owner.state['records'][0]['raw']
            self.assertGreaterEqual(len(reference['parts']),2)
            for edit in (lambda r:r.update(parts=[True]),lambda r:r.update(bytes=True),lambda r:r.update(parts=list(reversed(r['parts'])))):
                changed=deepcopy(reference); edit(changed)
                with self.assertRaises(NativeUIError): owner.raw(changed)

    def test_original_remote_rig_geometry_and_each_executed_eye_join_existing_png_capture(self):
        m=self.model; m.epoch=21000; m.gpu=ModelBoundary(epoch=21000)
        m.rig=RigPackets().native(20998,active=False,restore_epoch=20800)['animation']
        primary=m.primary(); m.sequence+=1
        before=m.packet(dict(commandId='1'*32),epoch=20999); m.sequence+=1
        after=m.packet(dict(commandId='2'*32),epoch=21000)
        draws=m.gpu.reader().read(m.gpu.capture)
        row=remote.remote_draws(primary,before,after,m.gpu.capture,draws,31,21000)
        self.assertEqual(['left','right'],[camera['eye'] for camera in row['cameraUses']])
        self.assertNotIn('localRenderingEnabled',before['source']['subject']); self.assertNotIn('visible',row)

    def test_unknown_remote_geometry_and_missing_eye_cannot_borrow_local_avatar_trace(self):
        m=self.model; m.epoch=21000; m.gpu=ModelBoundary(epoch=21000)
        m.rig=RigPackets().native(20998,active=False,restore_epoch=20800)['animation']
        primary=m.primary(); m.sequence+=1
        before=m.packet(dict(commandId='1'*32),epoch=20999); m.sequence+=1
        after=m.packet(dict(commandId='2'*32),epoch=21000)
        draws=m.gpu.reader().read(m.gpu.capture)
        wrong=deepcopy(after); wrong['source']['subject']['geometry']['instance']='2'*32
        with self.assertRaises(NativeUIError): remote.remote_draws(primary,before,wrong,m.gpu.capture,draws,31,21000)
        missing=deepcopy(draws); missing['source']['modelTrace']['models'][0]['cameraUses'].pop()
        with self.assertRaises(NativeUIError): remote.remote_draws(primary,before,after,m.gpu.capture,missing,31,21000)
        foreign_before,foreign_after=deepcopy(before),deepcopy(after)
        for packet in (foreign_before,foreign_after): packet['source']['worldRenderInstance']='3'*32
        with self.assertRaises(NativeUIError): remote.remote_draws(primary,foreign_before,foreign_after,m.gpu.capture,draws,31,21000)

    def test_missing_root_with_actual_prepared_or_original_chunk_is_not_adopted(self):
        m=self.model; path=source_store(m.adapter,'explicit-model',RUN).path
        for suffix in ('.pending-owned','.frame-000.json'):
            with self.subTest(suffix=suffix),m.lock.held():
                orphan=path.with_name(path.name+suffix); orphan.write_bytes(b'original owner\n'); orphan.chmod(0o600)
                with self.assertRaises(NativeUIError): m.owner()
                self.assertEqual([],m.commands); self.assertFalse(path.exists()); self.assertEqual(b'original owner\n',orphan.read_bytes())
                orphan.unlink()  # Only the test-created artifact.

    def test_probe_preserves_original_raw_once_and_unavailable_without_local_fallback(self):
        program=r'''
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
let files=[],calls=[];const original={schemaVersion:1,requestId:"a".repeat(32),source:{subject:null,original:true}};
const Test={featurePicoRemoteAvatarObservation:c=>{calls.push(c);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-pico-remote-avatar-observe",runId:"d".repeat(32),subjectSessionId:"11111111-1111-4111-8111-111111111111"};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||files[0].name!=="feature-pico-remote-avatar.json")throw Error("changed or replayed original");
delete Test.featurePicoRemoteAvatarObservation;request.commandId="b".repeat(32);applyAndroidControlCommand(request);
if(files.length!==2||files[1].v.available!==false)throw Error("invented local fallback");
request.commandId="c".repeat(32);request.expectedModel="injected";applyAndroidControlCommand(request);
if(files.length!==2)throw Error("unknown field admitted");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__': unittest.main()
