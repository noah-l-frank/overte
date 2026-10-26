"""Native lifetime is modeled; close, weak expiry and retained originals real."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_actions import SnapshotShareUIAction
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_seal_owner import SnapshotShareAdmissionSealOwner,ShareAdmissionSealAction
from ios.adapters import snapshot_share_seal as source
from ios.self_tests.snapshot_share_seal_domain import ShareSealDomain,ShareSealFlow,RUN
from ios.self_tests.snapshot_share_domain import SYSTEM_UI
from ios.self_tests.snapshot_share_domain import REAL_SLEEP,WDAView


class SnapshotShareSealTests(unittest.TestCase):
    def history(self,domain):
        return SnapshotShareAdmissionSealOwner.history(PrivateFeatureState(domain.root/'share-admission-seal-owner.json'),domain.source_lock,
            domain.binding,RUN,domain.fixture_url,domain.ipa,domain.admission_store)

    def test_actual_descriptor_close_and_exact_published_outputs_survive_pure_replay(self):
        domain=ShareSealDomain(self);descriptor=domain.first_fd
        originals={name:(domain.documents/pin['name']).read_bytes() for name,pin in domain.published.items()}
        with domain.seal_owner() as owner:
            proof=owner.seal();self.assertTrue(proof['admissionReaderClosed']);self.assertTrue(proof['sourceOutputsRetirementRequired'])
            packet,raw=owner.original();self.assertEqual(domain.original,packet)
            for field,value in (('processId',True),('sequence',True),('snapshotShareAdmissionSealVersion',True),('instance','0'*32),
                    ('requestId','ios-'+'0'*32),('sourceBirthClock',dict(epochMs=1,monotonicMs=1))):
                changed=deepcopy(packet);changed[field]=value
                with self.subTest(field=field),self.assertRaises(NativeUIError):source.original(changed,owner.state['nonce'],owner.admission)
            for fault in ('hash','parent','size','name','failed-close','collector','reader','duration'):
                changed=deepcopy(packet)
                if fault=='hash':changed['outputs'][0]['sha256']='0'*64
                elif fault=='parent':changed['outputs'][0]['parentIdentity']='0'*64
                elif fault=='size':changed['outputs'][0]['byteCount']=True
                elif fault=='name':changed['outputs'][0]['name']='snapshot-share-retire.json'
                elif fault=='failed-close':changed['descriptorClose']['succeeded']=False;changed['readerClosed']=False
                elif fault=='collector':changed['collectorAlive']=True
                elif fault=='reader':changed['outputReadersClosed']=False
                else:changed['clockAfter']['epochMs']+=1500;changed['clockAfter']['monotonicMs']+=1500
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.qualified(source.original(changed,owner.state['nonce'],owner.admission))
            self.assertEqual(raw,owner.original()[1])
        with self.assertRaises(OSError):os.fstat(descriptor)
        self.assertEqual(1,domain.close_calls);self.assertEqual(originals,{name:(domain.documents/pin['name']).read_bytes() for name,pin in domain.published.items()})
        with (domain.source_lock.held(),patch.object(domain,'call',side_effect=AssertionError('Live SDK called')),
                patch.object(domain,'execute',side_effect=AssertionError('Live process queried')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('History wrote state'))):
            before={p:(p.stat().st_ino,p.stat().st_mtime_ns,p.read_bytes()) for p in domain.root.iterdir() if p.is_file()}
            owner=self.history(domain);self.assertEqual(proof,owner.proof())
            with self.assertRaises(NativeUIError):owner.seal()
            self.assertEqual(before,{p:(p.stat().st_ino,p.stat().st_mtime_ns,p.read_bytes()) for p in before})

    def test_normal_share_transfer_and_run_retirement_join_the_admission_seal_owner(self):
        domain=ShareSealFlow(self)
        with domain.owner() as owner,self.assertRaises(NativeUIError):owner.admission_seal_owner()
        domain.activate('share-open','1'*32)
        with domain.owner() as owner:owner.open('1'*32)
        domain.activate('share-select-owned','2'*32)
        with domain.owner() as owner:
            transfer=owner.select('2'*32)
            with self.assertRaises(NativeUIError):owner.admission_seal_owner()
            cleanup=owner.cleanup();seal=owner.admission_seal_owner();proof=seal.seal()
            self.assertTrue(proof['admissionReaderClosed']);self.assertEqual(owner.archive_binding['processIdentity'],str(proof['processId']))
            self.assertEqual('archive-source-seal',owner.state['handoffs'][-1]['label']);self.assertTrue(domain.archive.foreground)
        self.assertEqual((1,1),(domain.archive.seal_calls,domain.archive.close_calls))
        self.assertFalse(domain.archive.group_run.exists());self.assertFalse(domain.archive.archive_run.exists())
        self.assertTrue(domain.main.f.f.h.path.exists());self.assertTrue((domain.archive.documents/'snapshot-share-chunk.json').exists())
        with domain.main.ctx.lock.held(),domain.archive.source_lock.held():
            owner=IOSSnapshotShareOwner.history(PrivateFeatureState(domain.main.ctx.root/'snapshot-share-owner.json'),domain.main.ctx.lock,
                domain.archive.source_lock,domain.main.ctx.binding,domain.archive.binding,RUN,domain.archive.fixture_url,SYSTEM_UI,
                domain.primary.target['appId'],domain.archive.ipa,domain.archive.admission_store)
            self.assertEqual(transfer,owner.proof());self.assertEqual(cleanup,owner.cleanup_proof())
            sealed=SnapshotShareAdmissionSealOwner.history(PrivateFeatureState(domain.archive.root/'share-admission-seal-owner.json'),domain.archive.source_lock,
                domain.archive.binding,RUN,domain.archive.fixture_url,domain.archive.ipa,domain.archive.admission_store)
            self.assertEqual(proof,sealed.proof())

    def test_lost_normal_close_return_reads_immutable_original_without_second_input(self):
        domain=ShareSealDomain(self);domain.flow.lost_buttons.add('snapshot.share.archive.admission-seal')
        with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        original=deepcopy(domain.original)
        with domain.seal_owner() as owner:self.assertTrue(owner.seal()['admissionReaderClosed']);self.assertEqual(original,owner.original()[0])
        self.assertEqual((1,1),(domain.seal_calls,domain.close_calls));self.assertEqual(1,domain.view.clicks.count('snapshot.share.archive.admission-seal'))

    def test_lost_readonly_value_return_does_not_close_or_click_again(self):
        domain=ShareSealDomain(self);domain.lost_output=True
        with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        with domain.seal_owner() as owner:self.assertTrue(owner.seal()['admissionReaderClosed'])
        self.assertEqual((1,1),(domain.seal_calls,domain.close_calls))

    def test_recreated_Archive_view_reads_same_source_bytes_after_lost_close_return(self):
        domain=ShareSealDomain(self);domain.flow.lost_buttons.add('snapshot.share.archive.admission-seal')
        with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        raw=domain.original_text.encode('utf-8');domain.view=WDAView(domain.flow,'seal',domain.binding['sessionId'])
        self.assertEqual('',domain.view.output)
        with domain.seal_owner() as owner:
            self.assertTrue(owner.seal()['admissionReaderClosed']);self.assertEqual(raw,owner.original()[1])
        self.assertEqual((1,1),(domain.seal_calls,domain.close_calls));self.assertEqual([],domain.view.clicks)

    def test_byte_identical_published_output_replacement_blocks_close_without_resend(self):
        domain=ShareSealDomain(self);path=domain.documents/domain.published['identity']['name'];replacement=path.with_name('replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        for _ in range(2):
            with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        self.assertEqual((1,0),(domain.seal_calls,domain.close_calls));os.fstat(domain.first_fd);self.assertIsNone(domain.original)

    def test_actual_held_collector_lease_blocks_close_even_when_identity_is_ready(self):
        domain=ShareSealDomain(self);domain.hold_collector()
        with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        self.assertEqual((0,0),(domain.seal_calls,domain.close_calls));os.fstat(domain.first_fd)
        self.assertIsNotNone(domain.collector_ref());domain.collectors.clear();self.assertIsNone(domain.collector_ref())
        with domain.seal_owner() as owner:self.assertTrue(owner.seal()['admissionReaderClosed'])
        self.assertEqual((1,1),(domain.seal_calls,domain.close_calls))

    def test_actual_expired_collector_allows_the_first_normal_seal(self):
        domain=ShareSealDomain(self);domain.hold_collector();domain.collectors.clear();self.assertIsNone(domain.collector_ref())
        with domain.seal_owner() as owner:self.assertTrue(owner.seal()['admissionReaderClosed'])
        self.assertEqual((1,1),(domain.seal_calls,domain.close_calls))

    def test_unknown_actual_close_return_stays_historical_and_never_repeats_close(self):
        domain=ShareSealDomain(self);domain.unknown_close_return=True
        for _ in range(2):
            with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        self.assertEqual((1,1),(domain.seal_calls,domain.close_calls))
        with domain.source_lock.held():
            owner=self.history(domain);packet,_raw=owner.original();self.assertFalse(packet['readerClosed']);self.assertIsNone(owner.state['result'])
            with self.assertRaises(NativeUIError):owner.proof()

    def test_same_byte_installed_node_replacement_cannot_reanchor_the_bundle_reader(self):
        domain=ShareSealDomain(self);path=domain.installed/'share-archive';path=path if path.exists() else next(p for p in domain.installed.iterdir() if p.is_file())
        replacement=path.with_name('replacement');replacement.write_bytes(path.read_bytes());replacement.replace(path)
        with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        self.assertEqual((1,0),(domain.seal_calls,domain.close_calls));os.fstat(domain.first_fd)

    def test_late_recovered_original_keeps_first_clocks_and_does_not_become_qualified(self):
        domain=ShareSealDomain(self);domain.flow.lost_buttons.add('snapshot.share.archive.admission-seal')
        with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        original=deepcopy(domain.original);REAL_SLEEP(5.6)
        with domain.seal_owner() as owner,self.assertRaises(NativeUIError):owner.seal()
        with domain.source_lock.held():
            owner=self.history(domain);self.assertEqual(original,owner.original()[0]);action=owner.action(True)
            before=deepcopy(action.state['before']);ref=deepcopy(action.state['proof']);raw=action.original()
            with self.assertRaises(NativeUIError):owner.proof()
            self.assertEqual(before,action.state['before']);self.assertEqual(ref,action.state['proof']);self.assertEqual(raw,action.original())
        self.assertEqual((1,1),(domain.seal_calls,domain.close_calls))

    def test_profiles_cannot_substitute_ordinary_share_actions_or_namespace(self):
        domain=ShareSealDomain(self)
        with domain.seal_owner() as owner:
            owner.seal();plan=owner.action(True).plan
            with self.assertRaises(NativeUIError):SnapshotShareUIAction(owner.root,owner.lock,owner.binding,owner.run,1,plan,lambda:True,historical=True)
            changed=deepcopy(plan);changed['control']='snapshot.share.inspect';changed['fields']=[['snapshot.share.query','ios-'+'a'*32]]
            with self.assertRaises(NativeUIError):ShareAdmissionSealAction(owner.root,owner.lock,owner.binding,owner.run,1,changed,lambda:True,historical=True)
            self.assertNotEqual(owner.action(True)._namespace,SnapshotShareUIAction._namespace)


if __name__=='__main__':unittest.main()
