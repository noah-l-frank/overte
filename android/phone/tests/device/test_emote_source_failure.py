"""Actual private failed-read transfer over synthetic readonly boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_emote_sources import Originals,RUN
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import unpack


class EmoteSourceFailureTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-source-failure-');self.addCleanup(temporary.cleanup)
        self.model=m=Originals(Path(temporary.name));m.idle=True
        self.archive=PrivateFeatureState(m.root/'retained-source-failure.json')

    def pending(self,fault='dispatch',role='primary'):
        m=self.model;source=m.source(role);source.read();self.prefix=deepcopy(source.frames)
        intent=source.originals.intent
        def interrupt(kind,value):
            intent(kind,value)
            selected={'planned':('original','planned'),'opened':('original','opened'),
                'saved':('original','saved'),'manifest-planned':('manifest','planned'),'manifest-saved':('manifest','saved')}.get(fault)
            if selected==(kind,value['phase']):raise NativeUIError('Synthetic lost failed source callback')
        source.originals.intent=interrupt
        if fault=='dispatch':m.fault='lost-return'
        with self.assertRaises(NativeUIError):source.read()
        m.fault=None
        return m.source(role)

    def cleanup(self):self.model.journal.activate(RUN,'a'*32,'cleanup',{})

    def retain(self,value):
        source=self.model.source(value['header']['role'])
        self.assertEqual('reading',source.state['phase']);self.assertEqual(self.prefix,source.frames)
        self.archive.write(value,self.archive.read());self.assertEqual(value,self.archive.read())

    def test_each_readonly_failure_keeps_actual_originals_before_pending_is_transferred(self):
        for role in ('primary','actor'):
            for fault in ('dispatch','planned','opened','saved','manifest-planned','manifest-saved'):
                with self.subTest(role=role,fault=fault):
                    self.setUp();m=self.model
                    with m.lock.held():
                        source=self.pending(fault,role);header=deepcopy(source.previous);self.cleanup();calls=deepcopy(m.calls)
                        proof=source.transfer_failed(self.retain)
                        self.assertEqual(proof,self.archive.read());self.assertEqual(header,proof['header'])
                        self.assertEqual('reading',unpack(proof['header']['payload'])[0]['phase'])
                        self.assertEqual('ready',source.state['phase']);self.assertEqual(self.prefix,source.frames)
                        self.assertEqual(['phase-read','phase-read'],m.calls[len(calls):])
                        self.assertEqual(1,source.state['revision']);self.assertNotIn('state',proof);self.assertNotIn('cleaned',proof)
                        before=deepcopy(m.calls);self.assertEqual(proof,source.failure_archive(proof));self.assertEqual(before,m.calls)
                        current=source.read();self.assertGreater(current['group']['native']['sequence'],self.prefix[-1]['group']['native']['sequence'])
                        self.assertEqual(proof,source.failure_archive(proof))

    def test_normal_phase_and_rejected_or_lost_retention_cannot_reset_the_failed_source(self):
        for fault in ('normal','rejected','lost'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model
                with m.lock.held():
                    source=self.pending();header=deepcopy(source.previous)
                    if fault!='normal':self.cleanup()
                    def retain(value):
                        self.retain(value)
                        if fault=='lost':raise NativeUIError('Synthetic lost durable retention return')
                        return False
                    with self.assertRaises(NativeUIError):source.transfer_failed(retain)
                    self.assertEqual(header,source.store.read());self.assertEqual(self.prefix,source.frames)
                    if fault=='normal':self.assertIsNone(self.archive.read())
                    else:self.assertIsNotNone(self.archive.read())

    def test_lost_retention_reuses_exact_original_archive_and_never_redates_it(self):
        m=self.model
        with m.lock.held():
            source=self.pending('opened');self.cleanup()
            def lost(value):self.retain(value);raise NativeUIError('Synthetic callback return lost')
            with self.assertRaises(NativeUIError):source.transfer_failed(lost)
            original=self.archive.read();calls=deepcopy(m.calls);source=m.source()
            self.assertEqual(original,source.transfer_failed(lambda value:self.assertEqual(original,value),retained=original))
            self.assertEqual(['phase-read','phase-read'],m.calls[len(calls):])
            source=m.source();before=deepcopy(source.previous)
            self.assertEqual(original,source.transfer_failed(lambda value:self.assertEqual(original,value),retained=original))
            self.assertEqual(before,source.store.read());self.assertEqual(1,source.state['revision'])

    def test_partial_file_replacement_mutation_and_missing_saved_evidence_block_transfer(self):
        for fault in ('changed','missing','foreign'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model
                with m.lock.held():
                    source=self.pending('saved' if fault=='missing' else 'opened');self.cleanup();header=deepcopy(source.previous)
                    def retain(value):
                        self.retain(value);original=source.state['pending']['original'];path=source.originals.path(original)
                        if fault=='changed':path.write_bytes(b'changed')
                        elif fault=='missing':path.unlink()
                        else:
                            replacement=path.with_name('foreign.json');replacement.write_bytes(b'');replacement.chmod(0o600);replacement.replace(path)
                    with self.assertRaises((NativeUIError,FileNotFoundError)):source.transfer_failed(retain)
                    self.assertEqual(header,source.store.read());self.assertEqual('reading',source.state['phase'])

    def test_phase_change_slow_callback_and_ignored_commit_keep_failure_responsibility(self):
        for fault in ('phase','slow','commit'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model
                with m.lock.held():
                    source=self.pending();self.cleanup();header=deepcopy(source.previous)
                    def retain(value):
                        self.retain(value)
                        if fault=='phase':m.journal.activate(RUN,'b'*32,'open',{})
                        elif fault=='slow':m.clock+=5.1
                    if fault=='commit':
                        with patch.object(source.store,'write',return_value=None),self.assertRaises(NativeUIError):source.transfer_failed(retain)
                    else:
                        with self.assertRaises(NativeUIError):source.transfer_failed(retain)
                    self.assertEqual(header,source.store.read());self.assertEqual(self.prefix,m.source().frames)

    def test_foreign_retained_header_diagnostic_role_and_cleanup_cannot_adopt_this_transfer(self):
        m=self.model
        with m.lock.held():
            source=self.pending('opened');self.cleanup();proof=source.transfer_failed(self.retain);header=deepcopy(source.previous)
            for fault in ('role','diagnostic','cleanup','segment'):
                value=deepcopy(proof)
                if fault=='role':value['header']['role']='actor'
                elif fault=='diagnostic':value['originalDiagnostic']['bytes']=1
                elif fault=='cleanup':value['cleanup']['activations'][-1]['ticket']='f'*32
                else:value['segment']=1
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.transfer_failed(lambda _value:None,retained=value)
                self.assertEqual(header,source.store.read())


if __name__=='__main__':unittest.main()
