"""Host-only original archive/clock joins; all Qt/Rig execution is synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.native_clock_join import digest
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_script_observation import NativeScriptObservation
from adapters.native_script_roots import NativeScriptRoots
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.emote_controls import IOSEmoteIO,project
from ios.self_tests.test_ios_emote_controls import NativeBoundary
from self_tests.test_emote_rig_measurements import RigPackets

RUN='c'*32
BINDING=dict(sourceRevision='d'*40,artifactSha256='e'*64,processIdentity='31',sessionId='sdk-session',generation=0,targetFingerprint='f'*64)


def phase(sequence,epoch):
    return dict(fixturePhaseVersion=1,instance='3'*32,sequence=sequence,requestId=str(sequence)*32,
        runId=RUN,area='emotes',capturedEpochMs=epoch,active=True,createdEpochMs=89000,retiredEpochMs=None,
        activations=[dict(sequence=1,ticket='4'*32,activatedEpochMs=89900,stimulus=dict(verb='baseline',inputs={}))])


def frame():
    model=RigPackets();before=model.native(18800,baseline=True)
    current=model.native(20000,active=True);group=model.group(current)
    after=model.native(20000,active=True)
    widget=NativeBoundary();widget.page=True;widget.active='Waving';widgets=widget.capture()
    # No name/pose is inferred from this UI; bind its actual source URL digest.
    import hashlib
    original=model.roots.root+'/system/+android_phoneInterface/PhoneEmote.qml'
    [row for row in widgets['controls'] if row['id']=='emote.page'][0]['componentSourceSha256']=hashlib.sha256(original.encode()).hexdigest()
    originals=dict(group,widgets=widgets)
    join=dict(clockJoinVersion=1,hostBeforeEpochMs=90000.,hostAfterEpochMs=91200.,hostBeforeMonotonic=1.,hostAfterMonotonic=2.2,
        nativeBefore=before,nativeAfter=after,originalsSha256=digest(originals),sourceTimes=[dict(source=name,field=field,epochMs=p[field])
            for name,p in originals.items() for field in ('capturedEpochMs','sampleEpochMs') if field in p])
    return dict(group=group,widgets=widgets,ui=project(widgets),clockJoin=join,phaseBefore=phase(1,90000),phaseAfter=phase(2,91200))


class IOSEmoteSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.store=PrivateFeatureState(self.root/'ios-emote-primary-sources.json')
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def owner(self):return IOSEmoteSources(self.store,self.root,BINDING,RUN,'primary',self.lock,lambda:True,None,historical=True)
    def test_iOS_host_epoch_can_differ_from_native_epoch_without_retiming(self):
        owner=self.owner();value=frame();self.assertTrue(owner.validate_frame(value))
        self.assertEqual(20000,value['group']['native']['capturedEpochMs'])
        self.assertEqual(90000,value['clockJoin']['hostBeforeEpochMs'])
    def test_v2_world_original_binds_actual_primary_domain_without_retiming(self):
        from ios.self_tests.test_ios_emote_world import packet
        value=frame();value['world']=packet();value['clockJoin']['originalsSha256']=digest(dict(value['group'],widgets=value['widgets'],world=value['world']))
        self.assertTrue(self.owner().validate_frame(value))
        for field,bad in (('processId',99),('runId','0'*32)):
            corrupt=deepcopy(value);corrupt['world'][field]=bad
            corrupt['clockJoin']['originalsSha256']=digest(dict(corrupt['group'],widgets=corrupt['widgets'],world=corrupt['world']))
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.owner().validate_frame(corrupt)
    def test_v1_owner_and_originals_remain_historically_readable(self):
        first=self.archive();legacy=first.envelope(first.state,version=1)
        self.store.write(legacy,first.previous);rebuilt=self.owner()
        self.assertEqual(first.frames,rebuilt.frames);self.assertNotIn('world',rebuilt.frames[0])
    def test_changed_native_original_or_host_clock_join_is_rejected(self):
        for mutate in (lambda v:v['group']['native'].update(capturedEpochMs=20001),
                       lambda v:v['clockJoin'].update(hostAfterEpochMs=95000),
                       lambda v:v['widgets'].update(processId=99)):
            value=frame();mutate(value)
            with self.assertRaises(NativeUIError):self.owner().validate_frame(value)
    def test_real_qml_component_url_must_match_original_submitted_engine_assignment(self):
        value=frame();row=[r for r in value['widgets']['controls'] if r['id']=='emote.page'][0]
        row['componentSourceSha256']='0'*64;value['ui']=project(value['widgets'])
        value['clockJoin']['originalsSha256']=digest(dict(value['group'],widgets=value['widgets']))
        with self.assertRaises(NativeUIError):self.owner().validate_frame(value)
    def test_phase_can_change_but_cannot_be_published_as_stable_current_effect(self):
        value=frame();value['phaseAfter']['activations'].append(dict(sequence=2,ticket='5'*32,activatedEpochMs=91100,stimulus=dict(verb='open',inputs={})))
        self.assertFalse(self.owner().validate_frame(value))
    def archive(self):
        owner=self.owner();owner.historical=False
        owner.state.update(phase='reading',pending=dict(original=None,manifest=None,partial={}))
        owner.save();value=frame();item=owner.originals.write(1,value);manifests=owner.originals.append([],item)
        owner.frames.append(value);owner.state.update(phase='ready',revision=1,manifests=manifests,pending=None);owner.save()
        return owner
    def test_private_immutable_archive_reconstructs_exact_originals(self):
        first=self.archive();second=self.owner()
        self.assertEqual(first.frames,second.frames)
        with self.assertRaises(NativeUIError):second.read()
    def test_archive_body_tampering_fails_reconstruction(self):
        self.archive();path=next(self.root.glob('emote-frame-*.json'));path.write_bytes(b'{}')
        with self.assertRaises(NativeUIError):self.owner()
    def test_failed_partial_acquisition_remains_owned_and_is_never_resent(self):
        calls=[];phase_reader=object.__new__(PhaseFixtureReader);phase_reader.area='emotes';phase_reader.run=RUN
        def missing(_):calls.append('read');raise NativeUIError('Synthetic lost fixture return')
        phase_reader.read=missing
        roots=NativeScriptRoots(lambda _:None,lambda:'',lambda:20000,lambda:True,31,ios=True)
        scripts=NativeScriptObservation(lambda _:None,lambda:'',lambda:20000,lambda:True,31,ios=True)
        native=NativeFeatureObservation(lambda _:None,lambda:'',lambda:20000,lambda:True,31,ios=True,native_clock_bound=True)
        readers=dict(roots=roots,scripts=scripts,native=native,ui=IOSEmoteIO(NativeBoundary()))
        owner=IOSEmoteSources(self.store,self.root,BINDING,RUN,'primary',self.lock,lambda:True,phase_reader,readers=readers)
        with self.assertRaises(NativeUIError):owner.read()
        repeated=IOSEmoteSources(self.store,self.root,BINDING,RUN,'primary',self.lock,lambda:True,phase_reader,readers=readers)
        with self.assertRaises(NativeUIError):repeated.read()
        self.assertEqual(['read'],calls);self.assertEqual('reading',repeated.state['phase'])

if __name__=='__main__':unittest.main()
