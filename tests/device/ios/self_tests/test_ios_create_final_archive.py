"""Actual qualified actor files; modeled native SDKs, no device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_retirement_publisher import PhaseRetirementPublisher
from feature_journeys.retirement_receipts import PhaseRetirementJournal
from ios.adapters.create_final_archive import CreateFinalArchive
from ios.self_tests import test_ios_create_retirement as retirement_fixture


class FinalArchiveTests(unittest.TestCase):
    def setUp(self):
        self.h=retirement_fixture.CreateRetirementTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
    def publication(self,owner,original,journal):
        receipts=PhaseRetirementJournal(journal);client=owner.source.phase.client;request=client.request
        def actual(path,value=None,method=None,**kwargs):
            if path.endswith('/retirements'):
                if value is not None:receipts.publish(owner.run,value);return {}
                return receipts.snapshot(owner.run)
            return request(path,value,method,**kwargs)
        client.request=actual
        publisher=PhaseRetirementPublisher(PrivateFeatureState(owner.store.path.with_name('phase-retirement-create-'+owner.run+'-actor.json')),
            owner.binding,owner.source.phase,owner.lock,lambda:True,owner.frozen().validate_original,epoch_ms=owner.source.epoch_ms,monotonic=owner.source.monotonic)
        publisher.publish(original);receipt=publisher.load(publisher.state['records'][-1])
        return dict(localSha256=digest(original),publication=receipt,publisherOriginal=publisher.store.read())
    def seal(self,*,lost=False):
        h=self.h
        journal=h.h.authority();facts=h.h.facts();facts.capture();owner=h.owner(facts);owner.admit()
        journal.activate(owner.run,'2'*32,'cleanup',{});original=owner.cleanup('2'*32);frozen=owner.frozen();measured=frozen.validate_original(original)
        paired=self.publication(owner,original,journal);journal.close(owner.run);phase=owner.source.phase.status()
        feature=dict(phase='cleaned',binding=owner.binding,phaseInstance=phase['instance'],retirement={key:deepcopy(value) for key,value in paired.items() if key!='publisherOriginal'})
        store=PrivateFeatureState(owner.store.path.with_name('ios-create-actor-'+owner.run+'-final.json'))
        archive=CreateFinalArchive(store,owner.store.path.parent,owner.binding,owner.run,'actor',owner.lock)
        arguments=dict(phase_original=phase,feature=feature,original=original,validate=frozen.validate_original,
            paired=paired,directories=[str(h.h.primary_h.root),str(h.h.peer_h.root)],
            extra=list(owner.store.path.parent.glob('phase-retirement-create-'+owner.run+'-actor*.json')),excluded=[store.path])
        if lost:
            save=archive.intent
            def intent(kind,value):
                save(kind,value)
                if value['phase']=='saved':raise OSError('Lost return after actual immutable final frame was saved')
            archive.frames.intent=intent
            with self.assertRaises(OSError):archive.seal(**arguments)
            self.assertEqual('writing',store.read()['phase']);self.assertEqual('saved',store.read()['pending']['phase'])
            archive=CreateFinalArchive(store,owner.store.path.parent,owner.binding,owner.run,'actor',owner.lock);archive.recover()
        else:archive.seal(**arguments)
        return owner,archive,measured
    def test_true_whole_originals_are_sealed_then_reopened_without_sdk_or_a_fresh_clock(self):
        with self.h.h.held():
            owner,archive,measured=self.seal();requests=deepcopy(self.h.native.requests)
            def forbidden(*_args,**_kwargs):raise AssertionError('A completed archive touched native SDK or fixture HTTP')
            with patch.object(owner.source.phase.client,'request',side_effect=forbidden),patch.object(owner.source,'capture',side_effect=forbidden):
                value=archive.verify();again=CreateFinalArchive(archive.store,archive.root,owner.binding,owner.run,'actor',owner.lock).verify()
            self.assertEqual(value,again);self.assertEqual(measured,value['measured']);self.assertEqual(requests,self.h.native.requests)
            self.assertFalse(value['phaseOriginal']['active']);self.assertGreater(len(value['files']),10)
    def test_saved_final_frame_unknown_return_is_adopted_read_only_and_original_file_replacement_is_rejected(self):
        with self.h.h.held():
            owner,archive,_=self.seal(lost=True);value=archive.verify();path=owner.source.record_store(1).path
            actual=path.read_bytes();path.unlink();path.write_bytes(actual);path.chmod(0o600)
            # Identical bytes on a replacement inode are not the sealed
            # original. A warm verification cannot conceal this boundary.
            with self.assertRaises(NativeUIError):archive.verify()
            self.assertTrue(value['files']);self.assertEqual('complete',archive.state['phase'])
    def test_actual_proof_carrier_mutation_during_pure_validation_prevents_seal(self):
        with self.h.h.held():
            h=self.h;journal=h.h.authority();facts=h.h.facts();facts.capture();owner=h.owner(facts);owner.admit()
            journal.activate(owner.run,'2'*32,'cleanup',{});original=owner.cleanup('2'*32);frozen=owner.frozen()
            paired=self.publication(owner,original,journal);journal.close(owner.run)
            phase=owner.source.phase.status();store=PrivateFeatureState(owner.store.path.with_name('ios-create-actor-'+owner.run+'-final.json'))
            archive=CreateFinalArchive(store,owner.store.path.parent,owner.binding,owner.run,'actor',owner.lock)
            paired_validation=archive.paired
            def altered(*args):
                paired_validation(*args);path=owner.source.record_store(1).path
                raw=path.read_bytes();path.write_bytes(raw+b' ')
            archive.paired=altered
            with self.assertRaises(NativeUIError):archive.seal(phase_original=phase,feature=dict(phase='cleaned',binding=owner.binding,phaseInstance=phase['instance'],retirement=paired),
                original=original,validate=frozen.validate_original,paired=paired,directories=[str(owner.store.path.parent)],extra=[],excluded=[store.path])
            self.assertIsNone(store.read())


if __name__=='__main__':unittest.main()
