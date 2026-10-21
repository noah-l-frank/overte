"""Owned ordinary Selfie/zoom preparation without replacing the controlled domain.

This owns view/preferences/SDK contacts only. Marker/content, current Rig/image
causality, independent publication and whole Emote retirement are separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_avatar_render import validate as avatar_packet
from adapters.native_phone_avatar_configuration import NativePhoneAvatarConfiguration,validate as config_packet,controlled
from adapters.native_phone_touch_state import NativePhoneTouchState,validate as touch_packet,released
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_graphics_subject import validate as subject_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import Locator,NativeUIError
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from overte_phone_graphics_scene import operation,rotation_equal
from overte_phone_graphics_measurements import near
from overte_phone_graphics_surface import PhoneGraphicsSurface,MODES
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=1
PACKAGE='io.github.noah_be.overte.phone'
PINCH='Enable two-finger perspective zoom'
SAVE=PACKAGE+':id/GeneralPreferencesSave'
CANCEL=PACKAGE+':id/GeneralPreferencesCancel'
GENERAL=PACKAGE+':id/settings.general'


class EmoteViewSurface(PhoneGraphicsSurface):
    """Use existing tablet/Settings/View input, including its original leases."""
    def general(self):
        tree=self.tablet.tree()
        def rows(key):return [row for row in tree.iter() if row.get('package')==PACKAGE
            and row.get('displayed','true')=='true' and row.get('resource-id')==key]
        return len(rows(SAVE))==len(rows(CANCEL))==1

    def known_tablet(self,value):
        return super().known_tablet(value) or self.owns('general') is True and self.general()

    def preference(self,enabled):
        need(type(enabled) is bool)
        with self.operation():
            self.open_settings()
            self.lease('general',True);self.click('general-open',Locator('id',GENERAL));self.ui.wait_control(Locator('id',SAVE));self.bound()
            need(self.general());self.lease('general',True)
            tree=self.tablet.tree();rows=[row for row in tree.iter() if row.get('package')==PACKAGE
                and row.get('displayed','true')=='true' and row.get('enabled','true')=='true'
                and (row.get('text')==PINCH or row.get('content-desc')==PINCH) and row.get('checkable')=='true']
            need(len(rows)==1 and rows[0].get('checked') in ('true','false'))
            if (rows[0].get('checked')=='true') is not enabled:self.click('pinch-checkbox',Locator('accessibility id',PINCH))
            # Normal Save runs Preference.save(); its ACK is not the saved value.
            self.click('general-save',Locator('id',SAVE));self.ui.wait_absent(Locator('id',SAVE));self.bound()
            self.lease('general',False);self.close_tablet()

    def dismiss_general(self):
        with self.operation():
            if self.general():
                need(self.owns('general') is True);self.click('general-cancel',Locator('id',CANCEL))
                self.ui.wait_absent(Locator('id',SAVE));self.bound()
            if self.owns('general') is True:self.lease('general',False)
            self.close_tablet()

    def pinch(self):
        with self.operation():
            need(not self.tablet.tablet_visible() and not self.general())
            rect=self.ui._request('GET','/window/rect');exact(rect,{'x','y','width','height'})
            need(all(number(rect[key],0,16384) for key in rect) and rect['width']>=240 and rect['height']>=240)
            def x(fraction):return int((rect['width']-1)*fraction)
            y=int((rect['height']-1)*.35)
            sources=[]
            for index in range(2):
                start=.55 if index==0 else .65
                actions=[dict(type='pointerMove',duration=0,origin='viewport',x=x(start),y=y),dict(type='pointerDown',button=0),
                    dict(type='pause',duration=100)]
                for tick in range(1,9):
                    # The first look-region contact stays stationary. Only the
                    # otherwise unused second contact changes pinch distance.
                    fraction=start if index==0 else start+.08*tick/8
                    actions.append(dict(type='pointerMove',duration=80,origin='viewport',x=x(fraction),y=y))
                actions.append(dict(type='pointerUp',button=0))
                sources.append(dict(type='pointer',id='overte-emote-pinch-'+str(index),parameters=dict(pointerType='touch'),actions=actions))
            self.before('pinch-send','world.pinch-out')
            try:
                self.ui._check();self.ui._request('POST','/actions',dict(actions=sources));self.ui._check();self.bound()
            finally:self.ui.release_actions() # Native original retirement is still mandatory.


class PhoneEmoteView:
    def __init__(self,adapter,selector,phase,lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='emotes' and isinstance(lock,PhoneScriptSourceLock)
            and all(callable(v) for v in (monotonic,sleep)));lock.assert_held()
        self.adapter,self.selector,self.phase,self.lock=adapter,selector,phase,lock
        self.run,self.monotonic,self.sleep=identifier(phase.run),monotonic,sleep;self.started=self.clock=None;self.failed=False;self.required_phase=None;self.delivery_anchor=None
        path=adapter.state_path(selector);need(lock.path==path.with_name('phone-script-sources.lock'))
        self.store=PrivateFeatureState(path.with_name('phone-emote-view.json'))
        _ui,_native,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(binding['processIdentity'].split(':')[0]);need(integer(self.pid,1))
        native_guard=adapter._avatar_configuration_observer(selector,read_only=True).guard
        runtime_guard=self.guard
        def original_candidate():
            need(runtime_guard() is not False and native_guard() is not False)
        self.guard=original_candidate
        self.previous=self.store.read()
        self.state=dict(phase='reserved',original=None,current=None,leases=dict(tablet=False,address=False,menu=False,general=False),actions=[],active=None)
        if self.previous is not None:self.state=self.decode(self.previous)

    def bound(self):
        self.lock.assert_held();need(not self.failed and self.guard() is not False and same(self.store.read(),self.previous))
        now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<60));self.clock=now

    def phase_guard(self):
        self.bound();previous=self.state['current']
        phase=self.phase.status(previous['phaseAfter'] if previous else None)
        need(phase['active'] and phase['activations'] and phase['activations'][-1]['stimulus']['verb']==self.required_phase)
        self.bound()

    def packet(self,value):
        exact(value,{'configuration','avatar','touch','phaseBefore','phaseAfter'})
        for key,validator,action in (('configuration',config_packet,'phone-avatar-configuration-observe'),
                ('avatar',avatar_packet,'feature-avatar-render-observe'),('touch',touch_packet,'phone-touch-state-observe')):
            original=value[key];validator(original,dict(schemaVersion=1,commandId=original.get('requestId'),action=action),
                self.pid,original.get('capturedEpochMs'))
        controlled(value['configuration'],value['avatar']);released(value['touch'])
        need(value['configuration']['instance']==value['touch']['instance'])
        for key in ('phaseBefore','phaseAfter'):
            p=value[key];phase_packet(p,run=self.run,area='emotes',request=p.get('requestId'),epoch=p.get('capturedEpochMs'))
            need(p['active'] and p['activations'])
        left,right=value['phaseBefore'],value['phaseAfter']
        phase_packet(right,run=self.run,area='emotes',request=right['requestId'],epoch=right['capturedEpochMs'],previous=left)
        need(same(left['activations'],right['activations']))

    def unchanged_avatar(self,original,current):
        a,b=original['avatar']['source'],current['avatar']['source']
        need(original['avatar']['instance']==current['avatar']['instance']
            and all(same(a[key],b[key]) for key in ('modelInstance','rigId','geometry')))
        left,right=a['pose'],b['pose']
        need(near(left['feetPosition'],right['feetPosition'],.01) and rotation_equal(left['orientation'],right['orientation'],.001)
            and near(left['modelScale'],right['modelScale'],.0001)
            and all(original['configuration']['source'][key]==current['configuration']['source'][key]
                for key in ('configured','loadedGeometry')))

    def decode(self,value):
        exact(value,{'emoteViewVersion','runId','fixtureUrl','binding','payload'})
        need(type(value['emoteViewVersion']) is int and value['emoteViewVersion']==VERSION and value['runId']==self.run
            and value['fixtureUrl']==self.phase.fixture_url and same(value['binding'],self.binding))
        records=unpack(value['payload']);need(len(records)==1);state=records[0]
        exact(state,{'phase','original','current','leases','actions','active'})
        need(state['phase'] in ('reserved','preparing','active','restoring','restored'))
        exact(state['leases'],{'tablet','address','menu','general'});need(all(type(v) is bool for v in state['leases'].values()))
        for key in ('original','current'):
            if state[key] is not None:self.packet(state[key])
        if state['original'] is not None:
            need(state['current'] is not None);self.unchanged_avatar(state['original'],state['current'])
        need(type(state['actions']) is list and len(state['actions'])<=24)
        kinds=set()
        for row in state['actions']:
            exact(row,{'kind','phase','intents','before','after'})
            need(type(row['kind']) is str and row['kind'] in {'preference-on','camera-selfie','dismiss-prepare','dismiss-cleanup',
                'restore-first-person','restore-camera','preference-restore','dismiss-camera','dismiss-restored'}|{'pinch-'+str(i) for i in range(6)}
                and row['kind'] not in kinds and row['phase'] in ('issued','observed')
                and type(row['intents']) is list and len(row['intents'])<=96);kinds.add(row['kind'])
            self.packet(row['before'])
            if row['after'] is not None:self.packet(row['after']);self.unchanged_avatar(row['before'],row['after'])
            need((row['after'] is not None)==(row['phase']=='observed'))
            for intent in row['intents']:
                exact(intent,{'stage','control','subject','graphics','fixturePhase'})
                need(type(intent['stage']) is str and 1<=len(intent['stage'])<=80
                    and type(intent['control']) is str and 1<=len(intent['control'])<=256)
                subject=intent['subject'];subject_packet(subject,dict(schemaVersion=1,commandId=subject.get('requestId'),
                    action='feature-graphics-subject-observe',runId=self.run),self.pid,subject.get('capturedEpochMs'),require_avatar=True)
                need(subject['instance']==row['before']['avatar']['instance'])
                phase=intent['fixturePhase'];phase_packet(phase,run=self.run,area='emotes',request=phase.get('requestId'),epoch=phase.get('capturedEpochMs'))
                need(phase['active'] and phase['activations'] and phase['activations'][-1]['ticket']==row['before']['phaseAfter']['activations'][-1]['ticket'])
        need(state['active'] is None or integer(state['active'],0,len(state['actions'])-1))
        if state['phase']=='reserved':need(state['original'] is None and state['current'] is None and not state['actions'] and not any(state['leases'].values()))
        else:need(state['original'] is not None)
        if state['phase'] in ('active','restored'):need(not any(state['leases'].values()))
        if state['phase']=='active':self.ready(state['current'])
        if state['phase']=='restored':self.restored(state['original'],state['current'])
        return deepcopy(state)

    def save(self):
        self.bound()
        value=dict(emoteViewVersion=VERSION,runId=self.run,fixtureUrl=self.phase.fixture_url,binding=deepcopy(self.binding),payload=pack([self.state]))
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def read(self):
        self.bound();started=self.monotonic()
        config=self.adapter._avatar_configuration_observer(self.selector,read_only=True)
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True)
        touch=self.adapter._touch_state_observer(self.selector,read_only=True)
        need(isinstance(config,NativePhoneAvatarConfiguration) and isinstance(touch,NativePhoneTouchState)
            and config.pid==avatar.pid==touch.pid==self.pid and config.ios is avatar.ios is touch.ios is False)
        previous=self.state['current']
        if previous:
            config.restore([previous['configuration']]);avatar.restore([previous['avatar']]);touch.restore([previous['touch']])
        epoch=config.clock_ms();host=self.phase.epoch_ms();need(integer(epoch,1) and number(host,1,1e15));query=self.monotonic()
        before=self.phase.status(previous['phaseAfter'] if previous else None)
        value=dict(configuration=config.read(),avatar=avatar.read(),touch=touch.read(),phaseBefore=before,phaseAfter=self.phase.status(before))
        self.packet(value)
        if self.required_phase is not None:need(before['activations'][-1]['stimulus']['verb']==self.required_phase)
        if previous:self.unchanged_avatar(previous,value)
        self.bound();result=deepcopy(value);self.bound()
        now=config.clock_ms();host_now=self.phase.epoch_ms();self.bound();final=self.monotonic()
        need(number(final,query,1e15) and final-started<5 and integer(now,epoch) and number(host_now,host,1e15))
        for key in ('configuration','avatar','touch'):fresh(value[key]['requestedEpochMs'],max(now,epoch+math.ceil((final-query)*1000)))
        fresh(before['capturedEpochMs'],max(host_now,host+math.ceil((final-query)*1000)))
        self.delivery_anchor=(query,epoch,host,config.clock_ms)
        return result

    def delivery(self,value):
        self.bound();need(self.delivery_anchor is not None)
        started,epoch,host,clock=self.delivery_anchor
        current=self.phase.status(value['phaseAfter']);self.bound()
        need(same(current['activations'],value['phaseAfter']['activations']))
        now=clock();host_now=self.phase.epoch_ms();self.bound();final=self.monotonic()
        need(integer(now,epoch) and number(host_now,host,1e15) and number(final,started,1e15) and final-started<5)
        for key in ('configuration','avatar','touch'):fresh(value[key]['requestedEpochMs'],max(now,epoch+math.ceil((final-started)*1000)))
        fresh(value['phaseBefore']['capturedEpochMs'],max(host_now,host+math.ceil((final-started)*1000)))

    def intent(self,stage,subject,graphics,control):
        self.bound();need(self.state['active'] is not None)
        row=self.state['actions'][self.state['active']];need(row['phase']=='issued' and len(row['intents'])<96)
        need(subject['instance']==self.state['original']['avatar']['instance'])
        phase=self.phase.status(self.state['current']['phaseAfter'])
        need(phase['active'] and phase['activations'] and phase['activations'][-1]['stimulus']['verb']==self.required_phase
            and phase['activations'][-1]['ticket']==row['before']['phaseAfter']['activations'][-1]['ticket'])
        row['intents'].append(dict(stage=stage,control=control,subject=deepcopy(subject),graphics=deepcopy(graphics),fixturePhase=phase));self.save()

    def lease(self,field,value):
        need(field in self.state['leases'] and type(value) is bool and self.state['active'] is not None)
        self.state['leases'][field]=value;self.save()

    def surface(self):
        original=self.adapter._graphics_surface(self.selector,self.run,self.intent,lambda key:self.state['leases'][key],
            self.lease,lambda _url:False,lock=self.lock)
        need(isinstance(original,PhoneGraphicsSurface))
        return EmoteViewSurface(original.ui,original.subject,original.graphics,self.run,self.intent,
            lambda key:self.state['leases'][key],self.lease,lambda _url:False)

    def step(self,kind,invoke,check):
        self.bound();old=[i for i,row in enumerate(self.state['actions']) if row['kind']==kind]
        if not old:
            before=self.read();self.state['current']=deepcopy(before)
            self.state['actions'].append(dict(kind=kind,phase='issued',intents=[],before=before,after=None))
            self.state['active']=len(self.state['actions'])-1;self.save();invoke(self.surface());self.bound()
        else:
            need(len(old)==1);self.state['active']=old[0];self.save()
            # An issued step may only be re-observed, never input-replayed.
        row=self.state['actions'][self.state['active']]
        if row['phase']=='observed':return # Historical step; later owned steps may supersede its value.
        current=self.read();check(row['before'],current)
        row.update(phase='observed',after=deepcopy(current));self.state['current']=current;self.save()

    @staticmethod
    def ready(current):
        need(current['avatar']['source']['cameraMode']=='selfie' and current['configuration']['source']['pinchZoomEnabled'] is True
            and number(current['configuration']['source']['boomLength'],3,12));released(current['touch'])

    def restored(self,original,current):
        self.unchanged_avatar(original,current)
        need(current['avatar']['source']['cameraMode']==original['avatar']['source']['cameraMode']
            and current['configuration']['source']['pinchZoomEnabled']==original['configuration']['source']['pinchZoomEnabled']
            and near(current['configuration']['source']['boomLength'],original['configuration']['source']['boomLength'],.00001))
        a,b=original['avatar']['source']['view'],current['avatar']['source']['view']
        need(near(a['position'],b['position'],.01) and rotation_equal(a['rotation'],b['rotation'],.001)
            and near(a['projection'],b['projection'],.0001));released(current['touch'])

    def no_leases(self):need(not any(self.state['leases'].values()))

    @operation
    def prepare(self):
        self.required_phase='baseline';self.phase_guard()
        with self.adapter.existing_input_session(self.selector):
            if self.state['phase']=='reserved':
                original=self.read();source=original['configuration']['source'];mode=original['avatar']['source']['cameraMode']
                # Normal View-menu cycling restores these exact native defaults.
                # Other existing zoom profiles fail before any mutation.
                need(mode in MODES and source['boomLength']==(.5 if mode=='first person look at' else 1.5)
                    and not self.surface().tablet.tablet_visible())
                self.state.update(phase='preparing',original=deepcopy(original),current=original);self.save()
            need(self.state['phase'] in ('preparing','active'))
            if self.state['phase']=='preparing':
                if self.state['current']['configuration']['source']['pinchZoomEnabled'] is False:
                    self.step('preference-on',lambda surface:surface.preference(True),
                        lambda _old,new:need(new['configuration']['source']['pinchZoomEnabled'] is True))
                self.step('camera-selfie',lambda surface:surface.select_camera('selfie'),
                    lambda _old,new:need(new['avatar']['source']['cameraMode']=='selfie'))
                self.step('dismiss-camera',lambda surface:surface.dismiss_general(),lambda *_:self.no_leases())
                for index in range(6):
                    if self.state['current']['configuration']['source']['boomLength']>=3:break
                    def advanced(old,new):need(new['configuration']['source']['boomLength']>old['configuration']['source']['boomLength'])
                    self.step('pinch-'+str(index),lambda surface:surface.pinch(),advanced)
                self.step('dismiss-prepare',lambda surface:surface.dismiss_general(),lambda *_:self.no_leases())
                self.ready(self.state['current']);self.state['phase']='active';self.save()
            current=self.read();self.ready(current);self.state['current']=current;self.save();self.delivery(current)
            return {'performed':True}

    @operation
    def cleanup(self):
        self.required_phase='cleanup';self.phase_guard();need(self.previous is not None and self.state['original'] is not None)
        with self.adapter.existing_input_session(self.selector):
            if self.state['phase']=='restored':
                current=self.read();self.restored(self.state['original'],current);self.no_leases();self.delivery(current);return {'performed':True}
            self.state['phase']='restoring';self.save()
            # Release own SDK state even after a lost dispatch; this is release,
            # never a repeated gesture. Read() independently requires no native
            # contacts, pending pinch or nonzero drive channels.
            self.surface().ui.release_actions();self.bound()
            self.step('dismiss-cleanup',lambda surface:surface.dismiss_general(),lambda *_:self.no_leases())
            self.step('restore-first-person',lambda surface:surface.select_camera('first person look at'),
                lambda _old,new:need(new['avatar']['source']['cameraMode']=='first person look at'
                    and new['configuration']['source']['boomLength']==.5))
            mode=self.state['original']['avatar']['source']['cameraMode']
            self.step('restore-camera',lambda surface:surface.select_camera(mode),
                lambda _old,new:need(new['avatar']['source']['cameraMode']==mode))
            saved=self.state['original']['configuration']['source']['pinchZoomEnabled']
            if self.state['current']['configuration']['source']['pinchZoomEnabled'] is not saved:
                self.step('preference-restore',lambda surface:surface.preference(saved),
                    lambda _old,new:need(new['configuration']['source']['pinchZoomEnabled'] is saved))
            self.step('dismiss-restored',lambda surface:surface.dismiss_general(),lambda *_:self.no_leases())
            current=self.read();self.restored(self.state['original'],current);self.no_leases()
            self.state.update(phase='restored',current=current);self.save();self.delivery(current);return {'performed':True}

    @operation
    def retire(self,retain):
        self.required_phase='cleanup';self.bound();need(callable(retain) and self.state['phase']=='restored');self.decode(self.previous)
        current=self.read();self.restored(self.state['original'],current);self.no_leases();self.bound()
        # The enclosing owner persists this exact original proof before this
        # child's ownership can disappear, including a lost retirement return.
        need(retain(deepcopy(current)) is not False);self.delivery(current)
        self.store.discard(self.previous);need(self.store.read() is None)
        self.previous=None;result=deepcopy(current);self.delivery(current);return result
