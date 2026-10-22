"""One-send normal Audio HOME/return with original OS and native cancellation.

No Qt source is queried while the owning process is backgrounded. This proves
this Audio recipe boundary, not continuous Chat/editor/keyboard hidden history.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.native_feature_observation import LIMIT,decode,exact,integer,need,number,validate as native_packet
from adapters.native_chat_view import measured_keyboard
from adapters.pico4 import audio_pages as pages,audio_settings_source as settings
from adapters.pico4.navigation import validate_snapshot
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.audio_capture_owner import PicoAudioCaptureOwner
from adapters.pico4 import lifecycle_source as ui
from adapters.script_journey.history import canonical,pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=1
PHASES=('prepared','home-issued','background-observed','resume-issued','returned','quiet')
ERRORS=('backgrounded','lifecycle-stopped','input-or-lifecycle-changed')


def sha(value):return hashlib.sha256(canonical(value)).hexdigest()


class PicoAudioBackground:
    def __init__(self,path,run,binding,lock,os_status,os_input,runtime,phase_source,*,monotonic=time.monotonic,sleep=time.sleep):
        need(ui.nonce(run) and isinstance(lock,ScriptSourceLock) and all(callable(f) for f in (os_status,os_input,runtime,monotonic,sleep)))
        self.store,self.run,self.binding,self.lock=PrivateFeatureState(path),run,deepcopy(context(binding)),lock
        need(self.store.path.parent==lock.path.parent and lock.path.name=='script-sources.lock')
        self.os_status,self.os_input,self.runtime_factory=os_status,os_input,runtime;self.monotonic,self.sleep=monotonic,sleep
        need(isinstance(phase_source,PhaseFixtureReader) and phase_source.run==run and phase_source.area=='audio')
        self.source=phase_source
        self.owner=None;self.disk=self.state=self.last_clock=None
        with lock.held():self.disk=self.store.read();self.load()
    def bound(self):
        self.lock.assert_held();now=self.monotonic()
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock) and self.store.read()==self.disk)
        self.last_clock=now
        if self.state is not None:
            clocks=[self.state['before']['page']['hostMonotonic'],*(row['hostMonotonic'] for row in self.state['background']),
                *(row['page']['hostMonotonic'] for row in self.state['quiet'])]
            need(now>=max(clocks))
            parent=PrivateFeatureState(self.store.path.with_name('audio-page-owner.json')).read()
            need(parent is not None and sha(parent)==self.state['parentSha256'])
        return now
    @staticmethod
    def os_packet(value,binding):
        exact(value,{'binding','foreground','running'})
        need(context(value['binding'])==binding and type(value['foreground']) is bool and value['running'] is True)
        return value
    def status(self):
        self.bound();packet=self.os_status(deepcopy(self.binding));self.os_packet(packet,self.binding);self.bound();return deepcopy(packet)
    def phase_anchor(self):
        return self.bound(),self.source.epoch_ms()
    def phase_fence(self,anchor,*,owner=None):
        # This HTTP source is independent of Qt and remains available in the
        # background. Recheck the exact original ticket after durable intent,
        # never reconstruct a live UI owner just to read fixture metadata.
        started,requested=anchor;original=self.state['fixturePhase']
        # Native/SDK guards can themselves advance the independent fixture.
        # Read its exact original history after the final such guard.
        if owner is not None:owner.parent.fresh()
        current=self.source.status(original)
        need(current['active'] and all(current[key]==original[key] for key in
            ('instance','createdEpochMs','activations')))
        epoch=self.source.epoch_ms();completed=self.bound()
        need(number(requested,1,1e15) and number(epoch,requested,1e15) and completed>=started
            and -250<=epoch-current['capturedEpochMs']
            and max(epoch-current['capturedEpochMs'],requested-current['capturedEpochMs']+(completed-started)*1000)<=1500)
        return current
    def load(self):
        self.bound();disk=self.store.read()
        if disk is None:need(self.state is None);return
        exact(disk,{'audioBackgroundOwnerVersion','binding','runId','payload'})
        need(type(disk['audioBackgroundOwnerVersion']) is int and disk['audioBackgroundOwnerVersion']==VERSION
            and disk['binding']==self.binding and disk['runId']==self.run)
        value=unpack(disk['payload']);need(len(value)==1);state=value[0];self.validate(state)
        self.disk,self.state=deepcopy(disk),deepcopy(state);self.bound()
    def frame(self,row):
        exact(row,{'native','page'})
        def original(value,limit=LIMIT):
            exact(value,{'raw','sha256'});need(type(value['raw']) is str and len(value['raw'].encode())<=limit and hashlib.sha256(value['raw'].encode()).hexdigest()==value['sha256'])
            return decode(value['raw'])
        packet=original(row['native']);pid=int(self.binding['processIdentity'].split(':')[0])
        native_packet(packet,packet['requestId'],pid,packet['capturedEpochMs'],require_recorded_history=True)
        page=row['page'];exact(page,{'pages','settings','ui','empty','hostMonotonic'});need(page['empty'] is None and number(page['hostMonotonic'],0,1e15))
        normal=original(page['pages'],pages.LIMIT);audio=original(page['settings']);lifecycle=original(page['ui'])
        validate_snapshot(normal,pid,normal['updatedEpochMs']);need(normal['bridgeId']==self.binding['sessionId'])
        need(normal.get('picoAudioPageVersion')==1);pages.validate(normal['picoAudioPages'],normal['updatedEpochMs'])
        settings.validate(audio,audio,pid,audio['capturedEpochMs']);ui.validate(lifecycle,lifecycle,pid,lifecycle['capturedEpochMs'])
        need(audio['runId']==lifecycle['runId']==self.run);return packet,normal,audio,lifecycle
    def clocks(self,row):
        packet,normal,audio,lifecycle=self.frame(row)
        return [packet['capturedEpochMs'],normal['picoAudioPages']['capturedEpochMs'],audio['capturedEpochMs'],lifecycle['capturedEpochMs'],
            *(audio['source'][key] for key in settings.CLOCKS),row['page']['hostMonotonic']*1000]
    def validate(self,state):
        exact(state,{'phase','cycle','parentSha256','captureArchive','fixturePhase','before','background','backgroundFirst','foreground','after','quiet'})
        need(state['phase'] in PHASES and integer(state['cycle'],1,8) and self.store.path.name==f'audio-background-cycle-{state["cycle"]:02d}.json'
            and type(state['parentSha256']) is str and len(state['parentSha256'])==64 and type(state['captureArchive']) is dict
            and type(state['background']) is list and len(state['background'])<=51 and type(state['quiet']) is list and len(state['quiet'])<=25)
        phase=state['fixturePhase'];phase_packet(phase,run=self.run,area='audio',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        need(phase['active'] and phase['activations'][-1]['stimulus']==dict(verb='background-resume',inputs={}))
        rank=PHASES.index(state['phase']);need(rank<2 or state['background'])
        previous=None
        for value in state['background']:
            exact(value,{'status','hostMonotonic'});self.os_packet(value['status'],self.binding)
            need(value['status']['foreground'] is False and number(value['hostMonotonic'],0,1e15)
                and (previous is None or value['hostMonotonic']>=previous));previous=value['hostMonotonic']
        if state['background']:
            need(integer(state['backgroundFirst'],0,len(state['background'])-1));window=state['background'][state['backgroundFirst']:]
            need(all(0<=b['hostMonotonic']-a['hostMonotonic']<=.5 for a,b in zip(window,window[1:])))
            if rank>=3:need(window[-1]['hostMonotonic']-window[0]['hostMonotonic']>=.25)
        else:need(state['backgroundFirst'] is None)
        if state['foreground'] is not None:self.os_packet(state['foreground'],self.binding);need(state['foreground']['foreground'])
        need(rank<4 or state['foreground'] is not None and state['after'] is not None)
        before=self.frame(state['before']);need(before[0]['audio']['recordedVoice']['active']
            and before[0]['audio']['recordedVoice']['cycle']==state['cycle'] and before[0]['audio']['recordedVoice']['event']['phase']=='capturing')
        if state['after'] is not None:self.returned_frame(state,state['after'])
        previous=first=None
        for row in state['quiet']:
            self.returned_frame(state,row);clocks=self.clocks(row)
            if first is None:first=clocks
            if previous is not None:need(all(0<=now-old<=500 for now,old in zip(clocks,previous)))
            previous=clocks
        if state['phase']=='quiet':need(first is not None and all(now-old>=3000 for now,old in zip(previous,first)))
    def save(self,state):
        self.bound();self.validate(state);disk=dict(audioBackgroundOwnerVersion=VERSION,runId=self.run,binding=self.binding,payload=pack([state]))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(state);self.load()
    def live(self):
        need(self.status()['foreground'])
        if self.owner is None:
            actual=self.runtime_factory();need(isinstance(actual,PicoAudioCaptureOwner) and actual.binding==self.binding and actual.run==self.run
                and actual.lock is self.lock and actual.source is self.source and actual.store.path.parent==self.store.path.parent)
            self.owner=actual
        return self.owner
    def capture_store(self):return PrivateFeatureState(self.store.path.with_name(f'audio-capture-cycle-{self.state["cycle"]:02d}.json'))
    def archives(self):
        self.bound();need(self.capture_store().read()==self.state['captureArchive'])
    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None);owner=self.live();owner.load();need(owner.state['phase']=='capturing')
            phase=owner.phase('background-resume');owner.observe();row=deepcopy(owner.state['frames'][-1]);packet=owner.frame(row)
            need(packet['audio']['recordedVoice']['active'] and packet['audio']['recordedVoice']['event']['phase']=='capturing'
                and not packet['audio']['muted'])
            cycle=packet['audio']['recordedVoice']['cycle'];need(self.store.path.name==f'audio-background-cycle-{cycle:02d}.json')
            parent=owner.parent.store.read()
            state=dict(phase='prepared',cycle=cycle,parentSha256=sha(parent),captureArchive=owner.store.read(),fixturePhase=phase,
                before=row,background=[],backgroundFirst=None,foreground=None,after=None,quiet=[])
            self.save(state);owner.parent.fresh()
    def home(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='prepared');self.archives();owner=self.live();phase=owner.phase('background-resume')
            need(phase['activations']==self.state['fixturePhase']['activations']);owner.observe();row=deepcopy(owner.state['frames'][-1]);packet=owner.frame(row)
            need(packet['audio']['recordedVoice']['active'] and packet['audio']['recordedVoice']['event']['phase']=='capturing')
            anchor=self.phase_anchor()
            state=deepcopy(self.state);state.update(phase='home-issued',captureArchive=owner.store.read(),before=row,fixturePhase=phase);self.save(state)
            self.phase_fence(anchor,owner=owner)
            self.os_input('lifecycle.background',deepcopy(self.binding),
                before_input=lambda:self.phase_fence(anchor,owner=owner));return self.observe_background()
    def observe_background(self):
        with self.lock.held():
            self.load();need(self.state['phase'] in ('home-issued','background-observed'));self.archives();started=self.bound()
            for attempt in range(51):
                packet=self.status();now=self.bound()
                if packet['foreground'] is False:
                    state=deepcopy(self.state)
                    if not state['background'] or now-state['background'][-1]['hostMonotonic']>.5:state['backgroundFirst']=len(state['background'])
                    state['background'].append(dict(status=packet,hostMonotonic=now));state['phase']='background-observed';self.save(state)
                    if now-state['background'][state['backgroundFirst']]['hostMonotonic']>=.25:return self.report()
                else:need(not self.state['background'])
                need(self.bound()-started<5 and attempt<50);self.sleep(.125)
            need(False)
    def resume(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='background-observed');self.archives();need(not self.status()['foreground'])
            need(self.state['background'][-1]['hostMonotonic']-self.state['background'][self.state['backgroundFirst']]['hostMonotonic']>=.25)
            anchor=self.phase_anchor()
            state=deepcopy(self.state);state['phase']='resume-issued';self.save(state);self.phase_fence(anchor)
            self.os_input('app.launch',deepcopy(self.binding),before_input=lambda:self.phase_fence(anchor));return self.reconcile()
    def adopt_observation(self,owner,original):
        # A crash after the owned read-only observation may leave a longer
        # actual capture journal. Adopt only that exact immutable prefix, never
        # an ordinary action or a changed original source/ticket/operation.
        before,after=unpack(original['payload'])[0],unpack(owner.store.read()['payload'])[0]
        need(all(owner.store.read()[key]==original[key] for key in original if key!='payload')
            and all(after[key]==value for key,value in before.items() if key not in ('phase','frames'))
            and before['phase'] in ('capturing','terminal') and after['phase'] in ('capturing','terminal')
            and after['frames'][:len(before['frames'])]==before['frames'] and len(after['frames'])>=len(before['frames']))
    def returned_frame(self,state,row):
        before,old_normal,old_audio,old_ui=self.frame(state['before']);after,normal,audio,lifecycle=self.frame(row)
        a,b=before['lifecycle'],after['lifecycle'];voice=after['audio']['recordedVoice']
        need(before['instance']==after['instance'] and after['sequence']>before['sequence']
            and b['backgrounds']>=a['backgrounds']+1 and b['activations']>=a['activations']+1 and b['launches']==a['launches']
            and voice['cycle']==state['cycle'] and not voice['active'] and voice['capturedBytes']==voice['playedBytes']==0
            and voice['event']['phase']=='cancelled' and voice['event']['error'] in ERRORS and after['audio']['muted']==before['audio']['muted'])
        need(voice['event']['publishedEpochMs']>=max(before['capturedEpochMs'],old_audio['capturedEpochMs'],old_ui['capturedEpochMs'],
            state['fixturePhase']['activations'][-1]['activatedEpochMs']))
        if state['after'] is not None:need(after['lifecycle']==self.frame(state['after'])[0]['lifecycle'])
        pages.accept(old_normal['picoAudioPages'],normal['picoAudioPages']);settings.accept(old_audio,audio);ui.accept(ui.summary(old_ui),ui.summary(lifecycle))
        need(normal['picoAudioPages']['current']==old_normal['picoAudioPages']['current'] and normal['open'] and normal['ready']
            and audio['source']['properties']==old_audio['source']['properties'] and audio['source']['mixerGains']==old_audio['source']['mixerGains']
            and audio['source']['inputPeakValuesEnabled']==old_audio['source']['inputPeakValuesEnabled']
            and lifecycle['source']['tabletShown'] and not lifecycle['source']['onHomeScreen']
            and ui.current_editor(lifecycle) is None and measured_keyboard(lifecycle['source']['keyboard']) is False)
        return after
    def returned(self,owner,row):return self.returned_frame(self.state,row)
    def reconcile(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='resume-issued');anchor=self.phase_anchor();self.phase_fence(anchor)
            status=self.status();need(status['foreground']);owner=self.live()
            self.adopt_observation(owner,self.state['captureArchive']);owner.observe();row=deepcopy(owner.state['frames'][-1]);self.returned(owner,row)
            state=deepcopy(self.state);state.update(phase='returned',foreground=status,after=row,captureArchive=owner.store.read());self.save(state)
            result=self.report();self.phase_fence(anchor,owner=owner);return result
    def quiet(self):
        with self.lock.held():
            self.load();need(self.state['phase'] in ('returned','quiet'));self.archives();owner=self.live();origin=previous=None;started=self.bound()
            for attempt in range(25):
                anchor=self.phase_anchor();self.phase_fence(anchor)
                owner.observe();row=deepcopy(owner.state['frames'][-1]);self.returned(owner,row);clocks=owner.clocks(row)
                state=deepcopy(self.state)
                if previous is None or any(now-old>.5*1000 for now,old in zip(clocks,previous)):origin=clocks;state['quiet']=[]
                previous=clocks;state['quiet'].append(row);state['captureArchive']=owner.store.read();state['phase']='returned';self.save(state)
                result=self.report();self.phase_fence(anchor,owner=owner)
                if all(now-old>=3000 for now,old in zip(clocks,origin)):
                    state=deepcopy(self.state);state['phase']='quiet';self.save(state);result=self.report();self.phase_fence(anchor,owner=owner);return result
                need(self.bound()-started<6 and attempt<24);self.sleep(.25)
            need(False)
    def report(self):
        need(self.state is not None)
        return dict(phase=self.state['phase'],cycle=self.state['cycle'],backgroundObserved=bool(self.state['background']),
            nativeCancellationObserved=self.state['after'] is not None,quiet=self.state['phase']=='quiet',
            hiddenEditorHistoryObserved=False,fullAudioQualified=False,journalsRetained=True)
