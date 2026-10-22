"""Run cleanup retains failed sources through real private bounded archives."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_run
from test_emote_sources import RUN
from overte_phone_emote_failures import PhoneEmoteFailures
from overte_phone_script_history import unpack
from adapters.normal_ui import NativeUIError


class EmoteFailureOwnerTests(unittest.TestCase):
    setUp=test_emote_run.EmoteRunTests.setUp
    owner=test_emote_run.EmoteRunTests.owner
    prepared=test_emote_run.EmoteRunTests.prepared
    cleanup_phase=test_emote_run.EmoteRunTests.cleanup_phase

    def failed_source(self,run,role='primary'):
        m=self.model
        with run.lock.held():
            source=run.source(role);source.read();prefix=deepcopy(source.frames);m.admission_fault='old-probe'
            with self.assertRaises(NativeUIError):source.read()
            m.admission_fault=None;return prefix,deepcopy(source.previous)

    def cleaning(self,run):
        self.cleanup_phase()
        with run.lock.held():run.state.update(phase='cleaning-inputs',cleanupTicket='a'*32);run.save()

    def records(self,owner):return owner.originals.restore(owner.state['manifests'],owner.state['count'])

    def test_real_run_cleanup_transfers_both_pending_streams_before_ordinary_input_restoration(self):
        run=self.prepared();primary=self.failed_source(run);actor=self.failed_source(run,'actor');self.cleanup_phase()
        proof=run.cleanup_inputs(dict(contractVersion=17,runId=RUN));self.assertEqual(1,proof['emoteCleanupInputsVersion'])
        with run.lock.held():
            failures=PhoneEmoteFailures(run);rows=self.records(failures)
            self.assertEqual(2,len(rows));self.assertIsNone(failures.state['pending'])
            for row,(prefix,header),role in zip(rows,(primary,actor),('primary','actor')):
                self.assertEqual(role,row['archive']['header']['role']);self.assertEqual(header,row['archive']['header'])
                failures.record(row,row['index']);self.assertEqual('reading',unpack(header['payload'])[0]['phase'])
                self.assertEqual(prefix,run.source(role).frames[:len(prefix)])
            self.assertIsNotNone(failures.store.read());self.assertEqual('inputs-restored',run.state['phase'])

    def test_missing_or_partial_failure_archive_commits_resume_without_resetting_source_facts(self):
        for boundary in ('original-planned','original-opened','original-saved','manifest-planned','manifest-saved'):
            with self.subTest(boundary=boundary):
                self.setUp();m=self.model;run=self.prepared();prefix,header=self.failed_source(run);self.cleaning(run)
                with run.lock.held():
                    owner=PhoneEmoteFailures(run);intent=owner.originals.intent
                    def interrupt(kind,value):
                        intent(kind,value)
                        if kind+'-'+value['phase']==boundary:raise NativeUIError('Synthetic lost failure archive callback')
                    owner.originals.intent=interrupt
                    with self.assertRaises(NativeUIError):owner.collect_sources()
                    self.assertEqual(header,run.source().previous);calls=deepcopy(m.calls)
                    recovered=PhoneEmoteFailures(run);recovered.collect_sources();rows=self.records(recovered)
                    self.assertEqual(1,len(rows));self.assertEqual(header,rows[0]['archive']['header'])
                    self.assertEqual(prefix,run.source().frames);self.assertTrue(all(item=='phase-read' for item in m.calls[len(calls):]))
                    self.assertIsNone(recovered.state['pending']);self.assertEqual('ready',run.source().state['phase'])

    def test_lost_final_owner_commit_reuses_transferred_source_without_a_second_archive(self):
        m=self.model;run=self.prepared();prefix,header=self.failed_source(run);self.cleaning(run)
        with run.lock.held():
            owner=PhoneEmoteFailures(run);save=owner.save
            def fail_final():
                if owner.state['pending'] is None:raise NativeUIError('Synthetic lost enclosing completion')
                return save()
            with patch.object(owner,'save',side_effect=fail_final),self.assertRaises(NativeUIError):owner.collect_sources()
            self.assertEqual('ready',run.source().state['phase']);self.assertIsNotNone(PhoneEmoteFailures(run).state['pending'])
            recovered=PhoneEmoteFailures(run);recovered.collect_sources();rows=self.records(recovered)
            self.assertEqual(1,len(rows));self.assertEqual(header,rows[0]['archive']['header']);self.assertEqual(prefix,run.source().frames)
            recovered.collect_sources();self.assertEqual(1,recovered.state['count']);self.assertIsNone(recovered.state['pending'])

    def test_ignored_parent_intent_prevents_failure_retention_and_source_release(self):
        run=self.prepared();_prefix,header=self.failed_source(run);self.cleaning(run)
        with run.lock.held():
            owner=PhoneEmoteFailures(run)
            with patch.object(owner.store,'write',return_value=None),self.assertRaises(NativeUIError):owner.collect_sources()
            self.assertEqual(header,run.source().previous);self.assertEqual([],list(self.model.root.glob('emote-frame-source-failures-*.json')))
            self.assertIsNone(owner.store.read())

    def test_foreign_partial_failure_record_or_missing_saved_record_is_not_replaced_or_dropped(self):
        for fault in ('partial','missing'):
            with self.subTest(fault=fault):
                self.setUp();run=self.prepared();_prefix,header=self.failed_source(run);self.cleaning(run)
                with run.lock.held():
                    owner=PhoneEmoteFailures(run);intent=owner.originals.intent
                    def interrupt(kind,value):
                        intent(kind,value)
                        if kind=='original' and value['phase']==('opened' if fault=='partial' else 'saved'):
                            raise NativeUIError('Synthetic lost failure evidence return')
                    owner.originals.intent=interrupt
                    with self.assertRaises(NativeUIError):owner.collect_sources()
                    original=owner.state['pending']['original'];path=owner.originals.path(original)
                    if fault=='partial':path.write_bytes(b'Foreign prefix')
                    else:path.unlink()
                    recovered=PhoneEmoteFailures(run);control=deepcopy(recovered.previous)
                    with self.assertRaises((NativeUIError,FileNotFoundError)):recovered.collect_sources()
                    self.assertEqual(header,run.source().previous);self.assertEqual(control,recovered.store.read())
                    self.assertEqual(0,recovered.state['count'])


if __name__=='__main__':unittest.main()
