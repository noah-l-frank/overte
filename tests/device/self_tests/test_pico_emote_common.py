"""Same actual Parent2/Input/Effect owners; explicit Qt/Rig/time leaf models.

These short components do not exercise remote Actor images, warm capture,
background, global stream capacity or final whole-feature retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import signature
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_common import PicoEmoteCommon
from adapters.pico4.emote_native_cycle import create
from adapters.script_journey.history import canonical
from self_tests.test_pico_emote_native_cycle import CycleBoundary

RETAINED=[]


class CommonTests(unittest.TestCase):
    def setUp(self):
        original=tempfile.TemporaryDirectory
        self.temporaries=[]
        def retained(*args,**kwargs):
            value=original(*args,**kwargs)
            value._finalizer.detach();value.cleanup=lambda:None
            self.temporaries.append(value);return value
        # Retention is selected before original registered cleanup and before
        # any input. The actual model.close still closes its original owners.
        with patch('self_tests.test_pico_emote_sources.tempfile.TemporaryDirectory',retained):
            self.model=CycleBoundary()
        self.addCleanup(self.finalize)
        print('Retained Common component originals:',self.model.s.root,flush=True)

    def finalize(self):
        root=self.model.s.root
        def inventory():return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            physical=signature(path.stat())) for path in root.rglob('*') if path.is_file()}
        before=inventory();self.model.close();after=inventory()
        self.assertEqual(before,after);self.assertTrue(root.is_dir())
        RETAINED.append(dict(root=str(root),files=after,originalModelCloseCalled=True))

    def prepared(self):
        m=self.model;common=PicoEmoteCommon()
        owner=create(m.adapter,'explicit-model',m.s.phase,m.s.root,m.s.lock,common=common)
        m.hosts.append(owner);owner.baseline();return owner,common

    def open(self,owner):
        call=self.model.input.call('open');self.assertEqual(dict(performed=True),owner.act(call))
        self.assertTrue(owner.observe()['state']['panel'])

    def test_once_act_pending_natural_restore_then_next_actual_play(self):
        m=self.model
        with m.s.lock.held():
            owner,common=self.prepared();self.open(owner)
            owner.act(m.input.call('play',{'name':'Crying'}));first=owner.observe()
            self.assertEqual('Crying',first['state']['animation'])
            wait=m.input.call('wait-complete');delivered=(list(m.input.inputs),list(m.input.controllers))
            self.assertEqual(dict(performed=True),owner.act(wait))
            pending=owner.observe();self.assertEqual(1,pending['picoEmotePendingRestoreVersion'])
            self.assertTrue(pending['state']['override'])
            self.assertEqual(delivered,(m.input.inputs,m.input.controllers))
            m.tick(2200);m.restore() # Explicit original Rig/timer model, no adapter effect setter.
            restored=owner.observe();self.assertEqual('restoration',restored['kind'])
            self.assertFalse(restored['state']['override']);self.assertFalse(restored['state']['restoredBeforeNominalEnd'])
            self.assertEqual(wait,restored['call']);self.assertEqual(delivered,(m.input.inputs,m.input.controllers))
            owner.act(m.input.call('play',{'name':'Surprised'}));second=owner.observe()
            self.assertEqual('Surprised',second['state']['animation']);self.assertEqual(4,len(owner.state['steps']))
            self.assertEqual(second['playbackReference'],common.state['played'])
            owner.validate();self.assertEqual(2,owner.identity['picoEmoteNativeCycleVersion'])
            self.assertFalse(common.finished())
            before=(list(m.s.calls),list(m.input.inputs),list(m.input.controllers))
            with self.assertRaises(NativeUIError):owner.cleanup(sleep=m.sleep)
            self.assertEqual(before,(m.s.calls,m.input.inputs,m.input.controllers))

    def test_handled_ignored_play_cannot_become_effect_or_allow_next_input(self):
        m=self.model
        with m.s.lock.held():
            owner,common=self.prepared();self.open(owner);m.ignore=True
            owner.act(m.input.call('play',{'name':'Crying'}))
            with self.assertRaises(NativeUIError):owner.observe()
            self.assertIsNone(owner.state['steps'][-1]['latest'])
            before=(list(m.input.inputs),list(m.input.controllers))
            with self.assertRaises(NativeUIError):owner.act(m.input.call('wait-complete'))
            self.assertEqual(before,(m.input.inputs,m.input.controllers))
            self.assertEqual('ready',common.store.read()['phase'])

    def test_actual_ack_then_unknown_parent_cas_retains_child_and_zero_resend(self):
        m=self.model
        with m.s.lock.held():
            owner,common=self.prepared();write=owner.file.write
            def lost(value,previous):
                if value['state']['phase']=='ready' and value['state']['steps']:
                    write(value,previous);raise NativeUIError('Actual Parent CAS reply lost after readback')
                return write(value,previous)
            owner.file.write=lost;call=m.input.call('open')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual(['tablet.open'],m.input.controllers)
            self.assertEqual('input-handled',common.records[-1]['kind'])
            self.assertIsNotNone(common.store.read());self.assertTrue(owner.failed);self.assertTrue(common.failed)
            before=(list(m.s.calls),list(m.input.inputs),list(m.input.controllers))
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual(before,(m.s.calls,m.input.inputs,m.input.controllers))

    def test_original_parent_expiry_after_issued_intent_sends_zero_input(self):
        m=self.model
        with m.s.lock.held():
            owner,common=self.prepared();guard=owner.source.guard;expired=[]
            def delayed():
                value=guard()
                durable=owner.store.read()
                if durable is not None and durable['state']['phase']=='input-issued' and not expired:
                    expired.append(True);m.tick(120001)
                return value
            owner.source.guard=delayed
            with self.assertRaises(NativeUIError):owner.act(m.input.call('open'))
            self.assertEqual([True],expired);self.assertEqual([],m.input.inputs);self.assertEqual([],m.input.controllers)
            self.assertEqual('input-issued',owner.store.read()['state']['phase'])
            self.assertEqual('input-issued',common.records[-1]['kind']);self.assertIsNone(m.input.store.read())

    def test_foreign_run_cursor_mutation_and_identical_child_replacement_refuse_without_delivery(self):
        m=self.model
        with m.s.lock.held():
            owner,common=self.prepared();call=m.input.call('open');foreign=deepcopy(call);foreign['runId']='a'*32
            before=(owner.store.path.read_bytes(),list(m.input.inputs),list(m.input.controllers))
            with self.assertRaises((ValueError,NativeUIError)):owner.act(foreign)
            self.assertEqual(before,(owner.store.path.read_bytes(),m.input.inputs,m.input.controllers))
            common.state['cursor']['index']=1
            with self.assertRaises(NativeUIError):owner.act(call)
            common.state['cursor']['index']=0
            raw=common.store.path.read_bytes() if common.store.path.exists() else None
            # Baseline has no ordinary Common child yet. Create a genuine child
            # through Open first; never fabricate its initial durable bytes.
            self.assertIsNone(raw);owner.act(call);raw=common.store.path.read_bytes()
            replacement=common.store.path.with_name('owned-identical-replacement')
            replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(common.store.path)
            before=(list(m.s.calls),list(m.input.inputs),list(m.input.controllers))
            with self.assertRaises(NativeUIError):owner.observe()
            self.assertEqual(before,(m.s.calls,m.input.inputs,m.input.controllers))

    def test_plan_and_declared_digest_replacement_cannot_rebind_original_parent_policy(self):
        m=self.model
        with m.s.lock.held():
            owner,common=self.prepared();original=owner.store.path.read_bytes()
            common.plan['prefix'][0]=dict(verb='play',inputs=dict(name='Crying'))
            common.plan_bytes=canonical(common.plan);common.plan_sha=hashlib.sha256(common.plan_bytes).hexdigest()
            before=(list(m.s.calls),list(m.input.inputs),list(m.input.controllers))
            with self.assertRaises(NativeUIError):owner.act(m.input.call('play',{'name':'Crying'}))
            self.assertEqual(before,(m.s.calls,m.input.inputs,m.input.controllers))
            self.assertEqual(original,owner.store.path.read_bytes());self.assertIsNone(common.previous)

    def test_cursor_and_declared_bytes_replacement_cannot_reseal_actual_durable_child(self):
        m=self.model
        with m.s.lock.held():
            owner,common=self.prepared();self.open(owner)
            original=(owner.store.path.read_bytes(),common.store.path.read_bytes())
            common.state['cursor']['index']=3;common.state_bytes=canonical(common.state)
            before=(list(m.s.calls),list(m.input.inputs),list(m.input.controllers))
            with self.assertRaises(NativeUIError):owner.act(m.input.call('play',{'name':'Surprised'}))
            self.assertEqual(before,(m.s.calls,m.input.inputs,m.input.controllers))
            self.assertEqual(original,(owner.store.path.read_bytes(),common.store.path.read_bytes()))

    def test_original_parent_clock_fields_cannot_be_renewed_before_native_bookends(self):
        m=self.model
        with m.s.lock.held():
            owner,common=self.prepared();original=owner.store.path.read_bytes()
            owner.state['started']+=120;owner.state['epochMs']+=120000;owner.state['hostEpochMs']+=120000
            before=(list(m.s.calls),list(m.input.inputs),list(m.input.controllers))
            with self.assertRaises(NativeUIError):owner.act(m.input.call('open'))
            self.assertEqual(before,(m.s.calls,m.input.inputs,m.input.controllers))
            self.assertEqual(original,owner.store.path.read_bytes());self.assertIsNone(common.previous)


if __name__=='__main__':unittest.main()
