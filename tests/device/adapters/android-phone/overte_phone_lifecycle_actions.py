"""Normal source-bound editor, Back, background and owned key/event inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.native_feature_observation import need,number
from adapters.normal_ui import Locator,NativeUIError
from feature_journeys.fixtures import context
from overte_phone_script_ui import PhoneScriptUI
from overte_phone_create_ui import PhoneCreateUI


class LifecycleActions:
    def __init__(self,feature,owner):self.flow,self.owner=feature,owner
    def intent(self,request):
        need(len(self.owner['intents'])<256);self.owner['intents'].append(deepcopy(request));self.flow.save_owner(self.owner)
    def sdk(self):
        native,_observe,binding,guard,_installed=self.flow.adapter.normal_feature_runtime(self.flow.selector,read_only=True)
        need(binding==self.owner['binding']);guard();return native,PhoneScriptUI(native,'io.github.noah_be.overte.phone')
    def step(self,name,call,*,before_foreground=True,after_foreground=True):
        key=self.owner['call']['ticket']+'-'+name if self.owner['call'] is not None else 'cleanup-'+name
        need(key not in self.owner['steps'] and len(self.owner['steps'])<256)
        self.owner['steps'].append(key);self.flow.save_owner(self.owner)
        if before_foreground:self.flow.runtime(self.owner)
        else:self.flow.adapter._graphics_lifecycle_status(self.flow.selector,self.owner['binding'])
        value=call()
        if after_foreground:self.flow.runtime(self.owner)
        else:self.flow.adapter._graphics_lifecycle_status(self.flow.selector,self.owner['binding'])
        return value
    def editor(self,*,control=False):return self.flow.adapter._lifecycle_editor(self.flow.selector,read_only=not control,intent=self.intent if control else None)
    def pending(self,*,control=False):
        return self.flow.adapter._pending_owner(self.flow.selector,intent=self.intent if control else None,read_only=not control)
    def world(self,*,control=False):return self.flow.adapter._lifecycle_world(self.flow.selector,read_only=not control,intent=self.intent if control else None)
    def current(self):return self.editor().request(self.flow.run)['source']['current']
    def wait(self,reader,predicate,*,seconds=10,foreground=True):
        started=previous=self.flow.monotonic()
        for attempt in range(101):
            value=reader()
            if foreground:self.flow.runtime(self.owner)
            now=self.flow.monotonic();need(number(now,previous,started+seconds));previous=now
            if predicate(value):return value
            need(attempt<100);self.flow.sleep(.1)
        raise NativeUIError('Original lifecycle input effect did not become available')
    def home(self,name):
        native,ui=self.sdk();need(ui.tablet_visible() and self.owner['tabletLease'])
        if native.available(ui.resource('app.scripts'),require_enabled=False):
            need(self.current()['status']=='none');return
        self.step(name,lambda:native.click(ui.resource('nav.home')))
        self.wait(self.current,lambda value:value['status']=='none')
    def open(self,editor,*,focus=True):
        native,ui=self.sdk()
        if not ui.tablet_visible():
            need(not self.owner['tabletLease']);self.owner['tabletLease']=True;self.flow.save_owner(self.owner)
            self.step('tablet-open',ui.open_tablet)
        need(self.owner['tabletLease'])
        if editor=='create':
            create=PhoneCreateUI(native,'io.github.noah_be.overte.phone');self.step('open-create',create.open_create)
            self.step('create-new-tab',lambda:create.tab(0))
        elif editor=='scripts':self.step('open-scripts',ui.open_manager);ui.wait_manager()
        else:
            need(editor=='chat');self.home('chat-home');entry=Locator('accessibility id','CHAT')
            if not native.available(entry):
                for index in range(1,9):
                    button=ui.resource('tabletPage.'+str(index))
                    if native.available(button):self.step('chat-page-'+str(index),lambda button=button:native.click(button))
                    if native.available(entry):break
            self.step('open-chat',lambda:native.click(entry))
        self.wait(self.current,lambda value:value['status']=='ready' and value['editor']==editor and value['text']=='' and not value['focused'])
        if focus:
            reader=self.editor(control=True);reader.request(self.flow.run);reader.request(self.flow.run,'focus')
            self.wait(self.current,lambda value:value['status']=='ready' and value['editor']==editor and value['focused'])
    def close(self):
        native,ui=self.sdk()
        if ui.tablet_visible():
            need(self.owner['tabletLease']);self.home('close-home');self.step('tablet-close',ui.close_tablet);ui.wait_tablet_absent()
        self.wait(self.current,lambda value:value['status']=='none')
        self.owner['tabletLease']=False;self.flow.save_owner(self.owner)
    def release_world(self,*,explicit=False):
        reader=self.world(control=True);before=reader.request(self.flow.run)
        source=before['source']
        if source['pending']:
            need(source['pendingRun']==self.flow.run)
            before=reader.request(self.flow.run,'release',source['pendingGesture'])
            if explicit:
                row=next(row for row in before['source']['gestures'] if row['gestureId']==source['pendingGesture'])
                need(row['releaseObserved'] and row['releaseReason']=='explicit')
        elif explicit:need(False)
        self.wait(lambda:reader.request(self.flow.run),lambda value:not value['source']['pending'] and value['motion']['upPressed']==0
            and all(abs(item)<=1e-6 for item in value['motion']['effectiveDrive']))
    def restore(self):
        from adapters.shared_appium.adapter import EMBEDDED_FIXTURE_URL
        self.step('restore-scene',lambda:self.flow.adapter.invoke(self.flow.selector,'scene.load',dict(url=EMBEDDED_FIXTURE_URL)))
        origin=self.owner['baseline']['world']['motion']['feetPosition'];reader=self.world()
        self.wait(lambda:reader.request(self.flow.run),lambda value:value['motion']['grounded']
            and math.sqrt(sum((a-b)**2 for a,b in zip(value['motion']['feetPosition'],origin)))<=.025,seconds=20)
    def deliver(self,call):
        verb=call['verb'];run=self.flow.run
        if verb=='open-editor':self.open(call['inputs']['editor'])
        elif verb=='type':
            reader=self.editor(control=True);before=reader.request(run);editor=before['source']['current'];need(editor['status']=='ready' and editor['focused'])
            key={'create':'unicode','chat':'reply','scripts':'retry'}[editor['editor']];need(call['inputs']['text']==context(run)[key])
            reader.request(run,'type')
        elif verb=='back':
            current=self.current();need(current['status']=='ready' and current['editor']=='create')
            client,session,_state=self.flow.adapter.existing_session(self.flow.selector)
            self.step('actual-android-back',lambda:client.execute(session,'mobile: pressKey',dict(keycode=4)))
            self.wait(self.current,lambda value:value['status']=='none')
        elif verb=='background-resume':
            old=self.current();need(old['status']=='ready' and old['editor']=='chat')
            before=self.flow.adapter._native_feature_observer(self.flow.selector,read_only=True).read(0)
            self.step('background',lambda:self.flow.adapter.invoke(self.flow.selector,'lifecycle.background',{}),after_foreground=False)
            self.wait(lambda:self.flow.adapter._graphics_lifecycle_status(self.flow.selector,self.owner['binding']),lambda value:value['foreground'] is False,seconds=5,foreground=False)
            self.step('foreground',lambda:self.flow.adapter.invoke(self.flow.selector,'app.launch',{}),before_foreground=False)
            after=self.flow.adapter._native_feature_observer(self.flow.selector,read_only=True).read(0)
            need(before['instance']==after['instance'] and before['lifecycle']['launches']==after['lifecycle']['launches']
                and after['lifecycle']['backgrounds']>before['lifecycle']['backgrounds'] and after['lifecycle']['activations']>before['lifecycle']['activations'])
            self.wait(self.current,lambda value:value['status']=='ready' and value['fieldToken']==old['fieldToken'] and value['text']==old['text'] and not value['focused'])
        elif verb=='hold-editor-input':
            need(call['inputs']['text']==context(run)['unicode']);self.pending(control=True).hold(run)
        elif verb=='replace-context':
            old=self.current();need(old['status']=='ready' and old['editor']=='scripts')
            self.home('replace-home');self.open('scripts',focus=False);new=self.current();need(new['fieldToken']!=old['fieldToken'])
        elif verb=='deliver-stale-input':
            reader=self.pending(control=True);source=reader.read(run);need(source['commit'])
            reader.attempt_retired(run,source['commit']['observation']['eventId'])
        elif verb=='close-editor':self.close()
        elif verb=='world-input':
            need(call['inputs']==dict(direction='forward'));reader=self.world(control=True);before=reader.request(run);current=self.current()
            held=reader.request(run,'hold');rows=[row for row in held['source']['gestures'] if row['runId']==run and row['pressObserved']
                and any(row['commandId']==command['commandId'] for command in self.owner['intents'])];need(rows)
            if current['status']=='ready':
                need(current['editor']=='create' and current['focused'])
                self.wait(lambda:reader.request(run),lambda value:value['motion']['sequence']>before['motion']['sequence'] and all(abs(x)<=1e-6 for x in value['motion']['effectiveDrive']))
                self.release_world(explicit=True)
            else:
                origin=self.owner['baseline']['world']['motion']['feetPosition']
                stable=dict(position=None,epoch=None,clock=None,sequences=set())
                def contact(value):
                    motion=value['motion'];position=motion['feetPosition'];now=self.flow.monotonic()
                    if not value['source']['pending'] or motion['effectiveDrive'][2]<=0 or not .3<=math.dist(position,origin)<=3:return False
                    if stable['position'] is None or math.dist(position,stable['position'])>.01:
                        stable.update(position=position,epoch=motion['capturedEpochMs'],clock=now,sequences=set())
                    stable['sequences'].add(motion['sequence'])
                    return len(stable['sequences'])>=3 and motion['capturedEpochMs']-stable['epoch']>=250 and now-stable['clock']>=.25
                # The controlled scene's actual collision contact may settle
                # while forward remains held. Camera/drive setters and view
                # leases would defeat the input-isolation measurement.
                self.wait(lambda:reader.request(run),contact,seconds=5)
        elif verb=='release-input':self.release_world(explicit=True)
        elif verb=='restore':self.restore()
        else:need(False)
