"""Original Qt boundary model; actual Python codec/private input transport.

No Qt, UIKit, native compiler or device is exercised by these host cases.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import lifecycle_fields as source,normal_input
from ios.self_tests.test_ios_normal_input import Boundary


class Census:
    def __init__(self,epoch=None):
        self.epoch=int(time.time()*1000)-100 if epoch is None else epoch;self.tick=0;self.sequence=0
        self.instance=uuid.uuid4().hex;self.objects=[];self.fields=[];self.pending=[]
        self.loader=self.object('loader');self.window=self.object('window');self.root=self.object('root')
        self.loaders=[dict(loaderId=self.loader,rootId=self.root,windowId=self.window,loadGeneration=1,sourceSha256='a'*64)]
    def clock(self):
        self.tick+=1;return dict(epochMs=self.epoch+self.tick,monotonicMs=self.tick)
    def object(self,kind):
        oid=uuid.uuid4().hex;self.objects.append(dict(id=oid,kind=kind,born=self.clock(),alive=True,expired=None));return oid
    def load(self,editor,*,advance=True,focused=True):
        for row in self.fields:
            if row['current'] is not None:row['current'].update(attached=False,visible=False,focused=False)
        loader=self.loaders[0]
        if advance:loader['loadGeneration']+=1
        original=dict(editor=editor,componentSource='file:///installed'+source.PATHS[editor],fieldName=source.NAMES[editor],
            loaderId=self.loader,windowId=self.window,rootId=self.object('root'),fieldId=self.object('field'),
            contextId=self.object('context'),loadGeneration=loader['loadGeneration'])
        loader['rootId']=original['rootId'];loader['sourceSha256']=hashlib.sha256(original['componentSource'].encode()).hexdigest()
        current=dict(identity=original,attached=True,visible=True,focused=focused,enabled=True,readOnly=False,
            textOwned=True,text='',textSha256=hashlib.sha256(b'').hexdigest(),textCodeUnits=0)
        self.fields.append(dict(identity=original,current=current));return current
    def packet(self):
        self.sequence+=1;before=self.clock()
        return deepcopy(dict(iosLifecycleFieldsVersion=1,instance=self.instance,sequence=self.sequence,processId=42,
            complete=True,clockBefore=before,clockAfter=self.clock(),objects=self.objects,fields=self.fields,loaders=self.loaders,
            pendingBindings=self.pending))


class FieldBoundary(Boundary):
    def __init__(self,editor='create'):
        super().__init__(field=next(key for key,value in source.IDS.items() if value==editor))
        self.census=Census();self.census.load(editor);self.change=None;self.intent=None;self.lost=False
    def observed(self):
        value=super().observed();packet=self.census.packet()
        value.update(tabletShown=True,lifecycleFieldsVersion=1,lifecycleFieldInventory=packet)
        value['controls'][0]['lifecycleField']=deepcopy(packet['fields'][-1]['current'])
        if self.change:self.change(value)
        return value
    def post(self,request,timeout):
        import json
        command=json.loads(request.data)
        if command['operation']=='edit':assert self.intent.read()==command['input']
        returned=super().post(request,timeout)
        if command['operation']=='edit':
            self.receipt['status']['sampleEpochMs']=int(self.receipt['status']['sampleEpochMs'])
            if self.lost:raise OSError('Declared lost IME return')
        return returned


class LifecycleFieldSourceTests(unittest.TestCase):
    def test_alias_requires_actual_loader_advance_and_new_field_root_context(self):
        c=Census();before=c.packet()
        for editor,generation in (('create',1),('chat',2),('scripts',3),('scripts',4)):
            c.load(editor,focused=generation!=4);after=c.packet()
            alias=source.alias_transition(before,after,editor,generation)
            self.assertEqual(generation,alias['generation']);self.assertEqual(c.fields[-1]['identity'],alias['identity'])
            before=after
        self.assertEqual(4,len(c.fields));self.assertFalse(source.active(after)['focused'])

    def test_first_observation_of_old_field_or_unadvanced_loader_cannot_prove_creation(self):
        c=Census();c.load('create');before=c.packet();after=c.packet()
        with self.assertRaises(NativeUIError):source.alias_transition(before,after,'create',1)
        c=Census();before=c.packet();c.load('create',advance=False);after=c.packet()
        with self.assertRaises(NativeUIError):source.alias_transition(before,after,'create',1)

    def test_async_loader_completion_can_add_its_root_once_without_reloading(self):
        c=Census();c.loaders[0].update(rootId=None,loadGeneration=2,sourceSha256=hashlib.sha256(('file:///installed'+source.PATHS['scripts']).encode()).hexdigest());before=c.packet()
        c.load('scripts',advance=False);after=c.packet();source.validate(after,pid=42,previous=before)
        # A root observed only after load started cannot borrow that baseline
        # as proof of a new load. The operation must retain its earlier barrier.
        with self.assertRaises(NativeUIError):source.alias_transition(before,after,'scripts',3)
        c.load('scripts',advance=False)
        with self.assertRaises(NativeUIError):source.validate(c.packet(),pid=42,previous=after)

    def test_unattached_old_live_context_does_not_borrow_new_page_alias_or_imply_death(self):
        c=Census();c.load('scripts');before=c.packet();c.load('scripts',focused=False);after=c.packet()
        alias=source.alias_transition(before,after,'scripts',4)
        self.assertNotEqual(before['fields'][0]['identity']['fieldId'],alias['identity']['fieldId'])
        self.assertFalse(after['fields'][0]['current']['attached'])
        self.assertTrue(all(row['alive'] for row in after['objects']))
        self.assertEqual(alias['identity'],source.active(after)['identity'])

    def test_mutated_or_resurrected_history_foreign_pid_clocks_and_rebound_loader_refuse(self):
        c=Census();c.load('create');before=c.packet();after=c.packet()
        for mutate in (lambda v:v.update(processId=43),lambda v:v.update(iosLifecycleFieldsVersion=True),
            lambda v:v['objects'][0].update(born=dict(epochMs=1,monotonicMs=0)),
            lambda v:v['fields'][0]['identity'].update(loadGeneration=9),
            lambda v:v['loaders'][0].update(rootId=c.root),
            lambda v:v['clockAfter'].update(monotonicMs=0),lambda v:v['objects'].pop()):
            value=deepcopy(after);mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.validate(value,pid=42,previous=before)
        c.fields[0]['current']=None
        for row in c.objects:
            if row['kind']=='field':row.update(alive=False,expired=c.clock())
        dead=c.packet();source.validate(dead,pid=42,previous=before)
        revived=deepcopy(dead);revived['sequence']+=1
        for row in revived['objects']:
            if row['kind']=='field':row.update(alive=True,expired=None)
        with self.assertRaises(NativeUIError):source.validate(revived,pid=42,previous=dead)

    def test_private_unowned_text_is_not_exposed_or_adopted(self):
        c=Census();current=c.load('chat');current.update(textOwned=False,text=None,textCodeUnits=14,textSha256='b'*64)
        value=c.packet();source.validate(value,pid=42)
        self.assertIsNone(source.active(value)['text'])
        current.update(textOwned=True,text='Private message')
        with self.assertRaises(NativeUIError):source.validate(c.packet(),pid=42)

    def test_incomplete_or_two_visible_editors_cannot_qualify_current_context(self):
        c=Census();c.load('create');c.load('chat');value=c.packet();value['complete']=False
        with self.assertRaises(NativeUIError):source.active(value)
        value['complete']=True;value['fields'][0]['current']['visible']=True
        value['fields'][0]['current']['attached']=True
        with self.assertRaises(NativeUIError):source.active(value)


class LifecycleFieldInputTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.b=FieldBoundary();self.b.intent=PrivateFeatureState(Path(temp.name)/'input.json')
        self.native=self.b.input();self.enterContext(patch.object(normal_input,'urlopen',self.b.post))
    def reference(self):return source.reference(self.native.capture(),self.b.field)
    def intent(self,command):self.b.intent.write(command,None)
    def inputs(self):return [row for row in self.b.requests if row['operation']=='edit']

    def test_unicode_ime_uses_exact_original_token_and_durable_intent_once(self):
        original=self.reference();text='Overte ä Ω 東京 '+'a'*32
        result=self.native.lifecycle_input(self.b.field,'replace',reference=original,text=text,before_send=self.intent)
        self.assertEqual({'performed':True},result);self.assertEqual(1,len(self.inputs()))
        command=self.b.intent.read();self.assertEqual(text,command['text'])
        self.assertEqual(original['control']['token'],command['fieldToken'])
        self.assertNotIn('generation',result);self.assertNotIn('text',result)

    def test_missing_or_refused_intent_never_dispatches(self):
        original=self.reference()
        for callback in (None,lambda command:False):
            with self.subTest(callback=callback),self.assertRaises(NativeUIError):
                self.native.lifecycle_input(self.b.field,'activate',reference=original,before_send=callback)
        self.assertEqual([],self.inputs())

    def test_replaced_context_or_foreign_draft_cannot_deliver_to_new_field(self):
        original=self.reference();self.b.census.load('create')
        with self.assertRaises(NativeUIError):
            self.native.lifecycle_input(self.b.field,'replace',reference=original,text='Overte ä Ω 東京 '+'a'*32,before_send=self.intent)
        self.assertIsNone(self.b.intent.read());self.assertEqual([],self.inputs())
        original=self.reference()
        for text in ('reply-'+'a'*32,'expected text','Overte ä Ω 東京 '+'A'*32):
            with self.subTest(text=text),self.assertRaises(NativeUIError):
                self.native.lifecycle_input(self.b.field,'replace',reference=original,text=text,before_send=self.intent)
        self.assertEqual([],self.inputs())

    def test_lost_or_ignored_return_keeps_original_intent_without_retry(self):
        original=self.reference();self.b.lost=True
        with self.assertRaises(OSError):self.native.lifecycle_input(self.b.field,'activate',reference=original,before_send=self.intent)
        saved=self.b.intent.read();self.b.lost=False;self.native.capture()
        self.assertEqual(saved,self.b.intent.read());self.assertEqual(1,len(self.inputs()))

    def test_control_cannot_disagree_with_its_actual_inventory(self):
        original=self.b.observed()
        for mutate in (lambda v:v.pop('lifecycleFieldsVersion'),lambda v:v.update(lifecycleFieldsVersion=True),
            lambda v:v['controls'][0]['lifecycleField'].update(focused=False),
            lambda v:v['controls'][0]['lifecycleField']['identity'].update(fieldId=uuid.uuid4().hex),
            lambda v:v['controls'][0].update(expectedText='acknowledged')):
            value=deepcopy(original);mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):normal_input.observation(value,42)

    def test_actual_reader_preserves_original_census_and_refuses_rewritten_or_missing_history(self):
        self.native.capture();original=deepcopy(self.native.lifecycle_fields_previous)
        for mutate in (lambda v:v['lifecycleFieldInventory']['objects'][0].update(born=dict(epochMs=1,monotonicMs=0)),
            lambda v:v['lifecycleFieldInventory'].update(instance=uuid.uuid4().hex),
            lambda v:(v.pop('lifecycleFieldsVersion'),v.pop('lifecycleFieldInventory'))):
            self.b.change=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):self.native.capture()
            self.assertEqual(original,self.native.lifecycle_fields_previous)
        self.assertEqual([],self.inputs())


class LifecyclePendingJoinTests(unittest.TestCase):
    def setUp(self):
        from self_tests.test_pending_commit_owner import Boundary as PendingBoundary,RUN
        from adapters.pending_commit_owner import NativePendingCommitOwner
        self.run=RUN;self.c=Census(epoch=19000);self.field=self.c.load('scripts',focused=False);self.p=PendingBoundary()
        # Declared native producer identities and exact configured component URL.
        self.field['identity']['componentSource']='qrc:/qml/hifi/dialogs/TabletRunningScripts.qml'
        def producer(value):
            value['processId']=42
            if value['commit']:value['commit']['observation']['processId']=42
        self.p.edit=producer
        self.owner=NativePendingCommitOwner(self.p.send,self.p.original,self.p.epoch,lambda:True,42,
            intent=self.p.intents.append,monotonic=lambda:self.p.clock,sleep=self.p.sleep)
        self.c.pending.append(dict(token=self.p.token,identity=deepcopy(self.field['identity'])))
    def joined(self):
        self.c.tick=1001+round(self.p.clock*1000)
        fields=self.c.packet();pending=deepcopy(self.owner.last)
        return fields,pending,self.p.commands[-1]

    def test_actual_pending_token_maps_original_context_and_separate_replacement(self):
        self.owner.focus(self.run);self.owner.type_owned(self.run);held=self.owner.hold(self.run)
        self.field.update(focused=True,text='retry-'+self.run,textSha256=hashlib.sha256(('retry-'+self.run).encode()).hexdigest(),textCodeUnits=38)
        fields,pending,query=self.joined();joined=source.join_pending(fields,pending,query)
        self.assertEqual(joined['current'],joined['held']);original=deepcopy(joined['held'])
        self.p.replace_context();self.p.clock=.1;self.c.tick=1006
        field=self.c.load('scripts',focused=False);field['identity']['componentSource']=self.field['identity']['componentSource']
        self.c.pending.append(dict(token=self.p.token,identity=deepcopy(field['identity'])))
        self.owner.attempt_retired(self.run,held['commit']['observation']['eventId'])
        fields,pending,query=self.joined();after=source.join_pending(fields,pending,query)
        self.assertEqual(original,after['held']);self.assertNotEqual(after['current'],after['held'])
        self.assertEqual('context-retired',after['commit']['observation']['events'][-1]['reason'])
        self.assertEqual([],after['resources']['pendingRuns'])

    def test_matching_text_and_source_without_original_native_token_relation_is_insufficient(self):
        self.owner.read(self.run);fields,pending,query=self.joined()
        for mutate in (lambda v:v.update(pendingBindings=[]),
            lambda v:v['pendingBindings'][0].update(token=uuid.uuid4().hex)):
            value=deepcopy(fields);mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.join_pending(value,pending,query)

    def test_native_token_relation_is_immutable_and_cannot_be_rebound_to_new_field(self):
        self.owner.read(self.run);before,_,_=self.joined();self.c.tick=1005;self.c.load('scripts')
        self.c.pending[0]['identity']=deepcopy(self.c.fields[-1]['identity']);after=self.c.packet()
        with self.assertRaises(NativeUIError):source.validate(after,pid=42,previous=before)

    def test_token_for_an_already_destroyed_context_cannot_claim_later_capture(self):
        self.owner.focus(self.run);self.owner.type_owned(self.run);held=self.owner.hold(self.run)
        original=deepcopy(self.field['identity']);self.p.replace_context();self.p.clock=.1;self.c.tick=1006
        new=self.c.load('scripts',focused=False);new['identity']['componentSource']=original['componentSource']
        self.c.pending.append(dict(token=self.p.token,identity=deepcopy(new['identity'])))
        self.owner.attempt_retired(self.run,held['commit']['observation']['eventId'])
        self.c.fields[0]['current']=None
        for row in self.c.objects:
            if row['id']==original['contextId']:
                row.update(alive=False,expired=dict(epochMs=19999,monotonicMs=999))
        fields,pending,query=self.joined();source.validate(fields,pid=42)
        with self.assertRaises(NativeUIError):source.join_pending(fields,pending,query)

    def test_late_observed_identity_or_disagreeing_current_state_cannot_join(self):
        self.owner.read(self.run);fields,pending,query=self.joined()
        for mutate in (lambda v:v['objects'][-1]['born'].update(epochMs=20001,monotonicMs=1001),
            lambda v:v['fields'][0]['current'].update(focused=True),
            lambda v:v.update(complete=False)):
            value=deepcopy(fields);mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.join_pending(value,pending,query)
