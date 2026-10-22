"""Original failed work transfer over synthetic producers; no device verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_run
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_emote_failures import PhoneEmoteFailures
from overte_phone_emote_lifetime import PhoneEmoteLifetime
from overte_phone_script_history import pack,unpack
from test_emote_sources import RUN


class LifetimeFailureTests(unittest.TestCase):
    setUp=test_emote_run.EmoteRunTests.setUp
    owner=test_emote_run.EmoteRunTests.owner
    prepared=test_emote_run.EmoteRunTests.prepared
    cleanup_phase=test_emote_run.EmoteRunTests.cleanup_phase

    def cleaning(self,run):
        self.cleanup_phase()
        with run.lock.held():run.state.update(phase='cleaning-inputs',cleanupTicket='a'*32);run.save()

    def failed(self,run,role='primary',*,source_failure=False,completed=0):
        # Caller holds the real source lock. Only the native producer fails.
        m=self.model;owner=PhoneEmoteLifetime(run.source(role))
        for _ in range(completed):owner.read();m.sleep(.25)
        if source_failure:
            m.admission_fault='old-probe'
            try:
                with self.assertRaises(NativeUIError):owner.read()
            finally:m.admission_fault=None
        else:
            with patch.object(m,'work_send',side_effect=NativeUIError('Synthetic lost original work query')),self.assertRaises(NativeUIError):owner.read()
        self.assertEqual('reading',owner.state['phase']);return deepcopy(owner.previous)

    def retained(self,proof):
        store=PrivateFeatureState(self.model.root/'retained-work-failure.json');store.write(proof,store.read())
        self.assertEqual(proof,store.read())

    def test_failed_work_transfers_no_sample_and_only_new_actual_reads_can_complete_a_window(self):
        m=self.model;run=self.prepared();self.cleaning(run)
        with run.lock.held():
            header=self.failed(run,completed=2);owner=PhoneEmoteLifetime(run.source());before=len(m.work_commands)
            proof=owner.transfer_failed(self.retained)
            self.assertEqual(header,proof['header']);self.assertEqual(before,len(m.work_commands));self.assertEqual('ready',owner.state['phase'])
            self.assertEqual(2,len(owner.state['records']));self.assertIsNone(owner.state['window'])
            state=PhoneEmoteLifetime.failure_archive(proof,owner.source);self.assertEqual('reading',state['phase']);self.assertEqual(2,len(state['records']))
            owner=PhoneEmoteLifetime(run.source());owner.wait(sleep=m.sleep)
            self.assertEqual('complete',owner.state['phase']);self.assertGreater(len(m.work_commands),before)
            self.assertEqual(header,proof['header']);self.assertIsNotNone(owner.store.read())

    def test_source_failure_must_transfer_first_and_parent_collects_source_then_lifetime(self):
        m=self.model;run=self.prepared();self.cleaning(run)
        with run.lock.held():
            header=self.failed(run,source_failure=True);owner=PhoneEmoteLifetime(run.source())
            with self.assertRaises(NativeUIError):owner.transfer_failed(self.retained)
            self.assertEqual(header,owner.store.read());failure=PhoneEmoteFailures(run)
            failure.collect_sources();before=len(m.work_commands);failure.collect_lifetimes()
            rows=failure.originals.restore(failure.state['manifests'],failure.state['count'])
            self.assertEqual(['source','lifetime'],[row['kind'] for row in rows]);self.assertEqual(header,rows[-1]['archive']['header'])
            self.assertEqual(before,len(m.work_commands));self.assertEqual('ready',PhoneEmoteLifetime(run.source()).state['phase'])

    def test_real_run_cleanup_collects_both_roles_without_copying_primary_work(self):
        m=self.model;run=self.prepared();self.cleaning(run)
        with run.lock.held():headers={role:self.failed(run,role,completed=1) for role in ('primary','actor')}
        result=run.cleanup_inputs(dict(contractVersion=18,runId=RUN));self.assertEqual(1,result['emoteCleanupInputsVersion'])
        with run.lock.held():
            failure=PhoneEmoteFailures(run);rows=failure.originals.restore(failure.state['manifests'],failure.state['count'])
            self.assertEqual(['lifetime','lifetime','admission'],[row['kind'] for row in rows])
            for row,role in zip(rows,('primary','actor')):
                self.assertEqual(headers[role],row['archive']['header']);self.assertEqual(7,row['emoteFailureRecordVersion']);failure.record(row,row['index'])
                owner=PhoneEmoteLifetime(run.source(role));self.assertEqual('ready',owner.state['phase']);self.assertEqual(1,len(owner.state['records']))
            self.assertNotEqual(unpack(headers['primary']['payload'])[0]['records'][0]['work']['requestId'],unpack(headers['actor']['payload'])[0]['records'][0]['work']['requestId'])
            self.assertIsNotNone(failure.store.read());self.assertIsNotNone(run.store.read())

    def test_rejected_slow_or_phase_changing_retention_keeps_original_pending_ownership(self):
        for fault in ('reject','slow','phase'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model;run=self.prepared();self.cleaning(run)
                with run.lock.held():
                    header=self.failed(run);owner=PhoneEmoteLifetime(run.source())
                    def retain(proof):
                        self.retained(proof)
                        if fault=='reject':return False
                        if fault=='slow':m.clock+=6
                        if fault=='phase':m.call('open')
                    with self.assertRaises(NativeUIError):owner.transfer_failed(retain)
                    self.assertEqual(header,owner.store.read());self.assertEqual('reading',unpack(owner.store.read()['payload'])[0]['phase'])

    def test_lost_callback_return_reuses_same_old_proof_without_new_queries(self):
        m=self.model;run=self.prepared();self.cleaning(run)
        with run.lock.held():
            header=self.failed(run);owner=PhoneEmoteLifetime(run.source())
            def lost(proof):self.retained(proof);raise OSError('Synthetic lost retained work return')
            with self.assertRaises(OSError):owner.transfer_failed(lost)
            proof=PrivateFeatureState(m.root/'retained-work-failure.json').read();calls=deepcopy(m.calls);work=len(m.work_commands);m.sleep(2)
            current=PhoneEmoteLifetime(run.source());self.assertEqual(proof,current.transfer_failed(self.retained,retained=proof))
            self.assertEqual(header,proof['header']);self.assertEqual(work,len(m.work_commands));self.assertTrue(all(call=='phase-read' for call in m.calls[len(calls):]))
            self.assertEqual(proof,PhoneEmoteLifetime(run.source()).transfer_failed(self.retained,retained=proof))

    def test_lost_enclosing_completion_reuses_original_record_without_duplicate_or_query(self):
        m=self.model;run=self.prepared();self.cleaning(run)
        with run.lock.held():
            header=self.failed(run);owner=PhoneEmoteFailures(run);save=owner.save
            def lost():
                if owner.state['pending'] is None:raise NativeUIError('Synthetic lost failure-owner completion')
                save()
            with patch.object(owner,'save',side_effect=lost),self.assertRaises(NativeUIError):owner.collect_lifetimes()
            self.assertEqual('ready',PhoneEmoteLifetime(run.source()).state['phase']);work=len(m.work_commands)
            current=PhoneEmoteFailures(run);current.collect_lifetimes();current.collect_lifetimes()
            self.assertEqual(1,current.state['count']);self.assertEqual(work,len(m.work_commands));self.assertIsNone(current.state['pending'])
            rows=current.originals.restore(current.state['manifests'],1);self.assertEqual(header,rows[0]['archive']['header'])

    def test_planned_opened_saved_original_and_manifest_interruptions_resume_owned_bytes(self):
        for boundary in ('original-planned','original-opened','original-saved','manifest-planned','manifest-saved'):
            with self.subTest(boundary=boundary):
                self.setUp();m=self.model;run=self.prepared();self.cleaning(run)
                with run.lock.held():
                    header=self.failed(run);owner=PhoneEmoteFailures(run);intent=owner.originals.intent
                    def interrupt(kind,value):
                        intent(kind,value)
                        if kind+'-'+value['phase']==boundary:raise NativeUIError('Synthetic lost lifetime archive commit')
                    with patch.object(owner.originals,'intent',side_effect=interrupt),self.assertRaises(NativeUIError):owner.collect_lifetimes()
                    self.assertEqual(header,PhoneEmoteLifetime(run.source()).previous);work=len(m.work_commands)
                    current=PhoneEmoteFailures(run);current.collect_lifetimes()
                    rows=current.originals.restore(current.state['manifests'],1);self.assertEqual(header,rows[0]['archive']['header'])
                    self.assertEqual(work,len(m.work_commands));self.assertEqual(1,current.state['count'])

    def test_ignored_parent_intent_or_lifetime_clear_cannot_release_pending_ownership(self):
        m=self.model;run=self.prepared();self.cleaning(run)
        with run.lock.held():
            header=self.failed(run);owner=PhoneEmoteFailures(run)
            with patch.object(owner.store,'write',return_value=None),self.assertRaises(NativeUIError):owner.collect_lifetimes()
            self.assertEqual(header,PhoneEmoteLifetime(run.source()).previous)
            life=PhoneEmoteLifetime(run.source())
            with patch.object(life.store,'write',return_value=None),self.assertRaises(NativeUIError):life.transfer_failed(self.retained)
            self.assertEqual(header,life.store.read());self.assertEqual([],list(m.root.glob('emote-frame-source-failures-*.json')))

    def test_foreign_or_changed_failure_proof_and_completed_window_cannot_be_transferred(self):
        m=self.model;run=self.prepared();self.cleaning(run)
        with run.lock.held():
            self.failed(run,completed=1);owner=PhoneEmoteLifetime(run.source());proof=owner.transfer_failed(self.retained)
            for fault in ('role','binding','version','work','segment','phase','kind'):
                value=deepcopy(proof)
                if fault=='role':value['header']['role']='actor'
                elif fault=='binding':value['header']['binding']['processIdentity']='32:foreign'
                elif fault=='version':value['emoteLifetimeFailureArchiveVersion']=2
                elif fault=='segment':value['segment']=1
                elif fault=='phase':value['cleanup']['activations'][-1]['ticket']='f'*32
                elif fault=='kind':value['emoteLifetimeRetirementVersion']=value.pop('emoteLifetimeFailureArchiveVersion')
                else:
                    state=unpack(value['header']['payload'])[0];state['records'][0]['work']['source']['manager']['instance']='f'*32;value['header']['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):PhoneEmoteLifetime(run.source()).transfer_failed(self.retained,retained=value)
            current=PhoneEmoteLifetime(run.source());current.wait(sleep=m.sleep)
            with self.assertRaises(NativeUIError):current.transfer_failed(self.retained)

    def test_unknown_ready_lifetime_version_cannot_skip_the_parent_collector(self):
        run=self.prepared();self.cleaning(run)
        with run.lock.held():
            self.failed(run);life=PhoneEmoteLifetime(run.source());life.transfer_failed(self.retained)
            header=deepcopy(life.previous);header['emoteLifetimeVersion']=999;life.store.write(header,life.previous)
            with self.assertRaises(NativeUIError):PhoneEmoteFailures(run).collect_lifetimes()
            self.assertEqual(header,life.store.read())

    def test_legacy_v3_failure_owner_is_read_without_rewriting_old_original_bytes(self):
        m=self.model;run=self.prepared();self.cleaning(run)
        with run.lock.held():
            self.failed(run,source_failure=True)
            with patch('overte_phone_emote_failures.VERSION',3):
                owner=PhoneEmoteFailures(run);owner.collect_sources()
            rows=owner.originals.restore(owner.state['manifests'],1);old=deepcopy(owner.previous)
            self.assertEqual(3,old['emoteFailureOwnerVersion']);self.assertEqual(3,rows[0]['emoteFailureRecordVersion'])
            current=PhoneEmoteFailures(run);self.assertEqual(old,current.previous)
            current.collect_lifetimes();self.assertEqual(7,current.previous['emoteFailureOwnerVersion'])
            self.assertEqual(rows,current.originals.restore(current.state['manifests'],2)[:1])


if __name__=='__main__':unittest.main()
