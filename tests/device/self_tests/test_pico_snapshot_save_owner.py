"""Closed Save admission and current original provider protocol counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_save_owner import PicoSnapshotSaveOwner
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
from adapters.pico4.snapshot_exports import PicoSnapshotExports,components
from adapters.pico4.snapshot_export_readbacks import os_destinations
from adapters.pico4.snapshot_saved_files import original_stat
from adapters.pico4.snapshot_save_originals import SnapshotSaveOriginals
from adapters.pico4.navigation import PicoNavigation
from adapters.script_journey.history import pack
import self_tests.test_pico_snapshot_exports as source_tests
packet,RUN=source_tests.packet,source_tests.RUN

PATH='/data/user/0/org.overte.pico/files/Snapshots/parity-aaaaaaaaaaaaaaaa-still-png-snap_1.png'


class SnapshotSaveAdmissionTests(unittest.TestCase):
    def fixture(self):
        owner=object.__new__(PicoSnapshotSaveOwner);owner.binding=dict(sessionId='own-bridge')
        owner.parent=SimpleNamespace(state=dict(capture=dict(file=dict(path=PATH))),snapshot=SimpleNamespace(ui=PicoNavigation))
        control='snapshot.save.'+hashlib.sha256(PATH.encode()).hexdigest();generation='11111111-1111-4111-8111-111111111111';token='22222222-2222-4222-8222-222222222222'
        row=dict(base=dict(ui=dict(bridgeId='own-bridge',generation=generation,lastCommandSequence=2,elapsedMs=30,snapshotExportControlsVersion=1,
            controls=[dict(id=control,path=PATH,token=token,enabled=True,focused=False,inputReady=True,profile='native-pico-snapshot-export-v1',
            componentUrl='file:///packaged/scripts/system/snapshot/NativeSnapshotReview.qml')])) )
        command=dict(schemaVersion=1,commandId='33333333-3333-4333-8333-333333333333',bridgeId='own-bridge',generation=generation,
            sequence=3,observedElapsedMs=30,controlId=control,controlToken=token,action='activate')
        return owner,row,command
    def test_only_original_path_token_generation_and_next_qml_sequence_can_admit_save(self):
        owner,row,command=self.fixture();owner.qml(command,row)
        for field,value in (('schemaVersion',True),('generation','foreign'),('sequence',4),('observedElapsedMs',31),('controlToken','foreign'),
                ('controlId','snapshot.share.'+'f'*64),('action','replace'),('expectedSaved',True)):
            changed=deepcopy(command);changed[field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):owner.qml(changed,row)
    def test_current_native_handle_or_already_changed_export_history_blocks_another_save(self):
        owner=object.__new__(PicoSnapshotSaveOwner);value=packet(PicoSnapshotExports.envelope(RUN));value['lease']=dict(present=True,
            componentUrl='file:///packaged/scripts/system/snapshot/NativeSnapshotReview.qml',native=dict(snapshotExportLeaseVersion=1,handle='42',ticket='',busy=False))
        baseline=dict(exports=dict(raw=json.dumps(value)));state=dict(frames=[baseline]);owner.before_export(baseline,state)
        for handle,busy,ticket in (('43',False,''),('42',True,'1')):
            changed=deepcopy(value);changed['lease']['native'].update(handle=handle,busy=busy,ticket=ticket)
            with self.subTest(handle=handle,busy=busy),self.assertRaises(NativeUIError):owner.before_export(dict(exports=dict(raw=json.dumps(changed))),state)
    def test_full_original_stat_signature_cannot_be_reduced_to_same_bytes_or_another_inode(self):
        signature='1 2 8180 1000 1000 1 3 2026-10-23 01:02:03.000000001 +0000 2026-10-23 01:02:03.000000002 +0000'
        self.assertTrue(original_stat(signature,3,1,2))
        for args in ((signature,3,1,9),(signature.replace('8180','81a4'),3,1,2),(signature,True,1,2),('1:2:3',3,1,2)):
            with self.subTest(args=args):self.assertFalse(original_stat(*args))
    def test_new_provider_verified_epoch_is_explicit_and_old_absence_only_protocol_is_not_current_quiet(self):
        request='d'*32;uri='content://media/external/images/media/1';destinations={request:dict(request=request,uri=uri,inserted=True,published=True)}
        row=dict(request=request,inserted=True,phase='qualified',identity=dict(uri=uri,providerUid=99,ownerPackage='org.overte.pico',
            displayName='original.png',device=1,inode=2),original=dict(bytes=3,sha256='e'*64),acquiredEpochMs=100,deleteId='',deleteIssued=False,
            deleteCount=-1,checkedEpochMs=200,absent=False,verifiedEpochMs=200)
        source=dict(snapshotOsDestinationsVersion=3,complete=True,pending=0,checkId='f'*32,checkedEpochMs=200,rows=[row])
        os_destinations(source,destinations,200)
        for version,verified in ((2,200),(3,99),(3,None)):
            changed=deepcopy(source);changed['snapshotOsDestinationsVersion']=version
            if verified is None:changed['rows'][0].pop('verifiedEpochMs')
            else:changed['rows'][0]['verifiedEpochMs']=verified
            with self.subTest(version=version,verified=verified),self.assertRaises(NativeUIError):os_destinations(changed,destinations,200)


class SnapshotSaveOriginalsTests(unittest.TestCase):
    def fixture(self):
        temporary=tempfile.TemporaryDirectory(prefix='pico-save-originals-');self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700)
        binding=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='123:original',sessionId='own-bridge',generation=0,targetFingerprint='3'*64)
        return root,binding,SnapshotSaveOriginals(root/'snapshot-save-originals.json',RUN,binding)
    def test_complete_original_frame_is_immutable_scoped_and_cold_readable(self):
        root,binding,owner=self.fixture();value=dict(raw='actual original bytes',native=dict(original='birth'))
        reference=owner.put('frame',value);cold=SnapshotSaveOriginals(owner.root.path,RUN,binding)
        self.assertEqual(value,cold.get('frame',reference));value['native']['original']='caller mutation'
        self.assertEqual('birth',cold.get('frame',reference)['native']['original'])
        with self.assertRaises(NativeUIError):SnapshotSaveOriginals(owner.root.path,'b'*32,binding)
        with self.assertRaises(NativeUIError):owner.put('reply',dict(ack=True))
    def cold_ledger(self,*,copy_id='d'*32,capture_present=True):
        # Only the already-owned Parent native/UI/phase effect proofs are seams.
        # Exercise the actual persisted Save envelope/chunks, cold load and full
        # Save state grammar. No cache, native query or input method is supplied.
        from adapters.normal_feature_state import PrivateFeatureState
        import adapters.pico4.snapshot_save_owner as module
        root,binding,originals=self.fixture();owner=object.__new__(PicoSnapshotSaveOwner)
        capture='a'*32;other='b'*32;ids=[other]+([capture] if capture_present else [])
        files=dict(source=dict(rows=[dict(id=id) for id in ids]))
        value=packet(PicoSnapshotExports.envelope(RUN));value['lease']=dict(present=True,native=dict(handle='42'))
        frame=dict(exports=dict(raw=json.dumps(value)),hostMonotonic=1.)
        owner.parent=SimpleNamespace(files=SimpleNamespace(state=None),state=dict(frames=[dict(original='parent')],capture=dict(file=dict(fileId=capture))),
            frame=lambda row:({}, {}, deepcopy(files)))
        owner.run=RUN;owner.binding=binding;owner.parent_digest='c'*64
        owner.source=SimpleNamespace(fixture_url='https://original.invalid/fixture')
        owner.lock=SimpleNamespace(assert_held=lambda:None);owner.pin=lambda:None
        owner.phase=lambda value:value;owner.artifact_root=lambda:dict(device=1,inode=2)
        owner.frame=lambda row:({}, {}, deepcopy(files),deepcopy(value));owner.stable_capture=lambda row:None
        owner.qml=lambda command,row:None;owner.before_export=lambda row,state:None;owner.export_proof=lambda state:None
        owner.exports=SimpleNamespace(last=value);owner.store=PrivateFeatureState(root/'snapshot-save-owner.json')
        owner.originals=originals;owner.disk=owner.state=None
        artifact=dict(name='snapshot-owned-'+RUN+'-'+copy_id+'.bin',bytes=3,sha256='e'*64,phase='planned',file=None,removeIntent=False)
        read=dict(schemaVersion=1,commandId='1'*32,action='feature-pico-snapshot-exports',runId=RUN,operation='read',exportRequest='2'*32,resourceId='3'*32)
        state=dict(stage='read-issued',source=dict(original='save-phase'),parentSha256=owner.parent_digest,frames=[frame],
            deliveries=[dict(kind='qml',command=dict(commandId='f'*32),frame=0)],requests=[read],export=dict(identity=dict(request='2'*32)),
            readId='3'*32,saved=None,artifacts={copy_id:artifact},artifactRoot=dict(device=1,inode=2),scope=RUN,quiet=[],inspection='',completedInspections={})
        disk=dict(snapshotSaveOwnerVersion=1,runId=RUN,binding=binding,fixtureUrl=owner.source.fixture_url,payload=pack([originals.encode(state)]))
        owner.store.write(disk,None)
        owner.originals=SnapshotSaveOriginals(originals.root.path,RUN,binding)
        return owner,module
    def reopen_ledger(self,owner,module):
        # Unrelated continuity is independently covered by original-source tests;
        # this counterexample isolates the exact cold ownership/collision boundary.
        from unittest.mock import patch
        with patch.object(module.native_source,'accept',side_effect=lambda before,after:after), \
                patch.object(module,'script_accept',side_effect=lambda before,after:after), \
                patch.object(module,'file_continuity',return_value=None):
            owner.load()
    def test_persisted_cold_save_reopens_without_a_warm_file_cache_or_new_source_input(self):
        owner,module=self.cold_ledger();self.reopen_ledger(owner,module)
        self.assertIsNone(owner.parent.files.state);self.assertEqual('read-issued',owner.state['stage'])
        self.assertEqual({'d'*32},set(owner.state['artifacts']));self.assertEqual(1,len(owner.state['frames']))
    def test_cold_saved_copy_cannot_collide_with_any_original_native_file_or_lose_original_capture(self):
        for id,present in (('a'*32,True),('b'*32,True),('d'*32,False)):
            owner,module=self.cold_ledger(copy_id=id,capture_present=present);before=owner.store.path.read_bytes()
            with self.subTest(id=id,present=present),self.assertRaises(NativeUIError):self.reopen_ledger(owner,module)
            self.assertEqual(before,owner.store.path.read_bytes());self.assertIsNone(owner.state)
            self.assertIsNone(owner.parent.files.state)

    def test_orphan_child_or_changed_original_cannot_be_adopted(self):
        root,binding,owner=self.fixture();reference=owner.put('frame',dict(original='immutable'))
        child=owner.history.store(0).path;before=child.read_bytes();child.write_bytes(before+b' ')
        with self.assertRaises(NativeUIError):owner.verify()
        # The interrupted root is retained; no new owner truncates the child.
        self.assertTrue(owner.root.path.exists());self.assertTrue(child.exists())
        owner.root.path.unlink()
        with self.assertRaises(NativeUIError):SnapshotSaveOriginals(owner.root.path,RUN,binding)
        self.assertTrue(child.exists())


class SnapshotSaveFenceTests(unittest.TestCase):
    def fixture(self):
        owner=object.__new__(PicoSnapshotSaveOwner);clock=[20000,1.];calls=[]
        phase=dict(active=True,instance='a'*32,createdEpochMs=10000,activations=[dict(original='save')],capturedEpochMs=20000)
        current=deepcopy(phase);owner.state=dict(source=phase);owner.anchor=(1.,20000,20000)
        owner.pin=lambda:calls.append('pin');owner.parent=SimpleNamespace(now=lambda:clock[1])
        def guard():calls.append('guard')
        owner.native=SimpleNamespace(clock_ms=lambda:clock[0],guard=guard)
        def status(_before):calls.append('phase');return deepcopy(current)
        owner.source=SimpleNamespace(epoch_ms=lambda:clock[0],status=status)
        return owner,clock,calls,current
    def test_last_original_native_guard_phase_change_is_seen_before_writer_admission(self):
        owner,clock,calls,current=self.fixture();guard=owner.native.guard
        def change():guard();current['activations'].append(dict(original='different phase'))
        owner.native.guard=change
        with self.assertRaises(NativeUIError):owner.fence()
        self.assertEqual(['pin','guard','phase'],calls)
    def test_final_host_or_native_age_cannot_be_refreshed_by_a_frozen_other_clock(self):
        for native,host in ((2000,0),(0,2)):
            owner,clock,calls,current=self.fixture();guard=owner.native.guard
            def slow():guard();clock[0]+=native;clock[1]+=host;current['capturedEpochMs']=clock[0]
            owner.native.guard=slow
            with self.subTest(native=native,host=host),self.assertRaises(NativeUIError):owner.fence()
            self.assertEqual(['pin','guard','phase'],calls)


class SnapshotSaveEnvelopeTests(unittest.TestCase):
    # Only the additional original-envelope case is exported by the Pico
    # selector; parent source cases remain owned by their original group.
    def test_exact_persisted_nonce_is_published_once_and_a_lost_return_never_reallocates_it(self):
        fixture=source_tests.PicoSnapshotExportsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        request=PicoSnapshotExports.envelope(RUN);fixture.owner.request_original(request)
        self.assertEqual(request,fixture.io.sent[-1])
        with self.assertRaises(NativeUIError):fixture.owner.request_original(request)
        self.assertEqual(1,len(fixture.io.sent))


class SnapshotSavePreparationRecoveryTests(unittest.TestCase):
    def fixture(self):
        owner=object.__new__(PicoSnapshotSaveOwner);calls=[]
        value=packet(PicoSnapshotExports.envelope(RUN));value['lease']=dict(present=True,
            componentUrl='file:///packaged/scripts/system/snapshot/NativeSnapshotReview.qml',native=dict(snapshotExportLeaseVersion=1,handle='42',ticket='',busy=False))
        baseline=dict(base={},exports=dict(raw=json.dumps(value)));owner.state=dict(stage='prepare-issued',frames=[baseline],saved=None)
        owner.lock=SimpleNamespace(held=nullcontext);owner.load=lambda:calls.append('load')
        owner.parent=SimpleNamespace(state={},still_idle=lambda *_:calls.append('still-idle'))
        owner.fence=lambda:calls.append('final-fence')
        def append():
            calls.append('read-only-frame');row=deepcopy(baseline);row['exports']['raw']=json.dumps(value);owner.state['frames'].append(row);return row
        def save(state):calls.append('prepared-cas');owner.state=state
        owner.append=append;owner.save=save
        return owner,value,calls
    def test_original_prepare_intent_can_finish_read_only_without_another_input_or_phase_intent(self):
        owner,value,calls=self.fixture();result=owner.prepare()
        self.assertEqual('prepared',result['stage']);self.assertFalse(result['ordinarySaveResendAllowed'])
        self.assertEqual(['load','read-only-frame','still-idle','prepared-cas','final-fence'],calls)
        with self.assertRaises(NativeUIError):owner.prepare()
    def test_intervening_native_handle_is_not_adopted_as_a_new_recovery_baseline(self):
        owner,value,calls=self.fixture();value['lease']['native']['handle']='43'
        with self.assertRaises(NativeUIError):owner.prepare()
        self.assertEqual('prepare-issued',owner.state['stage']);self.assertEqual(2,len(owner.state['frames']))
        self.assertNotIn('prepared-cas',calls);self.assertNotIn('final-fence',calls)


class SnapshotSaveAcquisitionTests(unittest.TestCase):
    def test_private_copy_check_archives_its_actual_query_without_a_discarded_duplicate(self):
        for saved in (False,True):
            owner=object.__new__(PicoSnapshotSaveOwner);calls=[];owner.run=RUN
            owner.parent=SimpleNamespace(now=lambda:1.,read_frame=lambda:{'actual':'base'})
            owner.native=SimpleNamespace(clock_ms=lambda:20000)
            owner.state=dict(saved=dict(file=dict(copy='a'*32))) if saved else None
            def request(run):self.assertEqual(RUN,run);calls.append('query')
            owner.exports=SimpleNamespace(request=request,original=lambda:{'actual':'export'})
            def current(id,*,historical):
                self.assertEqual('a'*32,id);self.assertTrue(historical);request(RUN);calls.append('current');return None,None,None,['owned','copy']
            owner.transport=SimpleNamespace(current=current,metadata=lambda parts:{'actual':'stat'})
            owner.parent.platform=SimpleNamespace(read=lambda:{'actual':'sdk'})
            owner.frame=lambda row:calls.append('validate-full-frame');owner.clocks=lambda row:(1000,20000)
            row=owner.read_frame()
            self.assertEqual(1,calls.count('query'));self.assertEqual(saved,'current' in calls)
            self.assertEqual({'actual':'export'},row['exports']);self.assertEqual(saved,row['copy'] is not None)
            self.assertEqual('validate-full-frame',calls[-1]);self.assertEqual((1.,20000,20000),owner.anchor)


class SnapshotOriginalFrameMemoTests(unittest.TestCase):
    def fixture(self):
        owner=object.__new__(PicoSnapshotCancelOwner);owner.run=RUN;owner.native=SimpleNamespace(pid=123);owner.binding=dict(sessionId='own-bridge');calls=[]
        def validate(row):
            calls.append(deepcopy(row))
            if row.get('invalid'):raise NativeUIError('Changed original')
            return (deepcopy(row),)
        owner.original_frame=validate;return owner,calls
    def test_exact_pure_original_is_reused_but_changed_content_and_owner_are_revalidated(self):
        owner,calls=self.fixture();row=dict(original=dict(value=1));first=owner.frame(row);first[0]['original']['value']=99
        result=owner.frame(row);self.assertEqual(1,result[0]['original']['value']);self.assertEqual(1,len(calls))
        result[0]['original']['value']=98;self.assertEqual(1,owner.frame(row)[0]['original']['value'])
        for key,value in (('run','b'*32),('pid',124),('bridge','another-bridge'),('row',dict(original=dict(value=True)))):
            if key=='run':owner.run=value
            elif key=='pid':owner.native.pid=value
            elif key=='bridge':owner.binding['sessionId']=value
            else:row=value
            owner.frame(row)
        self.assertEqual(5,len(calls))
        row['invalid']=True
        with self.assertRaises(NativeUIError):owner.frame(row)
        with self.assertRaises(NativeUIError):owner.frame(row)
        self.assertEqual(7,len(calls))
    def test_cold_owner_validates_again_and_warm_cache_remains_bounded(self):
        owner,calls=self.fixture()
        for index in range(129):owner.frame(dict(index=index))
        self.assertEqual(128,len(owner._original_frame_cache));self.assertEqual(129,len(calls))
        owner.frame(dict(index=0));self.assertEqual(130,len(calls))
        cold,cold_calls=self.fixture();cold.frame(dict(index=0));self.assertEqual(1,len(cold_calls))
    def test_save_platform_branch_is_part_of_the_exact_validation_context(self):
        owner=object.__new__(PicoSnapshotSaveOwner);owner.run=RUN;owner.native=SimpleNamespace(pid=123);owner.binding=dict(sessionId='own-bridge')
        source=dict(sdk=34,saveBackend='media-store');parent_context=dict(pid=123,bridge='own-bridge')
        owner.parent=SimpleNamespace(state=dict(platform=dict(original=dict(source=source))),frame_context=lambda:deepcopy(parent_context))
        calls=[]
        def validate(row):
            calls.append(deepcopy(source))
            if source['saveBackend']!='media-store':raise NativeUIError('Changed SDK backend')
            return (deepcopy(row),)
        owner.original_frame=validate;owner.frame(dict(original='unchanged'));owner.frame(dict(original='unchanged'))
        self.assertEqual(1,len(calls));source['saveBackend']='documents'
        with self.assertRaises(NativeUIError):owner.frame(dict(original='unchanged'))
        self.assertEqual(2,len(calls));source['saveBackend']='media-store';parent_context['pid']=124
        owner.frame(dict(original='unchanged'));self.assertEqual(3,len(calls))
    def test_equal_json_bytes_do_not_allow_a_tuple_subclass_or_coerced_dictionary_key_to_replace_original_types(self):
        class DictSubclass(dict):pass
        class ListSubclass(list):pass
        owner,calls=self.fixture();owner.frame(dict(rows=[{'1':'source'}]))
        changes=(dict(rows=({'1':'source'},)),dict(rows=ListSubclass([{'1':'source'}])),
            DictSubclass(rows=[{'1':'source'}]),dict(rows=[{1:'source'}]))
        for changed in changes:
            with self.subTest(type=type(changed)),self.assertRaises(NativeUIError):owner.frame(changed)
        self.assertEqual(1,len(calls));self.assertEqual((dict(rows=[{'1':'source'}]),),owner.frame(dict(rows=[{'1':'source'}])))


class SnapshotSavePublicationTests(unittest.TestCase):
    fixture=SnapshotSaveFenceTests.fixture
    def publication(self):
        owner,clock,calls,current=self.fixture();request=PicoSnapshotExports.envelope(RUN,'inspect-destinations',resource_id='a'*32)
        owner.lock=SimpleNamespace(assert_held=lambda:None);owner.current=True
        owner.state.update(stage='quiet-issued',requests=[request],deliveries=[],frames=[dict(original='already durable')])
        def save(state):owner.state=state;calls.append('durable-cas')
        owner.save=save
        return owner,clock,calls,current,request
    def test_slow_last_delivery_cas_is_covered_by_native_and_independent_host_age(self):
        for native,host in ((2000,0),(0,2)):
            owner,clock,calls,current,request=self.publication();save=owner.save
            def slow(state):save(state);clock[0]+=native;clock[1]+=host
            owner.save=slow
            with self.subTest(native=native,host=host),self.assertRaises(NativeUIError):owner.before_source_send(request)
            self.assertEqual([request],[row['command'] for row in owner.state['deliveries']]);self.assertEqual('quiet-issued',owner.state['stage'])
    def test_phase_progress_during_last_delivery_cas_blocks_source_publication_and_keeps_intent(self):
        owner,clock,calls,current,request=self.publication();save=owner.save
        def advance(state):save(state);current['activations'].append(dict(original='next phase'))
        owner.save=advance
        with self.assertRaises(NativeUIError):owner.before_source_send(request)
        self.assertEqual([request],[row['command'] for row in owner.state['deliveries']]);self.assertEqual(['durable-cas','pin','guard','phase'],calls)


if __name__=='__main__':unittest.main()
