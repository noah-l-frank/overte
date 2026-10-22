"""Actual Admission/source/file retirement logic over synthetic boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_emote_admission_owner import Model,POLICY
from test_emote_sources import RUN
from overte_phone_emote_admission import PhoneEmoteAdmission
from overte_phone_script_history import unpack
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError


class AdmissionRetirementTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-admission-retirement-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name));self.saved=PrivateFeatureState(self.model.root/'retained-admission.json')

    def owner(self,role='primary'):return PhoneEmoteAdmission(self.model.source(role),POLICY)
    def cleanup(self):self.model.journal.activate(RUN,'a'*32,'cleanup',{})
    def retain(self,value):
        owner=self.owner(value['header']['role']);self.assertEqual(value['header'],owner.store.read())
        self.saved.write(value,self.saved.read());self.assertEqual(value,self.saved.read())

    def test_each_role_retires_actual_admitted_originals_and_replays_after_new_source_reads(self):
        for role in ('primary','actor'):
            with self.subTest(role=role):
                self.setUp();m=self.model
                with m.lock.held():
                    owner=self.owner(role);owner.wait(sleep=m.sleep);header=deepcopy(owner.previous);self.cleanup()
                    calls=deepcopy(m.calls);count=len(m.inventory.commands)
                    value=owner.retire(self.retain)
                    self.assertEqual(header,value['header']);self.assertIsNone(owner.store.read())
                    self.assertEqual(['phase-read','phase-read'],m.calls[len(calls):]);self.assertEqual(count,len(m.inventory.commands))
                    source=m.source(role);source.read();calls=deepcopy(m.calls)
                    state=PhoneEmoteAdmission.archive(value,source,POLICY)
                    self.assertEqual('admitted',state['phase']);self.assertEqual([1,2,3],state['window']['records'])
                    self.assertEqual(calls,m.calls);self.assertEqual(header,self.saved.read()['header'])

    def test_abandoned_cache_read_and_partial_originals_are_not_promoted_during_retirement(self):
        for fault in ('cache','planned','opened','saved'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model
                with m.lock.held():
                    owner=self.owner();intent=owner.originals.intent
                    def interrupt(kind,value):
                        intent(kind,value)
                        if value['phase']==fault:raise NativeUIError('Synthetic lost admission callback')
                    owner.originals.intent=interrupt
                    if fault=='cache':m.inventory.resources[0]['model']['sha256']='f'*64
                    with self.assertRaises(NativeUIError):owner.read()
                    header=deepcopy(owner.previous);self.cleanup();owner=self.owner();calls=deepcopy(m.calls)
                    value=owner.retire(self.retain);state=PhoneEmoteAdmission.archive(value,owner.source,POLICY)
                    self.assertEqual('reading',state['phase']);self.assertEqual([],state['records']);self.assertIsNone(state['window'])
                    self.assertEqual(header,value['header']);self.assertEqual(['phase-read','phase-read'],m.calls[len(calls):])
                    if fault=='opened':self.assertEqual(0,value['originalDiagnostic']['bytes'])
                    else:self.assertIsNone(value['originalDiagnostic'])
                    self.assertNotIn('admitted',value);self.assertNotIn('cleaned',value)

    def test_retirement_requires_actual_cleanup_and_durable_unchanged_retention(self):
        for fault in ('normal','reject','lost','mutation','phase','slow','discard'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model
                with m.lock.held():
                    owner=self.owner();owner.wait(sleep=m.sleep);header=deepcopy(owner.previous)
                    if fault!='normal':self.cleanup()
                    def retain(value):
                        self.retain(value)
                        if fault=='reject':return False
                        if fault=='lost':raise NativeUIError('Synthetic lost archive return')
                        if fault=='mutation':owner.originals.path(owner.originals.expand(owner.state['records'][0])).write_bytes(b'{}')
                        elif fault=='phase':m.journal.activate(RUN,'b'*32,'open',{})
                        elif fault=='slow':m.clock+=5.1
                    if fault=='discard':
                        with patch.object(owner.store,'discard',return_value=None),self.assertRaises(NativeUIError):owner.retire(retain)
                    else:
                        with self.assertRaises(NativeUIError):owner.retire(retain)
                    self.assertEqual(header,owner.store.read())
                    if fault=='normal':self.assertIsNone(self.saved.read())

    def test_exact_retained_context_recovers_lost_retirement_returns_without_reacquisition(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.wait(sleep=m.sleep);self.cleanup()
            def lost(value):self.retain(value);raise NativeUIError('Synthetic lost retention callback')
            with self.assertRaises(NativeUIError):owner.retire(lost)
            proof=self.saved.read();owner=self.owner();calls=deepcopy(m.calls)
            self.assertEqual(proof,owner.retire(lambda value:self.assertEqual(proof,value),retained=proof))
            self.assertEqual(['phase-read','phase-read'],m.calls[len(calls):]);self.assertIsNone(owner.store.read())
            owner=self.owner();self.assertEqual(proof,owner.retire(lambda value:self.assertEqual(proof,value),retained=proof))
            self.assertIsNone(owner.store.read())

    def test_foreign_policy_source_header_role_and_derived_window_cannot_borrow_valid_files(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.wait(sleep=m.sleep);self.cleanup();proof=owner.retire(self.retain)
            for fault in ('role','policy','source','window','diagnostic'):
                value=deepcopy(proof)
                if fault=='role':value['header']['role']='actor'
                elif fault=='policy':value['header']['policy']['domainId']='e'*32
                elif fault=='source':value['sourceHeader']['binding']['artifactSha256']='f'*64
                elif fault=='diagnostic':value['originalDiagnostic']={}
                else:
                    from overte_phone_script_history import pack
                    state=unpack(value['header']['payload'])[0];state['window']['records']=[1,2,2];value['header']['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):PhoneEmoteAdmission.archive(value,owner.source,POLICY)

    def test_pending_source_must_transfer_before_a_missing_admission_result_can_retire(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();intent=owner.source.originals.intent
            def interrupt(kind,value):
                intent(kind,value)
                if kind=='original' and value['phase']=='opened':raise NativeUIError('Synthetic interrupted first source file')
            owner.source.originals.intent=interrupt
            with self.assertRaises(NativeUIError):owner.read()
            self.cleanup();owner=self.owner();header=deepcopy(owner.previous)
            with self.assertRaises(NativeUIError):owner.retire(self.retain)
            self.assertIsNone(self.saved.read());self.assertEqual(header,owner.store.read())
            source_archive=PrivateFeatureState(m.root/'retained-source.json')
            owner.source.transfer_failed(lambda value:source_archive.write(value,None))
            self.assertIsNotNone(source_archive.read());owner=self.owner();proof=owner.retire(self.retain)
            state=PhoneEmoteAdmission.archive(proof,owner.source,POLICY)
            self.assertEqual('reading',state['phase']);self.assertEqual([],state['records']);self.assertIsNone(state['window'])
            self.assertEqual([],owner.source.frames);self.assertIsNone(owner.store.read())


if __name__=='__main__':unittest.main()
