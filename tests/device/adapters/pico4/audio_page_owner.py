"""Durable normal Audio open/muted rejection/restore/close; partial recipe only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.recorded_preview_evidence import INPUT,SINK
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from adapters.audio_preview import AudioPreview
from adapters import audio_preview_lifetime as lifetime
from adapters.token_audio_ui import TokenAudioUI
from adapters.native_chat_view import measured_keyboard
from adapters.pico4 import audio_pages as pages,audio_settings_source as settings,lifecycle_source as ui
from adapters.pico4.lifecycle_back import BUTTON,PicoLifecycleBack,envelope,frame
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import validate_envelope

VERSION=1
PHASES=('prepared','tablet-issued','tablet-open','opening','opened','claim-issued','claimed','mute-issued','muted',
    'record-issued','rejected','restore-issued','restored','release-issued','released','back-issued','home','tablet-close-issued','closed')


class PicoAudioPageOwner:
    def __init__(self,path,run,binding,page_source,settings_source,ui_source,preview,session,route,source_lock):
        need(ui.nonce(run) and isinstance(page_source,pages.PicoAudioPages) and isinstance(settings_source,settings.PicoAudioSettings)
            and isinstance(ui_source,ui.PicoLifecycleSource) and isinstance(preview,AudioPreview)
            and isinstance(session,PicoOpenXrAdapterSession) and isinstance(route,TokenAudioUI) and isinstance(source_lock,ScriptSourceLock))
        need(page_source.source_lock is settings_source.source_lock is ui_source.source_lock is preview.lock is source_lock)
        self.store,self.run,self.binding=PrivateFeatureState(path),run,deepcopy(context(binding));self.pid=int(binding['processIdentity'].split(':')[0])
        need(self.store.path.name=='audio-page-owner.json' and source_lock.path==self.store.path.with_name('script-sources.lock')
            and page_source.pid==settings_source.pid==ui_source.pid==preview.native.pid==self.pid
            and preview.binding==self.binding and preview.run==run and page_source.bridge==binding['sessionId'])
        self.pages,self.settings,self.ui,self.preview,self.session,self.route,self.lock=page_source,settings_source,ui_source,preview,session,route,source_lock
        self.disk=self.state=self.anchor=self.last_clock=None;self.route.intent=self.intent
        with self.lock.held():self.load()
    def now(self):
        need(self.settings.guard() is not False);now=self.settings.monotonic()
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock));self.last_clock=now;return now
    def raw(self,row):
        exact(row,{'raw','sha256'});need(type(row['raw']) is str and len(row['raw'].encode())<=262144 and frame(row['raw'])==row)
        return decode(row['raw'])
    def empty(self,packet):
        exact(packet,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','files','memoryEmpty'})
        need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1 and ui.nonce(packet['requestId']) and ui.nonce(packet['instance'])
            and integer(packet['sequence'],1) and packet['processId']==self.pid and integer(packet['processId'],1)
            and integer(packet['requestedEpochMs'],1) and integer(packet['capturedEpochMs'],packet['requestedEpochMs'],packet['requestedEpochMs']+4999)
            and packet['memoryEmpty'] is True and type(packet['files']) is list and len(packet['files'])==2)
        for row,name in zip(packet['files'],(INPUT,SINK)):exact(row,{'name','exists'});need(row['name']==name and row['exists'] is False)
        return packet
    def packets(self,row):
        exact(row,{'pages','settings','ui','empty','hostMonotonic'});need(number(row['hostMonotonic'],0,1e15))
        normal=self.raw(row['pages']);self.pages.packet(row['pages']['raw'],normal['updatedEpochMs'])
        audio=self.raw(row['settings']);settings.validate(audio,audio,self.pid,audio['capturedEpochMs']);need(audio['runId']==self.run)
        lifecycle=self.raw(row['ui']);ui.validate(lifecycle,lifecycle,self.pid,lifecycle['capturedEpochMs']);need(lifecycle['runId']==self.run)
        empty=None if row['empty'] is None else self.empty(self.raw(row['empty']))
        return normal,audio,lifecycle,empty
    def validate(self,state):
        exact(state,{'phase','frames','streams','route','originalId','operations','previewOrigin','quiet','fences'})
        need(state['phase'] in PHASES and type(state['frames']) is list and 1<=len(state['frames'])<=96
            and set(state['operations'])=={'mute','record','restore'} and all(ui.nonce(v) for v in state['operations'].values())
            and len(set(state['operations'].values()))==3 and type(state['previewOrigin']) is bool
            and (state['originalId'] is None or ui.nonce(state['originalId'])))
        prior_pages=prior_settings=prior_ui=None;last_empty=None
        for row in state['frames']:
            normal,audio,lifecycle,empty=self.packets(row)
            prior_pages=pages.accept(prior_pages,normal['picoAudioPages']);prior_settings=settings.accept(prior_settings,audio)
            prior_ui=ui.accept(prior_ui,ui.summary(lifecycle))
            if empty is not None:
                if last_empty is not None:need(empty['instance']==last_empty['instance'] and empty['sequence']>last_empty['sequence']
                    and empty['capturedEpochMs']>=last_empty['capturedEpochMs'] and empty['requestId']!=last_empty['requestId'])
                last_empty=empty
        normal,audio,lifecycle,empty=self.packets(state['frames'][0]);need(not normal['open'] and not lifecycle['source']['tabletShown']
            and ui.current_editor(lifecycle) is None and measured_keyboard(lifecycle['source']['keyboard']) is False
            and not normal['picoAudioPages']['current'] and empty is not None)
        need(state['previewOrigin']==audio['source']['native']['muted'])
        need(type(state['streams']) is list and len(state['streams'])<=3)
        for index,stream in enumerate(state['streams']):
            exact(stream,{'operation','envelope','neutral'});need(stream['operation']==('tablet.open' if index==0 else 'controller.button'))
            if stream['envelope'] is not None:
                if stream['operation']=='controller.button':envelope(stream['envelope'],self.session.profile)
                else:
                    validate_envelope(stream['envelope'],self.session.profile)
                    need(stream['envelope']['commands']==[dict(id='tablet-open-'+str(stream['envelope']['sequence']),operation='tablet.open',arguments=dict(holdMilliseconds=1000))])
                if stream['neutral'] is not None:PicoLifecycleBack.neutral(stream['neutral'],stream['envelope'],audio['capturedEpochMs'])
            else:need(stream['neutral'] is None)
        route=state['route']
        if route is not None:
            exact(route,{'verb','identifier','token','before','after'});need(route['verb']=='open-audio' and route['identifier']=='audio.entry'
                and type(route['token']) is str and bool(route['token']))
            for scope in (route['before'],route['after']):
                if scope is not None:
                    exact(scope,{'bridgeId','generation','processId','lastCommandSequence'});need(scope['bridgeId']==self.binding['sessionId']
                        and scope['processId']==self.pid and integer(scope['lastCommandSequence']))
            if route['after'] is not None:need(route['after']['generation']==route['before']['generation']
                and route['after']['lastCommandSequence']==route['before']['lastCommandSequence']+1)
        exact(state['fences'],{'mute','record','restore'});previous=-1
        for key in ('mute','record','restore'):
            index=state['fences'][key]
            if index is not None:need(integer(index,0,len(state['frames'])-1) and index>previous);previous=index
        phase=state['phase'];before_audio=phase in ('prepared','tablet-issued','tablet-open','opening')
        need((state['originalId'] is None)==before_audio)
        expected_streams=0 if phase=='prepared' else 1 if PHASES.index(phase)<PHASES.index('back-issued') else 2 if phase in ('back-issued','home') else 3
        need(len(state['streams'])==expected_streams)
        for index,stream in enumerate(state['streams']):
            if index<len(state['streams'])-1 or phase not in ('tablet-issued','back-issued','tablet-close-issued'):
                need(stream['envelope'] is not None and stream['neutral'] is not None)
        if phase=='prepared' or phase=='tablet-issued':where='closed'
        elif phase in ('tablet-open','opening','home','tablet-close-issued'):where='home'
        elif phase=='closed':where='closed'
        else:where='audio'
        self.check(state['frames'][-1],where,state=state)
        if not before_audio:need(route is not None and route['after'] is not None)

        need(type(state['quiet']) is list and len(state['quiet'])<=4)
        for window in state['quiet']:
            exact(window,{'where','first','last'});need(window['where'] in ('home','closed')
                and integer(window['first'],0,len(state['frames'])-1) and integer(window['last'],window['first']+1,len(state['frames'])-1))
            samples=state['frames'][window['first']:window['last']+1];first=previous=None
            for sample in samples:
                self.check(sample,window['where'],state=state);need(sample['empty'] is not None)
                clocks=self.clocks(sample)
                if first is None:first=clocks
                if previous is not None:need(all(0<=now-old<=500 for now,old in zip(clocks,previous)))
                previous=clocks
            need(all(now-old>=3000 for now,old in zip(previous,first)))

    def load(self):
        self.lock.assert_held();self.now();disk=self.store.read()
        if self.disk is not None:need(disk==self.disk)
        if disk is None:need(self.state is None);return
        exact(disk,{'audioPageOwnerVersion','runId','binding','payload'})
        need(type(disk['audioPageOwnerVersion']) is int and disk['audioPageOwnerVersion']==VERSION and disk['runId']==self.run and disk['binding']==self.binding)
        value=unpack(disk['payload']);need(len(value)==1);self.validate(value[0]);last=self.packets(value[0]['frames'][-1])
        for reader,previous in ((self.pages,last[0]['picoAudioPages']),(self.settings,last[1]),(self.ui,ui.summary(last[2]))):
            if reader.previous is None:reader.restore(previous)
            elif reader.previous!=previous:
                if reader is self.pages:pages.accept(previous,reader.previous)
                elif reader is self.settings:settings.accept(previous,reader.previous)
                else:ui.accept(previous,reader.previous)
        empties=[self.packets(row)[3] for row in value[0]['frames'] if row['empty'] is not None]
        need(bool(empties));evidence=self.preview.evidence
        need(evidence.instance in (None,empties[-1]['instance']));evidence.instance=empties[-1]['instance']
        evidence.sequence=max(evidence.sequence,empties[-1]['sequence'])
        self.disk,self.state=deepcopy(disk),deepcopy(value[0])
    def save(self,state):
        self.lock.assert_held();need(self.store.read()==self.disk);self.validate(state)
        disk=dict(audioPageOwnerVersion=VERSION,runId=self.run,binding=self.binding,payload=pack([state]))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(state)
    def capture(self,*,empty=False):
        self.lock.assert_held();started=self.now();requested=self.settings.clock_ms()
        normal=self.pages.capture();audio=self.settings.capture(self.run);lifecycle=self.ui.capture(self.run)
        result=dict(pages=frame(self.pages.last_raw),settings=frame(self.settings.last_raw),ui=frame(self.ui.last_raw),empty=None,hostMonotonic=0)
        need(self.raw(result['pages'])==normal and self.raw(result['settings'])==audio and self.raw(result['ui'])==lifecycle)
        clocks=[normal['picoAudioPages']['capturedEpochMs'],audio['capturedEpochMs'],lifecycle['capturedEpochMs'],*(audio['source'][k] for k in settings.CLOCKS)]
        if empty:
            observed=self.preview.evidence.inspect_empty();result['empty']=frame(self.preview.evidence.original())
            need(self.empty(self.raw(result['empty']))==observed);clocks.append(observed['capturedEpochMs'])
        result['hostMonotonic']=self.now();self.anchor=(started,requested,min(clocks));self.packets(result);return result
    def fresh(self):
        need(self.anchor is not None);started,requested,captured=self.anchor
        need(self.settings.guard() is not False and self.ui.guard() is not False and self.pages.guard() is not False)
        epoch=self.settings.clock_ms();completed=self.settings.monotonic()
        need(number(completed,0,1e15) and self.last_clock<=completed and completed-started<=1.5
            and integer(epoch,1) and -250<=epoch-captured and max(epoch-captured,requested-captured+(completed-started)*1000)<=1500)
        self.last_clock=completed
    def check(self,row,where,*,state=None):
        state=self.state if state is None else state
        normal,audio,lifecycle,_=self.packets(row);source=audio['source'];base=self.packets(state['frames'][0])[1]['source'];native=source['native']
        selected=state['originalId']
        need(source['properties']['context']=='VR' and not native['recording'] and not native['previewActive']
            and native['muted']==source['properties']['muted']==source['properties']['mutedHMD']
            and native['localEcho']==base['native']['localEcho'] and native['serverEcho']==base['native']['serverEcho']
            and source['mixerGains']==base['mixerGains'] and ui.current_editor(lifecycle) is None
            and measured_keyboard(lifecycle['source']['keyboard']) is False)
        for key in settings.BOOLEANS+settings.NUMBERS:
            if key not in ('muted','mutedHMD'):need(source['properties'][key]==base['properties'][key])
        if state['phase'] in ('rejected','restore-issued','restored','release-issued','released','back-issued','home','tablet-close-issued','closed'):
            need(native['previewCycle']==1)
        opened=where=='audio';need(source['inputPeakValuesEnabled']==(True if opened else base['inputPeakValuesEnabled']))
        if opened:
            original=pages.original(normal['picoAudioPages'],selected)
            need(normal['open'] and normal['ready'] and normal['picoAudioPages']['current']==original['id'] and original['current']
                and original['originalPeakValuesEnabled']==base['inputPeakValuesEnabled'] and lifecycle['source']['tabletShown']
                and not lifecycle['source']['onHomeScreen'])
        else:
            need(not normal['picoAudioPages']['current'] and native['muted']==base['native']['muted'])
            if selected is not None:need(not pages.original(normal['picoAudioPages'],selected)['pageAlive'])
            need(lifecycle['source']['tabletShown']==(where=='home') and normal['open']==(where=='home'))
            if where=='home':need(lifecycle['source']['onHomeScreen'])
        return normal,audio,lifecycle
    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None and self.preview.store.read() is None);row=self.capture(empty=True)
            normal,audio,lifecycle,_=self.packets(row);source=audio['source']
            need(not source['native']['previewActive'] and source['native']['previewCycle']==0)
            state=dict(phase='prepared',frames=[row],streams=[],route=None,originalId=None,
                operations={key:uuid.uuid4().hex for key in ('mute','record','restore')},previewOrigin=source['native']['muted'],quiet=[],fences={key:None for key in ('mute','record','restore')})
            self.save(state);self.check(row,'closed');self.fresh()
    def intent(self,verb,observed,identifier):
        self.lock.assert_held();need(self.state['phase']=='opening' and self.state['route'] is None and verb=='open-audio' and identifier=='audio.entry')
        need(observed['bridgeId']==self.binding['sessionId'] and observed['processId']==self.pid and observed['ready'])
        control=self.route.row(observed,identifier,ready=True);need(control is not None)
        state=deepcopy(self.state);state['route']=dict(verb=verb,identifier=identifier,token=control['token'],
            before={key:observed[key] for key in ('bridgeId','generation','processId','lastCommandSequence')},after=None)
        self.save(state);self.fresh()
    def stream(self,phase,operation):
        state=deepcopy(self.state);state.update(phase=phase);state['streams'].append(dict(operation=operation,envelope=None,neutral=None));self.save(state);self.fresh()
        def intent(value):
            state=deepcopy(self.state);state['streams'][-1]['envelope']=deepcopy(value);self.save(state)
            started,requested,captured=self.anchor;now=self.settings.monotonic()
            need(number(now,0,1e15) and now>=self.last_clock and requested-captured+(now-started)*1000<=1500)
        self.session.stage(self.binding['processIdentity'],operation,dict(holdMilliseconds=1000) if operation=='tablet.open' else BUTTON,intent=intent)
    def tablet(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='prepared');row=self.capture(empty=True);self.check(row,'closed')
            state=deepcopy(self.state);state['frames'].append(row);self.save(state);self.stream('tablet-issued','tablet.open');return self.reconcile()
    def open_audio(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='tablet-open');row=self.capture(empty=True);self.check(row,'home')
            state=deepcopy(self.state);state['frames'].append(row);state['phase']='opening';self.save(state);self.fresh()
            self.route.activate('audio.entry','open-audio');return self.reconcile()
    def claim_preview(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='opened' and self.preview.store.read() is None)
            row=self.capture();self.check(row,'audio');state=deepcopy(self.state);state['frames'].append(row);state['phase']='claim-issued';self.save(state);self.fresh()
            self.preview.claim();return self.reconcile()
    def action(self,kind):
        with self.lock.held():
            self.load();before={'mute':'claimed','record':'muted','restore':'rejected'};need(kind in before and self.state['phase']==before[kind])
            row=self.capture();self.check(row,'audio');state=deepcopy(self.state);state['frames'].append(row);state['phase']=kind+'-issued';state['fences'][kind]=len(state['frames'])-1;self.save(state);self.fresh()
            enabled=True if kind=='mute' else self.state['previewOrigin'] if kind=='restore' else None
            self.preview.act(state['operations'][kind],'record-start' if kind=='record' else 'mute',enabled=enabled);return self.reconcile()
    def release(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='restored');row=self.capture();self.check(row,'audio')
            state=deepcopy(self.state);state['frames'].append(row);state['phase']='release-issued';self.save(state);self.fresh()
            self.preview.release_native();return self.reconcile()
    def close_page(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='released');row=self.capture(empty=True);self.check(row,'audio')
            state=deepcopy(self.state);state['frames'].append(row);self.save(state);self.stream('back-issued','controller.button');return self.reconcile()
    def close_tablet(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='home');self.quiet('home');self.stream('tablet-close-issued','controller.button');self.reconcile();return self.quiet('closed')
    def reconcile(self):
        with self.lock.held():
            self.load();need(self.state is not None);state=deepcopy(self.state);phase=state['phase']
            if phase in ('tablet-issued','back-issued','tablet-close-issued'):
                need(state['streams'][-1]['envelope'] is not None)
                state['streams'][-1]['neutral']=deepcopy(self.session.require_owned_neutral(self.binding['processIdentity'],state['streams'][-1]['envelope']))
                row=self.capture(empty=True);self.check(row,'closed' if phase=='tablet-close-issued' else 'home')
                state['phase']={'tablet-issued':'tablet-open','back-issued':'home','tablet-close-issued':'closed'}[phase]
            elif phase=='opening':
                need(state['route'] is not None);row=self.capture();normal,audio,lifecycle,_=self.packets(row)
                state['route']['after']={key:normal[key] for key in ('bridgeId','generation','processId','lastCommandSequence')}
                original=normal['picoAudioPages']['current'];need(ui.nonce(original) and original not in {r['id'] for r in self.packets(state['frames'][0])[0]['picoAudioPages']['originals']})
                state['originalId']=original;self.check(row,'audio',state=state);state['phase']='opened'
            elif phase in ('claim-issued','mute-issued','record-issued','restore-issued','release-issued'):
                if phase=='claim-issued' and self.preview.store.read() is None:
                    # Claim creates only a private owner after new read-only
                    # sources; it never delivers an ordinary audio input.
                    current=self.capture(empty=True);self.check(current,'audio');self.fresh();self.preview.claim()
                owned=self.preview.owned();need(owned['originMuted']==state['previewOrigin']
                    and owned['nativeInstance']==self.packets(state['frames'][0])[3]['instance'])
                if phase in ('mute-issued','record-issued','restore-issued'):
                    kind=phase[:-7];operation=state['operations'][kind]
                    if owned['pending'] is not None:need(owned['pending']['operationId']==operation);self.preview.reconcile();owned=self.preview.owned()
                    need(any(action['operationId']==operation and action['verb']==('record-start' if kind=='record' else 'mute') for action in owned['actions']))
                if phase=='release-issued':
                    need(owned['releaseState'] in ('requested','verified'))
                    if owned['releaseState']=='requested':self.preview.release_native()
                    need(self.preview.owned()['releaseState']=='verified')
                row=self.capture(empty=phase=='release-issued');self.check(row,'audio');source=self.packets(row)[1]['source']
                if phase=='claim-issued':need(source['native']['previewCycle']==0 and owned['history']['cycle']==0)
                if phase in ('mute-issued','record-issued'):need(source['native']['muted'] is True)
                if phase in ('record-issued','restore-issued','release-issued'):
                    history=owned['history'];need(history['cycle']==source['native']['previewCycle']==1 and not history['active']
                        and history['event']['phase']=='error' and history['event']['error']=='microphone-muted'
                        and history['event']['capturedBytes']==history['event']['playedBytes']==history['event']['totalBytes']==0)
                    fence=self.packets(state['frames'][state['fences']['record']])
                    need(history['startedEpochMs']>=max(fence[0]['picoAudioPages']['capturedEpochMs'],fence[1]['capturedEpochMs'],fence[2]['capturedEpochMs']))
                if phase in ('restore-issued','release-issued'):need(source['native']['muted']==state['previewOrigin'])
                state['phase']={'claim-issued':'claimed','mute-issued':'muted','record-issued':'rejected','restore-issued':'restored','release-issued':'released'}[phase]
            else:need(False)
            state['frames'].append(row);self.save(state);result=self.report();self.fresh();return result
    def clocks(self,row):
        normal,audio,lifecycle,empty=self.packets(row);need(empty is not None)
        return [audio['capturedEpochMs'],lifecycle['capturedEpochMs'],normal['picoAudioPages']['capturedEpochMs'],empty['capturedEpochMs'],
            *(audio['source'][key] for key in settings.CLOCKS),row['hostMonotonic']*1000]
    def lifetime(self,row):
        audio=self.packets(row)[1]
        return audio['source'].get('previewLifetime') if audio['audioSettingsVersion']==2 else None
    def resource_match(self,row):
        current,original=self.lifetime(row),self.lifetime(self.state['frames'][0])
        return None if current is None or original is None else lifetime.restored(current,original)
    def await_deferred(self):
        """Read original closure destruction without sending or repeating input.

        The native 30s callback supplies immutable events. Requested waiting,
        PCM absence and receiver death never produce a retirement event here.
        The bounded journal remains retained on timeout or unavailable data.
        """
        with self.lock.held():
            self.load();need(self.state['phase']=='closed' and self.lifetime(self.state['frames'][0]) is not None)
            started=self.now()
            for attempt in range(41):
                row=self.capture(empty=True);self.check(row,'closed')
                need(self.packets(row)[1]['source']['native']['previewCycle']==1 and self.preview.owned()['releaseState']=='verified')
                state=deepcopy(self.state);state['frames'].append(row);self.save(state);result=self.report();self.fresh()
                if self.resource_match(row) is True:return self.quiet('closed',require_deferred=True)
                need(self.now()-started<40 and attempt<40);self.settings.sleep(1)
            need(False)
    def quiet(self,where,*,require_deferred=False):
        with self.lock.held():
            self.load();need(where in ('home','closed') and self.state['phase']==where);origin=prior=None;first_index=None;started=self.now()
            for _attempt in range(41):
                row=self.capture(empty=True);self.check(row,where);_,audio,lifecycle,empty=self.packets(row)
                if require_deferred:need(self.resource_match(row) is True)
                need(audio['source']['native']['previewCycle']==1 and self.preview.owned()['releaseState']=='verified')
                clocks=self.clocks(row)
                if prior is None or any(now-old>500 for now,old in zip(clocks,prior)):origin=clocks;first_index=len(self.state['frames'])
                prior=clocks;state=deepcopy(self.state);state['frames'].append(row);self.save(state);result=self.report();self.fresh()
                if all(now-old>=3000 for now,old in zip(clocks,origin)):
                    state=deepcopy(self.state);state['quiet'].append(dict(where=where,first=first_index,last=len(state['frames'])-1))
                    self.save(state);result=self.report();self.fresh();return result
                need(self.now()-started<10);self.settings.sleep(.25)
            need(False)
    def report(self):
        need(self.state is not None);normal,audio,lifecycle,_=self.packets(self.state['frames'][-1]);original=None
        if self.state['originalId'] is not None:original=pages.original(normal['picoAudioPages'],self.state['originalId'])
        current=self.lifetime(self.state['frames'][-1]);native_quiet=[]
        for window in self.state['quiet']:
            if all(self.resource_match(row) is True for row in self.state['frames'][window['first']:window['last']+1]):native_quiet.append(window['where'])
        return dict(phase=self.state['phase'],partialRecipe='normal-muted-start-rejection',fullAudioQualified=False,
            tabletShown=lifecycle['source']['tabletShown'],audioPageCurrent=bool(normal['picoAudioPages']['current']),
            pageAlive=None if original is None else original['pageAlive'],contextAlive=None if original is None else original['contextAlive'],
            inputPeakValuesEnabled=audio['source']['inputPeakValuesEnabled'],
            nativeDeferredFunctorsRetired=None if current is None else lifetime.deferred_retired(current),
            nativeResourceMatchesBaseline=self.resource_match(self.state['frames'][-1]),nativeDeferredQuietWindows=native_quiet,originalQuietWindows=[row['where'] for row in self.state['quiet']],journalsRetained=True)


def run_normal_audio_page(owner):
    """Continue this bounded segment from its own durable originals only.

    Issued normal/controller inputs are only reconciled. A pre-preview-call
    intent gap without any original preview pending/action remains unresolved.
    Every invocation at the closed boundary proves a fresh original quiet window.
    """
    need(isinstance(owner,PicoAudioPageOwner))
    with owner.lock.held():
        owner.load()
        if owner.state is None:owner.prepare()
        for _step in range(20):
            phase=owner.state['phase']
            if phase.endswith('-issued') or phase=='opening':owner.reconcile()
            elif phase=='prepared':owner.tablet()
            elif phase=='tablet-open':owner.open_audio()
            elif phase=='opened':owner.claim_preview()
            elif phase=='claimed':owner.action('mute')
            elif phase=='muted':owner.action('record')
            elif phase=='rejected':owner.action('restore')
            elif phase=='restored':owner.release()
            elif phase=='released':owner.close_page()
            elif phase=='home':
                result=owner.close_tablet()
                return owner.await_deferred() if owner.lifetime(owner.state['frames'][0]) is not None else result
            elif phase=='closed':
                return owner.await_deferred() if owner.lifetime(owner.state['frames'][0]) is not None else owner.quiet('closed')
            else:need(False)
        need(False)
