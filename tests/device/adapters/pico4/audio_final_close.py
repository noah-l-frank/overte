"""Normal final Audio X/peak/private-tap closure, retaining process resources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters import audio_preview_lifetime as lifetime
from adapters.native_feature_observation import exact,integer,need,number,decode,validate as native_packet
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_capture_owner import PicoAudioCaptureOwner
from adapters.pico4.audio_background_owner import sha
from adapters.pico4 import audio_pages as pages,audio_settings_source as settings,lifecycle_source as ui
from adapters.pico4.lifecycle_back import BUTTON,PicoLifecycleBack,envelope,frame
from adapters.recorded_preview_history import accept_history
from adapters.script_journey.history import pack,unpack
from feature_journeys.phase_fixture import validate as phase_packet

VERSION=1
PHASES=('prepared','release-issued','released','back-issued','home','tablet-close-issued','closed')


class PicoAudioFinalClose:
    def __init__(self,path,capture):
        need(isinstance(capture,PicoAudioCaptureOwner))
        self.capture_owner,self.parent,self.preview,self.source=capture,capture.parent,capture.preview,capture.source
        self.lock,self.run,self.binding=capture.lock,capture.run,capture.binding
        self.store=PrivateFeatureState(path)
        need(self.store.path==capture.store.path.with_name('audio-final-close.json'))
        self.disk=self.state=None
        with self.lock.held():self.disk=self.store.read();self.load()
    def files_bound(self):
        self.lock.assert_held();need(self.store.read()==self.disk
            and self.capture_owner.store.read()==self.capture_owner.disk and self.parent.store.read()==self.parent.disk)
        if self.state is not None:
            need(sha(self.capture_owner.store.read())==self.state['captureSha256']
                and sha(self.parent.store.read())==self.state['parentSha256'])
    def bound(self):
        self.files_bound();return self.parent.now()
    def packets(self,row):
        exact(row,{'native','page'});packet=self.parent.raw(row['native'])
        native_packet(packet,packet['requestId'],self.parent.pid,packet['capturedEpochMs'],require_recorded_history=True)
        normal,audio,lifecycle,empty=self.parent.packets(row['page'])
        return packet,normal,audio,lifecycle,empty
    def check(self,row,where,*,released=False):
        packet,normal,audio,lifecycle,empty=self.packets(row);voice=packet['audio']['recordedVoice'];source=audio['source']
        before=self.capture_owner.frame(self.capture_owner.state['frames'][-1]);baseline=self.parent.packets(self.parent.state['frames'][0])[1]['source']
        original=pages.original(normal['picoAudioPages'],self.parent.state['originalId'])
        need(packet['instance']==before['instance'] and packet['lifecycle']==before['lifecycle']
            and voice==before['audio']['recordedVoice'] and not voice['active'] and voice['event']['phase'] in ('cancelled','completed')
            and source['native']['previewCycle']==voice['cycle'] and not source['native']['previewActive'] and not source['native']['recording']
            and not packet['audio']['recording'] and packet['audio']['muted']==source['native']['muted']==self.parent.state['previewOrigin']
            and source['properties']==baseline['properties'] and source['mixerGains']==baseline['mixerGains']
            and source['native']['localEcho']==baseline['native']['localEcho'] and source['native']['serverEcho']==baseline['native']['serverEcho']
            and ui.current_editor(lifecycle) is None and measured_keyboard(lifecycle['source']['keyboard']) is False
            and original['originalPeakValuesEnabled']==baseline['inputPeakValuesEnabled'])
        if where=='audio':
            need(normal['open'] and normal['ready'] and normal['picoAudioPages']['current']==original['id'] and original['current']
                and original['pageAlive'] and source['inputPeakValuesEnabled'] is True
                and lifecycle['source']['tabletShown'] and not lifecycle['source']['onHomeScreen'])
        else:
            need(where in ('home','closed') and not normal['picoAudioPages']['current'] and not original['pageAlive']
                and not original['current'] and source['inputPeakValuesEnabled']==baseline['inputPeakValuesEnabled']
                and normal['open']==lifecycle['source']['tabletShown']==(where=='home'))
            if where=='home':need(normal['ready'] and lifecycle['source']['onHomeScreen'])
        if released:
            need(empty is not None and audio['audioSettingsVersion']==2 and source['previewLifetime']['previewTapStateEmpty'])
        return packet
    def clocks(self,row):return [self.packets(row)[0]['capturedEpochMs'],*self.parent.clocks(row['page'])]
    def validate(self,state):
        exact(state,{'phase','captureSha256','parentSha256','fixturePhase','frames','streams','quiet'})
        need(state['phase'] in PHASES and all(type(state[key]) is str and len(state[key])==64 for key in ('captureSha256','parentSha256'))
            and type(state['frames']) is list and 1<=len(state['frames'])<=112 and type(state['streams']) is list and len(state['streams'])<=2
            and type(state['quiet']) is list and len(state['quiet'])<=3)
        phase=state['fixturePhase'];phase_packet(phase,run=self.run,area='audio',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        need(phase['active'] and phase['activations'][-1]['stimulus']==dict(verb='close',inputs={}))
        last_native=last_pages=last_settings=last_ui=last_empty=None
        for row in state['frames']:
            packet,normal,audio,lifecycle,empty=self.packets(row)
            if last_native is not None:
                need(packet['instance']==last_native['instance'] and packet['sequence']>last_native['sequence']
                    and packet['capturedEpochMs']>=last_native['capturedEpochMs'])
                accept_history(last_native['audio']['recordedVoice'],packet['audio']['recordedVoice'])
            last_native=packet;last_pages=pages.accept(last_pages,normal['picoAudioPages']);last_settings=settings.accept(last_settings,audio)
            last_ui=ui.accept(last_ui,ui.summary(lifecycle))
            if empty is not None:
                if last_empty is not None:need(empty['instance']==last_empty['instance'] and empty['sequence']>last_empty['sequence']
                    and empty['capturedEpochMs']>=last_empty['capturedEpochMs'])
                last_empty=empty
        self.check(state['frames'][0],'audio')
        expected=0 if PHASES.index(state['phase'])<3 else 1 if PHASES.index(state['phase'])<5 else 2
        need(len(state['streams'])==expected)
        previous=self.parent.state['streams'][0]['envelope'];previous_fence=-1
        for index,stream in enumerate(state['streams']):
            exact(stream,{'envelope','neutral','fence'});need(integer(stream['fence'],previous_fence+1,len(state['frames'])-1))
            self.check(state['frames'][stream['fence']],'audio' if index==0 else 'home',released=True);previous_fence=stream['fence']
            if stream['envelope'] is not None:
                envelope(stream['envelope'],self.parent.session.profile)
                need(previous is not None and stream['envelope']['sessionNonce']==previous['sessionNonce']
                    and stream['envelope']['sequence']==previous['sequence']+1
                    and stream['envelope']['commands'][0]['id']!=previous['commands'][0]['id'])
                previous=stream['envelope']
                if stream['neutral'] is not None:PicoLifecycleBack.neutral(stream['neutral'],stream['envelope'],self.packets(state['frames'][stream['fence']])[2]['capturedEpochMs'])
            else:need(stream['neutral'] is None)
            if index<len(state['streams'])-1 or state['phase'] in ('home','closed'):need(stream['envelope'] is not None and stream['neutral'] is not None)
        if state['phase'] in ('prepared','release-issued','released','back-issued'):where='audio'
        elif state['phase'] in ('home','tablet-close-issued'):where='home'
        else:where='closed'
        self.check(state['frames'][-1],where,released=PHASES.index(state['phase'])>=2)
        for window in state['quiet']:
            exact(window,{'where','first','last','deferred'});need(window['where'] in ('home','closed') and type(window['deferred']) is bool
                and integer(window['first'],0,len(state['frames'])-1) and integer(window['last'],window['first']+1,len(state['frames'])-1))
            rows=state['frames'][window['first']:window['last']+1];clocks=[self.clocks(row) for row in rows];resources=None
            for row in rows:
                self.check(row,window['where'],released=True)
                if window['deferred']:
                    current=self.packets(row)[2]['source']['previewLifetime'];need(lifetime.deferred_retired(current))
                    if resources is None:resources=deepcopy(current)
                    need(current==resources)
            need(all(all(0<=b-a<=500 for a,b in zip(old,new)) for old,new in zip(clocks,clocks[1:]))
                and all(b-a>=3000 for a,b in zip(clocks[0],clocks[-1])))
    def load(self):
        self.capture_owner.load();self.bound();disk=self.store.read()
        if disk is None:need(self.state is None);return
        exact(disk,{'audioFinalCloseVersion','runId','binding','fixtureUrl','payload'})
        need(type(disk['audioFinalCloseVersion']) is int and disk['audioFinalCloseVersion']==VERSION and disk['runId']==self.run
            and disk['binding']==self.binding and disk['fixtureUrl']==self.source.fixture_url)
        values=unpack(disk['payload']);need(len(values)==1);self.validate(values[0]);self.disk,self.state=deepcopy(disk),deepcopy(values[0]);self.bound()
    def save(self,state,*,input_intent=False):
        self.files_bound() if input_intent else self.bound();self.validate(state)
        disk=dict(audioFinalCloseVersion=VERSION,runId=self.run,binding=self.binding,fixtureUrl=self.source.fixture_url,payload=pack([state]))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(state)
        self.files_bound() if input_intent else self.bound()
    def anchor(self):return self.bound(),self.source.epoch_ms()
    def fresh(self,anchor):
        started,requested=anchor;original=self.state['fixturePhase']
        for artifact in self.capture_owner.state['artifacts'].values():self.capture_owner.read_file(artifact)
        self.files_bound();self.parent.fresh()
        current=self.source.status(original)
        need(current['active'] and all(current[key]==original[key] for key in ('instance','createdEpochMs','activations')))
        epoch=self.source.epoch_ms();completed=self.parent.settings.monotonic()
        need(number(completed,started,1e15) and completed>=self.parent.last_clock and number(epoch,requested,1e15) and -250<=epoch-current['capturedEpochMs']
            and max(epoch-current['capturedEpochMs'],requested-current['capturedEpochMs']+(completed-started)*1000)<=1500)
        self.parent.last_clock=completed
        return started,requested,current['capturedEpochMs'],epoch,completed
    def intent_fresh(self,native_anchor,fixture_anchor):
        # The session's intent callback is pure private host IO. In particular
        # no fixture HTTP/clock, native guard/query or session reentry occurs.
        native_started,native_requested,native_captured=native_anchor
        started,requested,captured,epoch,completed=fixture_anchor;now=self.parent.settings.monotonic()
        need(number(now,completed,1e15) and now>=self.parent.last_clock and now>=native_started
            and native_requested-native_captured+(now-native_started)*1000<=1500
            and max(epoch-captured+(now-completed)*1000,requested-captured+(now-started)*1000)<=1500)
        self.parent.last_clock=now
    def capture(self,*,empty=False):
        started=self.parent.now();requested=self.parent.settings.clock_ms()
        # Existing original native history consumption works after the normal
        # page has gone; AudioPreview.read() additionally requires its live UI.
        packet=self.preview._sample();raw=self.preview.native.original();need(decode(raw)==packet)
        page=self.parent.capture(empty=empty);self.parent.anchor=(started,requested,min(packet['capturedEpochMs'],self.parent.anchor[2]))
        return dict(native=frame(raw),page=page)
    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None and self.capture_owner.state['phase']=='retained')
            source=self.source.status(self.capture_owner.state['lastPhase']);need(source['active'] and source['activations'][-1]['stimulus']==dict(verb='close',inputs={}))
            owned=self.preview.owned();need(owned['pending'] is None and owned['releaseState']=='live')
            row=self.capture();self.check(row,'audio');anchor=(row['page']['hostMonotonic'],source['capturedEpochMs'])
            state=dict(phase='prepared',captureSha256=sha(self.capture_owner.store.read()),parentSha256=sha(self.parent.store.read()),
                fixturePhase=source,frames=[row],streams=[],quiet=[])
            self.save(state);self.fresh(anchor)
    def release(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='prepared');anchor=self.anchor();row=self.capture();self.check(row,'audio')
            owned=self.preview.owned();need(owned['pending'] is None and owned['releaseState']=='live' and not owned['history']['active']
                and self.packets(row)[0]['audio']['muted']==owned['originMuted'])
            state=deepcopy(self.state);state['phase']='release-issued';state['frames'].append(row);self.save(state);self.fresh(anchor)
            # Preconditions exclude normal cancel/unmute from this private tap
            # release. Its own durable requested state handles uncertain sends.
            self.preview.release_native();return self.reconcile()
    def stream(self,phase):
        with self.lock.held():
            self.load();need((phase,self.state['phase']) in (('back-issued','released'),('tablet-close-issued','home')))
            where='audio' if phase=='back-issued' else 'home'
            if where=='home':self.quiet('home')
            anchor=self.anchor();row=self.capture(empty=True);self.check(row,where,released=True)
            state=deepcopy(self.state);state['phase']=phase;state['frames'].append(row);state['streams'].append(dict(envelope=None,neutral=None,fence=len(state['frames'])-1));self.save(state);fixture_anchor=self.fresh(anchor);native_anchor=self.parent.anchor
            def intent(value):
                state=deepcopy(self.state);state['streams'][-1]['envelope']=deepcopy(value);self.save(state,input_intent=True);self.intent_fresh(native_anchor,fixture_anchor)
            self.parent.session.stage(self.binding['processIdentity'],'controller.button',BUTTON,intent=intent)
            return self.reconcile()
    def reconcile(self):
        with self.lock.held():
            self.load();phase=self.state['phase'];need(phase in ('release-issued','back-issued','tablet-close-issued'));anchor=self.anchor()
            state=deepcopy(self.state)
            if phase=='release-issued':
                owned=self.preview.owned();need(owned['pending'] is None and owned['releaseState'] in ('requested','verified'))
                if owned['releaseState']=='requested':self.preview.release_native()
                need(self.preview.owned()['releaseState']=='verified');where='audio';state['phase']='released'
            else:
                stream=state['streams'][-1];need(stream['envelope'] is not None)
                stream['neutral']=deepcopy(self.parent.session.require_owned_neutral(self.binding['processIdentity'],stream['envelope']))
                where='home' if phase=='back-issued' else 'closed';state['phase']=where
            row=self.capture(empty=True);self.check(row,where,released=True);state['frames'].append(row);self.save(state)
            result=self.report();self.fresh(anchor);return result
    def quiet(self,where,*,deferred=False):
        with self.lock.held():
            self.load();need(where in ('home','closed') and self.state['phase']==where);origin=previous=first=resources=None;started=self.bound()
            for attempt in range(25):
                anchor=self.anchor();row=self.capture(empty=True);self.check(row,where,released=True)
                if deferred:
                    current=self.packets(row)[2]['source']['previewLifetime'];need(lifetime.deferred_retired(current))
                    if resources is None:resources=deepcopy(current)
                    need(current==resources)
                clocks=self.clocks(row)
                if previous is None or any(b-a>500 for a,b in zip(previous,clocks)):origin=clocks;first=len(self.state['frames'])
                previous=clocks;state=deepcopy(self.state);state['frames'].append(row);self.save(state);result=self.report();self.fresh(anchor)
                if all(b-a>=3000 for a,b in zip(origin,clocks)):
                    state=deepcopy(self.state);state['quiet'].append(dict(where=where,first=first,last=len(state['frames'])-1,deferred=deferred));self.save(state)
                    result=self.report();self.fresh(anchor);return result
                need(self.bound()-started<6 and attempt<24);self.parent.settings.sleep(.25)
            need(False)
    def await_deferred(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='closed');started=self.bound()
            for attempt in range(41):
                anchor=self.anchor();row=self.capture(empty=True);self.check(row,'closed',released=True)
                state=deepcopy(self.state);state['frames'].append(row);self.save(state);result=self.report();self.fresh(anchor)
                if lifetime.deferred_retired(self.packets(row)[2]['source']['previewLifetime']):return self.quiet('closed',deferred=True)
                need(self.bound()-started<40 and attempt<40);self.parent.settings.sleep(1)
            need(False)
    def report(self):
        need(self.state is not None);packet,normal,audio,lifecycle,empty=self.packets(self.state['frames'][-1])
        original=pages.original(normal['picoAudioPages'],self.parent.state['originalId']);current=audio['source'].get('previewLifetime')
        baseline=self.parent.lifetime(self.parent.state['frames'][0])
        return dict(phase=self.state['phase'],cycle=packet['audio']['recordedVoice']['cycle'],tabletShown=lifecycle['source']['tabletShown'],
            pageAlive=original['pageAlive'],contextAlive=original['contextAlive'],inputPeakValuesEnabled=audio['source']['inputPeakValuesEnabled'],
            privatePcmEmpty=empty is not None,originalPcmRetained=True,originalQuietWindows=deepcopy(self.state['quiet']),
            nativeDeferredFunctorsRetired=None if current is None else lifetime.deferred_retired(current),
            nativeResourceMatchesBaseline=None if current is None or baseline is None else lifetime.restored(current,baseline),
            fullAudioQualified=False,acousticObserved=False,journalsRetained=True)
