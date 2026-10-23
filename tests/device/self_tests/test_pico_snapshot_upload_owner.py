"""Normal Upload admission, durable recovery and unchanged original scope.

Pure owner boundaries below are explicit seams; the separate TLS/native suites
own real wire bytes and actual Qt bodies. No whole or device result is inferred.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.snapshot_upload_owner import PicoSnapshotUploadOwner,provider_phase,quiet_indices,mutation_scope
from adapters.pico4.snapshot_upload_originals import SnapshotUploadOriginals
from adapters.pico4.snapshot_save_owner import PicoSnapshotSaveOwner
from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
from self_tests import test_pico_snapshot_save_owner as saved_tests
from self_tests.test_pico_snapshot_context import source as context_source
PATH,RUN=saved_tests.PATH,saved_tests.RUN
from feature_journeys.witness import Journal


class SnapshotUploadAdmissionTests(unittest.TestCase):
    def fixture(self):
        saved,row,command=saved_tests.SnapshotSaveAdmissionTests().fixture();owner=object.__new__(PicoSnapshotUploadOwner)
        owner.binding=saved.binding;owner.base=saved.parent
        selected=row['base']['ui']['controls'][0];selected['id']=selected['id'].replace('snapshot.save.','snapshot.upload.')
        command['controlId']=selected['id'];return owner,row,command
    def test_exact_original_upload_path_control_token_generation_and_next_sequence(self):
        owner,row,command=self.fixture();owner.qml(command,row)
        for field,value in (('schemaVersion',True),('generation','foreign'),('sequence',4),('observedElapsedMs',31),('controlToken','foreign'),
                ('controlId','snapshot.share.'+'f'*64),('action','replace'),('expectedUploaded',True)):
            changed=deepcopy(command);changed[field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):owner.qml(changed,row)
    def test_original_phase_transcript_is_closed_but_never_a_share_effect(self):
        journal=Journal();run=journal.register('snapshots');counter=1
        def activate(verb,inputs=None):
            nonlocal counter
            journal.activate(run,f'{counter:032x}',verb,inputs or {});counter+=1
            return journal.phase(run,f'{100+counter:032x}')
        activate('baseline');activate('open');activate('capture-cancel',dict(mode='animated',format='png'))
        activate('capture',dict(mode='still',format='png'));saved=activate('save')
        owner=object.__new__(PicoSnapshotUploadOwner);owner.run=run;owner.parent=SimpleNamespace(state=dict(source=saved));owner.parent_state=owner.parent.state;owner.failure=None
        owner.base=SimpleNamespace(phase=lambda value:PicoSnapshotCancelOwner.phase(owner,value))
        for verb in ('share-open','share-cancel','share-open','share-select-owned'):activate(verb)
        current=activate('upload-fail');owner.phase(current)
        owner.state=dict(stage='prepare-issued',proof=None);owner.verb='upload-fail'
        self.assertFalse(owner.report()['precedingShareQualified']);self.assertFalse(owner.report()['fullSnapshotRecipe'])
        with self.assertRaises(NativeUIError):owner.phase(activate('upload'))
        changed=deepcopy(current);changed['activations'][-2]['stimulus']['verb']='share-cancel'
        with self.assertRaises((ValueError,RuntimeError)):owner.phase(changed)


class SnapshotUploadContextTests(unittest.TestCase):
    def fixture(self):
        original=context_source();original['history']['events']=original['history']['events'][:1];original['history']['sequence']=1
        owner=object.__new__(PicoSnapshotUploadOwner)
        owner.base=SimpleNamespace(state=dict(capture=dict(frame=0,requestId='snap_100_1',file=dict(path='/original/capture.png')),frames=[{}]),
            frame=lambda row:(None,original,None))
        row=dict(base=dict(script=dict(raw=json.dumps(context_source()))),provider=dict(domainId='01234567-89ab-cdef-0123-456789abcdef'))
        return owner,row

    def test_upload_context_joins_original_pending_domain_href_path_and_birth(self):
        owner,row=self.fixture();owner.capture_context(row)
        for fault in ('birth','domain','href','path','normalized','legacy','missing-pending'):
            owner,row=self.fixture();script=json.loads(row['base']['script']['raw']);current=script['captureContext']
            if fault=='birth':current['instance']='a'*32
            elif fault=='domain':current['entries']['previousSnapshotDomainID']['value']=row['provider']['domainId']
            elif fault=='href':current['entries']['previousSnapshotHref']['value']='hifi://new'
            elif fault=='path':current['entries']['previousStillSnapPath']['value']='/foreign.png'
            elif fault=='normalized':current['normalizedHref']='hifi://foreign'
            elif fault=='legacy':script['snapshotScriptOriginalsVersion']=2
            else:owner.base.state['capture']['requestId']='snap_100_999'
            row['base']['script']['raw']=json.dumps(script)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.capture_context(row)


class SnapshotUploadOriginalsTests(unittest.TestCase):
    def fixture(self,verb='upload-fail'):
        temporary=tempfile.TemporaryDirectory(prefix='pico-upload-originals-');self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        binding=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='123:original',sessionId='own-bridge',generation=0,targetFingerprint='3'*64)
        return root,binding,SnapshotUploadOriginals(root/('snapshot-'+verb+'-originals.json'),RUN,binding,verb)
    def test_complete_components_and_received_headers_are_immutable_scoped_and_cold_readable(self):
        root,binding,store=self.fixture();frame={key:dict(original=key) for key in ('base','upload','provider','account')};frame['hostMonotonic']=1.
        state=dict(frames=[frame],received=dict(metadata=dict(original='actual retained binary header')))
        encoded=store.encode(state);cold=SnapshotUploadOriginals(store.root.path,RUN,binding,'upload-fail')
        self.assertEqual(state,cold.decode(encoded));state['received']['metadata']['original']='mutated'
        self.assertEqual('actual retained binary header',cold.decode(encoded)['received']['metadata']['original'])
        with self.assertRaises(NativeUIError):SnapshotUploadOriginals(store.root.path,RUN,binding,'upload')
        with self.assertRaises(NativeUIError):store.put('ack',dict(uploaded=True))
        self.assertEqual(5,len(store.values))
    def test_orphan_and_changed_originals_remain_owned_instead_of_new_baselines(self):
        root,binding,store=self.fixture();store.put('provider',dict(actual='wire receipts'))
        child=store.history.store(0).path;child.write_bytes(child.read_bytes()+b' ')
        with self.assertRaises(NativeUIError):store.verify()
        store.root.path.unlink()
        with self.assertRaises(NativeUIError):SnapshotUploadOriginals(store.root.path,RUN,binding,'upload-fail')
        self.assertTrue(child.exists())


class SnapshotUploadFenceTests(unittest.TestCase):
    def fixture(self):
        owner=object.__new__(PicoSnapshotUploadOwner);clock=[20000,1.];current=dict(active=True,instance='original',createdEpochMs=1000,activations=[dict(original='upload-phase')],capturedEpochMs=20000)
        owner.anchor=(1.,20000,20000);owner.state=dict(source=deepcopy(current));owner.pin=lambda:None
        owner.base=SimpleNamespace(now=lambda:clock[1]);owner.native=SimpleNamespace(guard=lambda:True,clock_ms=lambda:clock[0])
        owner.source=SimpleNamespace(epoch_ms=lambda:clock[0],status=lambda previous:deepcopy(current))
        return owner,clock,current
    def test_final_phase_read_follows_last_native_guard_and_refuses_advanced_or_retired_phase(self):
        for fault in ('advanced','retired'):
            owner,clock,current=self.fixture()
            def late():
                if fault=='advanced':current['activations'].append(dict(original='next-phase'))
                else:current['active']=False
                return True
            owner.native.guard=late
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.fence()
    def test_last_source_clock_work_and_slow_final_cas_are_covered_with_either_clock_frozen(self):
        for fault in ('host','native','clock-read'):
            owner,clock,current=self.fixture()
            if fault=='host':clock[1]+=2
            elif fault=='native':clock[0]+=2000
            else:
                def late_clock():clock[1]+=2;return clock[0]
                owner.native.clock_ms=late_clock
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.fence()
    def publication(self):
        owner,clock,current=self.fixture();calls=[];owner.lock=SimpleNamespace(assert_held=lambda:None);owner.current=True
        owner.state.update(stage='input-issued',deliveries=[],frames=[]);owner.append=lambda:dict(original='fresh original frame')
        owner.qml=lambda command,row:calls.append('closed-normal-command');owner.before_input=lambda row,state:calls.append('original-before-input')
        def save(state):owner.state=state;calls.append('durable-intent')
        owner.save=save;return owner,clock,current,calls
    def test_late_parent_cas_phase_change_refuses_writer_and_keeps_exact_issued_command(self):
        owner,clock,current,calls=self.publication();save=owner.save
        def late(state):save(state);current['activations'].append(dict(original='advanced-during-CAS'))
        owner.save=late;command=dict(commandId='original-final-normal-envelope')
        with self.assertRaises(NativeUIError):owner.before_qml(command)
        self.assertEqual(command,owner.state['deliveries'][0]['command']);self.assertEqual('input-issued',owner.state['stage'])
        self.assertEqual(['closed-normal-command','original-before-input','durable-intent'],calls)
        with self.assertRaises(NativeUIError):owner.before_qml(command)
    def test_lost_control_response_cannot_reenter_send_from_an_issued_or_completed_owner(self):
        owner,clock,current=self.fixture();owner.lock=SimpleNamespace(held=lambda:__import__('contextlib').nullcontext())
        owner.load=lambda:None;owner.append=lambda:(_ for _ in ()).throw(AssertionError('Unexpected new source/input'))
        for phase in ('input-issued','observed','read-issued','acquired','quiet-issued','partial-ready'):
            owner.state['stage']=phase
            with self.subTest(phase=phase),self.assertRaises(NativeUIError):owner.send()


class SnapshotUploadArchiveTests(unittest.TestCase):
    def test_extra_mutation_cannot_hide_a_deleted_or_replaced_original_story_behind_the_same_count(self):
        baseline=dict(requests=[dict(requestId='a',method='POST')]);original=dict(requestId='b',method='POST')
        provider=dict(requests=baseline['requests']+[original,dict(requestId='c',method='GET')])
        mutation_scope(provider,baseline,[original])
        for method in ('DELETE','POST'):
            changed=deepcopy(provider);changed['requests'].append(dict(requestId='d',method=method))
            with self.subTest(method=method),self.assertRaises(NativeUIError):mutation_scope(changed,baseline,[original])

    def test_backend_retirement_or_phase_history_change_cannot_admit_ordinary_upload(self):
        phase=dict(activations=[dict(ticket='a'*32,stimulus=dict(verb='save')),dict(ticket='b'*32,stimulus=dict(verb='upload-fail'))])
        original=dict(active=True,ticket='b'*32,activations=[dict(ticket='a'*32,verb='save'),dict(ticket='b'*32,verb='upload-fail')])
        provider_phase(original,phase)
        for fault in ('retired','ticket','missing','rewritten','extra'):
            value=deepcopy(original)
            if fault=='retired':value['active']=False
            elif fault=='ticket':value['ticket']='c'*32
            elif fault=='missing':value['activations'].pop(0)
            elif fault=='rewritten':value['activations'][0]['verb']='share-open'
            else:value['activations'].append(dict(ticket='c'*32,verb='upload'))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):provider_phase(value,phase)

    def test_archived_quiet_cannot_omit_an_original_intermediate_observation(self):
        quiet_indices([2,3,4],5)
        for rows in ([2,4],[4,3,2],[2,2,3],[2],[2,3,5],[True,2,3]):
            with self.subTest(rows=rows),self.assertRaises(NativeUIError):quiet_indices(rows,5)

    def test_unresolved_input_cannot_carry_an_archived_effect_or_claim_a_read_phase(self):
        owner=object.__new__(PicoSnapshotUploadOwner);owner.run=RUN;owner.parent_sha='1'*64;owner.failure_disk=None;owner.verb='upload-fail'
        owner.phase=lambda value:None;owner.artifact_root=lambda:dict(device=1,inode=2)
        owner.frame=lambda row:(_ for _ in ()).throw(AssertionError('Original frame verification reached'))
        value=dict(stage='input-issued',source={},parentSha256=owner.parent_sha,failureSha256=None,frames=[{}],deliveries=[],
            artifacts={},quiet=[],job='',proof=None,readId='',scope=RUN,received=None,artifactRoot=owner.artifact_root())
        with self.assertRaisesRegex(AssertionError,'Original frame verification reached'):owner.validate(value)
        for fault in ('job','proof','read-issued','acquired'):
            changed=deepcopy(value)
            if fault=='job':changed['job']='a'*32
            elif fault=='proof':changed['proof']=dict(frame=0)
            else:changed['stage']=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.validate(changed)


if __name__=='__main__':unittest.main()
