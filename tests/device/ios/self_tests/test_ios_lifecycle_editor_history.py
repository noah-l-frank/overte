"""Durable history over actual canonical host transports, with Qt/OS modeled.

These cases exercise observation and archival logic. They do not claim normal
page navigation, actual IME delivery, native compilation or device acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import time
import unittest
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.lifecycle_editor_history import LifecycleEditorHistory
from ios.self_tests.test_ios_lifecycle_originals import LifecycleOriginalsTests
from ios.self_tests.test_ios_normal_input import Boundary


class LifecycleEditorHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=LifecycleOriginalsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture;self.c=self.f.c;self.tokens={}
        for row in self.c.fields:row['current']=None
        self.c.pending=[]
        def current():
            rows=[row['current'] for row in self.c.fields if row['current'] is not None
                  and row['current']['attached'] and row['current']['visible']]
            return rows[0] if rows else None
        self.current=current
        def observed():
            value=Boundary.observed(self.f.b);field=current()
            if field and field['identity']['editor']=='scripts':
                key=field['identity']['fieldId'];self.tokens.setdefault(key,uuid.uuid4().hex)
                self.f.p.boundary.token=self.tokens[key];self.f.p.boundary.text=field['text'];self.f.p.boundary.focused=field['focused']
            value.update(sampleEpochMs=self.f.stamp()['epochMs'],controls=[],tabletShown=field is not None,
                         lifecycleFieldsVersion=1,lifecycleFieldInventory=self.c.packet())
            return value
        def pending(value):
            value['processId']=42
            if value['commit']:value['commit']['observation']['processId']=42
            field=current()
            if field is None or field['identity']['editor']!='scripts':value['current']=dict(status='none')
            else:
                token=value['current']['token']
                if not any(row['token']==token for row in self.c.pending):self.c.pending.append(dict(token=token,identity=deepcopy(field['identity'])))
        self.f.b.observed=observed;self.f.p.boundary.edit=pending
        self.source=self.f.source();root=self.f.f.adapter.state_path('test-only').parent
        self.store=PrivateFeatureState(root/'lifecycle-editor-owner.json');self.lock=ScriptSourceLock(root/'script-feature-sources.lock')
        self.enterContext(self.lock.held());self.history=self.owner()
    def owner(self):return LifecycleEditorHistory(self.store,self.source.binding,self.source.run,self.lock,self.source.source['check'])
    def sample(self):return self.history.append(self.source.sample(time.time()*1000))
    def load(self,editor,*,focused=True):
        field=self.c.load(editor,focused=focused)
        if editor=='scripts':field['identity']['componentSource']='qrc:/qml/hifi/dialogs/TabletRunningScripts.qml'
        self.f.p.k.b.notify('did-show' if focused else 'did-hide',valid=focused,intersects=focused)
        return field

    def test_original_generations_survive_restore_without_new_queries_or_resetting_history(self):
        initial=self.sample();self.history.baseline();before=initial
        for generation,editor in enumerate(('create','chat','scripts'),1):
            self.load(editor);after=self.sample();alias=self.history.qualify(before,after)
            self.assertEqual(generation,alias['generation']);self.assertEqual(generation,self.history.historical_editor(after)['generation']);before=after
        self.c.fields[-1]['current']=None;self.f.p.k.b.notify('did-hide',valid=False)
        closed=self.sample();projection=self.history.historical_editor(closed)
        self.assertEqual(dict(editor='none',text='',focused=False,generation=0,keyboard=False),projection)
        count=(len(self.f.b.requests),len(self.f.p.boundary.commands));saved=deepcopy(self.history.state)
        restored=self.owner();self.assertEqual(saved,restored.state);self.assertEqual(count,(len(self.f.b.requests),len(self.f.p.boundary.commands)))
        self.assertEqual(3,len(restored.state['aliases']));self.assertEqual(0,restored.historical_editor(closed)['generation'])

    def test_unqualified_observation_or_acknowledgment_does_not_assign_a_generation(self):
        self.sample();self.history.baseline();self.load('chat');after=self.sample()
        with self.assertRaises(NativeUIError):self.history.qualify(1,after)
        self.assertEqual([],self.history.state['aliases'])
        with self.assertRaises(NativeUIError):self.history.historical_editor(after)
        self.assertEqual([],self.owner().state['aliases'])

    def test_fourth_context_keeps_the_actual_held_event_bound_to_third_context(self):
        before=self.sample();self.history.baseline()
        for editor in ('create','chat','scripts'):
            self.load(editor);after=self.sample();self.history.qualify(before,after);before=after
        # Explicit Qt boundary state for the separately tested IME recipe.
        # This test executes observation/holder/archive integration, not Qt input.
        text='retry-'+self.source.run;self.current().update(text=text,textSha256=hashlib.sha256(text.encode()).hexdigest(),textCodeUnits=len(text))
        self.sample()
        intent=PrivateFeatureState(self.store.path.with_name('lifecycle-pending-test-intent.json'))
        self.source.pending.intent=lambda command:intent.write(command,intent.read())
        held=self.source.pending.hold(self.source.run);event=held['commit']['observation']['eventId']
        before=self.sample();self.load('scripts',focused=False);after=self.sample()
        alias=self.history.qualify(before,after);self.assertEqual(4,alias['generation'])
        self.assertEqual('hold',intent.read()['operation'])
        self.source.pending.attempt_retired(self.source.run,event);terminal=self.sample()
        restored=self.owner();self.assertEqual(4,restored.historical_editor(terminal)['generation'])
        original=restored.read(terminal)['originals']['pending']['commit']['observation']
        self.assertEqual(event,original['eventId']);self.assertEqual('context-retired',original['events'][-1]['reason'])
        self.assertFalse(original['pending']);self.assertEqual('attempt',intent.read()['operation'])

    def test_first_seen_existing_field_and_changed_original_inode_do_not_qualify(self):
        self.sample();self.history.baseline();self.load('create');before=self.sample();after=self.sample()
        with self.assertRaises(NativeUIError):self.history.qualify(before,after)
        ref=self.history.state['frames'][0];path=self.history.files.path(self.history.files.expand(ref));raw=path.read_bytes()
        temporary=path.with_name('replacement-original.json');temporary.write_bytes(raw);temporary.chmod(0o600);temporary.replace(path)
        with self.assertRaises(NativeUIError):self.owner()

    def test_saved_original_parent_append_recovers_once_without_requery(self):
        value=self.source.sample(time.time()*1000);ref=self.history.files.write(1,value)
        self.assertEqual('saved',self.history.state['original']['phase']);self.assertEqual([],self.history.state['frames'])
        count=len(self.f.b.requests);restored=self.owner();self.assertEqual(1,restored.recover_original());self.assertEqual(ref,restored.state['frames'][0])
        self.assertEqual(count,len(self.f.b.requests))
        with self.assertRaises(NativeUIError):restored.recover_original()
        self.assertEqual(1,len(self.owner().state['frames']))

    def test_foreign_file_or_cas_change_blocks_owner_without_discarding_evidence(self):
        self.sample();self.history.baseline();saved=deepcopy(self.store.read())
        foreign=self.store.path.with_name('lifecycle-editor-foreign.json');PrivateFeatureState(foreign).write({'unowned':True},None)
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(saved,self.store.read());self.assertTrue(foreign.exists())
