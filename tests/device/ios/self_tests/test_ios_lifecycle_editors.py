"""Normal editor composition over real host owners; Qt/OS/SDK are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
import unittest
import uuid
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,lifecycle_input_owner as field_owner,lifecycle_navigation_controls as navigation
from ios.adapters.lifecycle_editors import LifecycleEditors
from ios.adapters.lifecycle_input_owner import LifecycleInputOwner
from ios.adapters.lifecycle_navigation_owner import LifecycleNavigationOwner
from ios.adapters.lifecycle_editor_history import LifecycleEditorHistory
from ios.self_tests.test_ios_lifecycle_editor_history import LifecycleEditorHistoryTests
from ios.self_tests.test_ios_lifecycle_navigation import Native as NavigationEvents
from ios.self_tests.test_ios_lifecycle_inputs import Native as FieldEvents
from ios.self_tests.test_ios_tablet_back_controls import BackBoundary
from ios.adapters.tablet_back_controls import FIELDS as BACK_FIELDS
from ios.adapters.tablet_launcher_controls import FIELDS as LAUNCHER_FIELDS


class EditorDomain:
    def __init__(self,case):
        self.f=LifecycleEditorHistoryTests();self.f.setUp();case.addCleanup(self.f.doCleanups)
        self.route='closed';self.page=0;self.pages=1;self.tokens={};self.objects={};self.commands=[];self.effect_count=0
        self.ignore=None;self.lost=None;self.deferred=None;self.pending=None;self.menu_fallback=False
        self.nav=NavigationEvents(epoch_ms=lambda:20000+self.f.f.tick);self.field=FieldEvents(epoch_ms=lambda:20000+self.f.f.tick)
        self.nav.stamp=self.field.stamp=self.f.f.stamp
        self.back={key:value for key,value in BackBoundary().observed()['controls'][0].items() if key in BACK_FIELDS}
        self.b=self.f.f.b;self.source=self.f.source;self.native=self.source.source['native'];self.lock=self.f.lock
        self.b.observed=self.observed
        case.enterContext(patch.object(normal_input,'urlopen',self.post))
        self.root=self.f.store.path.parent;self.flow=self.reopen()

    def token(self,key):return self.tokens.setdefault(key,str(uuid.uuid4()))
    def object(self,key):return self.objects.setdefault(key,uuid.uuid4().hex)
    def current(self):return self.f.current()
    def row(self,control,**extra):
        return dict(id=control,token=self.token(control),enabled=True,focused=False,frame=dict(x=10,y=20,width=200,height=48),**extra)

    def observed(self):
        self.f.f.stamp();field=self.current();rows=[];extra={}
        if field and field['identity']['editor']=='scripts':
            key=field['identity']['fieldId'];self.f.tokens.setdefault(key,uuid.uuid4().hex)
            self.f.f.p.boundary.token=self.f.tokens[key];self.f.f.p.boundary.text=field['text'];self.f.f.p.boundary.focused=field['focused']
        if self.route=='closed':rows.append(self.row('hud.tablet'))
        elif self.route=='launcher':
            extra.update(tabletLauncherControlsVersion=1,createControlsVersion=1,createGeneration=self.token('create-generation'),
                chatControlsVersion=1,chatGeneration=self.token('chat-generation'),featureControlsVersion=1)
            selected=dict(tabletLauncherControlVersion=1,launcherRootId=self.token('launcher-root'),
                launcherQmlSource='qrc:/qml/hifi/tablet/TabletHome.qml',launcherCurrentIndex=self.page,launcherPageCount=self.pages,inputReady=True)
            rows.append(self.row('snapshot.entry',**selected,launcherControlIndex=-1))
            for index in range(self.pages if self.pages>1 else 0):rows.append(self.row('tablet.page.'+str(index+1),**selected,launcherControlIndex=index))
            if self.page==self.pages-1:
                rows.extend([self.row('create.entry',inputReady=True),self.row('chat.entry',inputReady=True),
                    self.row('scripts.menu' if self.menu_fallback else 'scripts.entry')])
            rows.append(self.row('tablet.close'))
        elif self.route in ('menu','menu-edit'):
            extra['featureControlsVersion']=1;rows.append(self.row('scripts.menu-edit' if self.route=='menu' else 'scripts.menu-running'))
            rows.append(self.row('tablet.home'))
        else:
            need(field is not None);editor=field['identity']['editor'];control={'create':'lifecycle.create.text','chat':'chat.input','scripts':'lifecycle.scripts.filter'}[editor]
            actual=self.row(control);actual['focused']=field['focused']
            if editor=='chat':
                extra.update(chatControlsVersion=1,chatGeneration=self.token('chat-generation'))
                actual.update(inputReady=True,text=field['text'])
            else:actual['lifecycleField']=deepcopy(field)
            rows.extend([actual,self.row('tablet.back',**self.back),self.row('tablet.home')]);extra['tabletBackControlsVersion']=1
        nav=[]
        for row in rows:
            if row['id'] not in navigation.IDS:continue
            nav.append(dict(controlId=row['id'],token=row['token'],controlObject=self.object(row['id']),windowObject=self.object('window'),
                containerObject=self.object('hud' if row['id']=='hud.tablet' else 'tablet'),contextObject=self.object('context-'+self.route),
                qmlSource='qrc:/qml/hifi/tablet/TabletHome.qml',surface='hud' if row['id']=='hud.tablet' else 'tablet',inputReady=True))
        return dict(schemaVersion=1,instance=self.b.instance,frameSpace='qt-window-logical',processId=42,sampleEpochMs=self.f.f.stamp()['epochMs'],
            elapsedMs=self.f.f.tick,lastSequence=self.b.sequence,tabletShown=self.route!='closed',ready=True,controls=rows,
            lifecycleFieldsVersion=1,lifecycleFieldInventory=self.f.c.packet(),
            lifecycleNavigation=dict(iosLifecycleNavigationVersion=1,complete=True,controls=nav),**extra)

    def apply(self,control,command):
        self.effect_count+=1
        if control=='hud.tablet':self.route='launcher'
        elif control=='tablet.home' or control=='tablet.back':
            for row in self.f.c.fields:
                if row['current'] is not None:row['current'].update(attached=False,visible=False,focused=False)
            self.route='launcher';self.f.f.p.k.b.notify('did-hide',valid=False)
        elif control.startswith('tablet.page.'):self.page=int(control.rsplit('.',1)[1])-1
        elif control=='scripts.menu':self.route='menu'
        elif control=='scripts.menu-edit':self.route='menu-edit'
        elif control in ('create.entry','chat.entry','scripts.entry','scripts.menu-running'):
            editor='scripts' if control=='scripts.menu-running' else control.split('.')[0]
            self.f.load(editor,focused=False);self.route=editor
        elif command['operation']=='activate':
            self.current()['focused']=True;self.f.f.p.k.b.notify('did-show',valid=True,intersects=True)
        else:
            text=command['text'];self.current().update(text=text,textOwned=True,textSha256=hashlib.sha256(text.encode()).hexdigest(),textCodeUnits=len(text.encode('utf-16-le'))//2)

    def post(self,request,timeout):
        query=json.loads(request.data);self.b.requests.append(deepcopy(query))
        if query['operation']=='observe':self.b.receipt=dict(schemaVersion=1,commandId=query['commandId'],observation=self.observed())
        else:
            before=self.observed();command=query['input'];row=next(row for row in before['controls'] if row['token']==command['fieldToken']);control=row['id']
            kind='navigation' if control in navigation.IDS else 'field';owner=self.flow.owners[kind]
            assert owner.current()['phase']=='issued' and owner.store.read()==owner.previous and owner.current()['command']==command
            original=navigation.project(before,control) if kind=='navigation' else field_owner.project(before,control)
            source=self.nav if kind=='navigation' else self.field;key=str(uuid.uuid4())
            source.event(key,'received',dict(outerCommandId=query['commandId'],command=command,controlId=control,root=original['root']))
            stamp=self.f.f.stamp();self.b.sequence=command['sequence'];self.commands.append((control,deepcopy(command)))
            if self.deferred==control:self.pending=(control,deepcopy(command))
            elif self.ignore!=control:self.apply(control,command)
            self.b.receipt=dict(schemaVersion=1,commandId=query['commandId'],status=dict(schemaVersion=1,commandId=command['commandId'],
                instance=command['instance'],sequence=command['sequence'],performed=True,processId=42,sampleEpochMs=stamp['epochMs']))
            source.event(key,'returned',self.b.receipt)
            if self.lost==control:self.lost=None;raise OSError('Declared lost original normal editor return')
        self.b.response=json.dumps(query).encode();return self.b

    def reopen(self):
        history=LifecycleEditorHistory(self.f.store,self.source.binding,self.source.run,self.lock,self.source.source['check'])
        owners=[]
        for cls in (LifecycleNavigationOwner,LifecycleInputOwner):
            owners.append(cls(PrivateFeatureState(self.root/cls.store_name('primary')),self.lock,self.source.binding,self.source.run,'primary',self.native,self.source.source['check']))
        self.flow=LifecycleEditors(PrivateFeatureState(self.root/'ios-lifecycle-editors-owner.json'),history,self.source,
            owners[0],self.nav.reader(),owners[1],self.field.reader());return self.flow


class LifecycleEditorsTests(unittest.TestCase):
    def setUp(self):self.d=EditorDomain(self)

    def test_normal_create_unicode_back_then_chat_and_scripts_use_original_generations(self):
        d=self.d;before=(d.f.f.f.sessions,d.f.f.f.launches)
        for generation,editor in enumerate(('create','chat','scripts'),1):
            result=d.flow.open(editor);text={'create':'Overte ä Ω 東京 ','chat':'reply-','scripts':'retry-'}[editor]+d.source.run
            self.assertEqual(generation,result['generation']);d.flow.type(editor,text)
            measured=d.flow.history.historical_editor(len(d.flow.history.state['frames']))
            self.assertEqual(text,measured['text']);self.assertTrue(measured['focused']);self.assertTrue(measured['keyboard'])
            d.flow.back(editor);closed=d.flow.history.historical_editor(len(d.flow.history.state['frames']))
            self.assertEqual('none',closed['editor']);self.assertEqual(0,closed['generation']);self.assertFalse(closed['keyboard'])
        self.assertEqual(before,(d.f.f.f.sessions,d.f.f.f.launches));self.assertEqual(3,len(d.flow.history.state['aliases']))
        self.assertEqual(len(d.commands),len({command['commandId'] for _,command in d.commands}))

    def test_lost_entry_is_adopted_without_second_input_and_reconstruction_keeps_original_files(self):
        d=self.d;d.lost='create.entry'
        with self.assertRaises(OSError):d.flow.open('create')
        commands=deepcopy(d.commands);d.reopen();d.flow.open('create')
        entries=[row for row in d.commands if row[0]=='create.entry'];self.assertEqual(1,len(entries))
        self.assertEqual(commands,d.commands[:len(commands)]);d.flow.type('create','Overte ä Ω 東京 '+d.source.run);d.flow.back('create')
        original={path:(path.stat().st_ino,path.read_bytes()) for path in d.root.iterdir() if path.name.startswith('lifecycle-editor-frame-')}
        self.assertEqual(len(d.flow.history.state['frames']),len(original))
        count=len(d.commands);d.reopen();self.assertEqual(count,len(d.commands))
        self.assertTrue(all((path.stat().st_ino,path.read_bytes())==value for path,value in original.items()))

    def test_positive_ack_with_ignored_widget_effect_stays_unqualified_without_resend(self):
        d=self.d;d.ignore='create.entry'
        with self.assertRaises(NativeUIError):d.flow.open('create')
        self.assertEqual([],d.flow.history.state['aliases']);self.assertEqual(1,sum(control=='create.entry' for control,_ in d.commands))
        d.reopen()
        with self.assertRaises(NativeUIError):d.flow.open('create')
        self.assertEqual(1,sum(control=='create.entry' for control,_ in d.commands));self.assertEqual([],d.flow.history.state['aliases'])

    def test_late_actual_widget_callback_uses_new_observation_and_retains_failed_original(self):
        d=self.d;d.deferred='create.entry'
        with self.assertRaises(NativeUIError):d.flow.open('create')
        failed=d.flow.history.read(len(d.flow.history.state['frames']));count=len(d.flow.history.state['frames'])
        control,command=d.pending;d.apply(control,command);d.deferred=None;d.reopen();d.flow.open('create')
        self.assertEqual(1,sum(c=='create.entry' for c,_ in d.commands));self.assertGreater(len(d.flow.history.state['frames']),count)
        self.assertEqual(failed,d.flow.history.read(count));self.assertEqual(1,len(d.flow.history.state['aliases']))

    def test_real_launcher_selection_and_scripts_menu_fallback_follow_original_controls(self):
        d=self.d;d.pages=2;d.menu_fallback=True
        for editor in ('create','chat','scripts'):
            d.flow.open(editor)
            if editor!='scripts':d.flow.back(editor)
        controls=[control for control,_ in d.commands]
        self.assertEqual(1,controls.count('tablet.page.2'));self.assertIn('scripts.menu',controls)
        self.assertIn('scripts.menu-edit',controls);self.assertIn('scripts.menu-running',controls);self.assertNotIn('scripts.entry',controls)
        self.assertEqual(3,d.flow.history.historical_editor(len(d.flow.history.state['frames']))['generation'])

    def test_lost_child_reservation_is_joined_to_its_original_parent_slot_before_single_delivery(self):
        d=self.d;owner=d.flow.owners['navigation'];reserve=owner.reserve
        def lost(control,*args,**kwargs):
            result=reserve(control,*args,**kwargs)
            if control=='create.entry':raise OSError('Declared lost return after actual child reservation CAS')
            return result
        with patch.object(owner,'reserve',side_effect=lost):
            with self.assertRaises(OSError):d.flow.open('create')
        self.assertEqual(0,sum(control=='create.entry' for control,_ in d.commands));d.reopen();d.flow.open('create')
        self.assertEqual(1,sum(control=='create.entry' for control,_ in d.commands));self.assertEqual(1,len(d.flow.history.state['aliases']))

    def test_saved_observation_parent_append_recovers_original_without_query_or_input_repeat(self):
        d=self.d;write=d.flow.history.files.write;failed=False
        def lost(index,value):
            nonlocal failed
            result=write(index,value)
            if d.route=='create' and not d.current()['focused'] and not failed:
                failed=True;raise OSError('Declared lost frame return after actual saved-original CAS')
            return result
        with patch.object(d.flow.history.files,'write',side_effect=lost):
            with self.assertRaises(OSError):d.flow.open('create')
        original=deepcopy(d.flow.history.state['original']);self.assertEqual('saved',original['phase'])
        path=d.flow.history.files.path(original);saved=(path.stat().st_ino,path.read_bytes());queries=len(d.b.requests)
        d.reopen();self.assertEqual(queries,len(d.b.requests));sample=d.source.sample
        def no_requery_before_focus(*args,**kwargs):
            self.assertTrue(d.current()['focused'],'Saved entry observation must be adopted before focus input')
            return sample(*args,**kwargs)
        with patch.object(d.source,'sample',side_effect=no_requery_before_focus):d.flow.open('create')
        self.assertEqual(saved,(path.stat().st_ino,path.read_bytes()));self.assertEqual(1,sum(c=='create.entry' for c,_ in d.commands))

    def test_positive_text_delivery_with_unchanged_actual_field_cannot_supply_requested_unicode(self):
        d=self.d;d.flow.open('create');d.ignore='lifecycle.create.text';text='Overte ä Ω 東京 '+d.source.run
        with self.assertRaises(NativeUIError):d.flow.type('create',text)
        measured=d.flow.history.historical_editor(len(d.flow.history.state['frames']));self.assertEqual('',measured['text'])
        self.assertEqual('delivered',d.flow.owners['field'].current()['phase']);count=len(d.commands)
        with self.assertRaises(NativeUIError):d.flow.back('create')
        self.assertEqual(count,len(d.commands));self.assertEqual(1,measured['generation'])

    def test_ignored_semantic_back_keeps_original_editor_keyboard_and_generation(self):
        d=self.d;d.flow.open('create');d.ignore='tablet.back'
        with self.assertRaises(NativeUIError):d.flow.back('create')
        measured=d.flow.history.historical_editor(len(d.flow.history.state['frames']))
        self.assertEqual('create',measured['editor']);self.assertEqual(1,measured['generation']);self.assertTrue(measured['keyboard'])
        self.assertEqual(1,sum(c=='tablet.back' for c,_ in d.commands))

    def test_parent_operation_label_substitution_refuses_before_intent_or_input(self):
        d=self.d;d.flow.start();before=len(d.commands);saved=d.flow.store.path.read_bytes()
        with self.assertRaises(NativeUIError):d.flow.drive('create-focus','navigation','hud.tablet')
        self.assertEqual(before,len(d.commands));self.assertEqual(saved,d.flow.store.path.read_bytes())
        self.assertEqual([],d.flow.state['actions']);self.assertEqual([],d.flow.owners['navigation'].state['events'])


class LifecycleEditorsRuntimeTests(unittest.TestCase):
    def setUp(self):
        from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f

    def test_canonical_editor_scope_uses_existing_session_binding_and_lock(self):
        before=(self.f.sessions,self.f.launches)
        with self.f.adapter._lifecycle_editors_runtime().editors('test-only','a'*32) as flow:
            self.assertIsInstance(flow,LifecycleEditors);self.assertEqual(flow.binding,flow.history.binding)
            flow.bound();self.assertTrue(all(owner.lock is flow.lock for owner in flow.owners.values()))
        self.assertEqual(before,(self.f.sessions,self.f.launches))
        with self.assertRaises((NativeUIError,ValueError,RuntimeError)):flow.start()

    def test_changed_candidate_refuses_editor_factory_before_transport_or_session(self):
        self.f.artifact.write_bytes(b'Changed candidate before editor composition');before=(self.f.sessions,self.f.launches)
        with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_REJECTED'):
            with self.f.adapter._lifecycle_editors_runtime().editors('test-only','a'*32):pass
        self.assertEqual(before,(self.f.sessions,self.f.launches));self.assertEqual([],self.k.afc)
