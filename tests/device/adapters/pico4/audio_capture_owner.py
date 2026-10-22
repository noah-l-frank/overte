"""Normal one-cycle Audio capture with original fixture/start/PCM provenance.

This continuation owns an already claimed normal Audio page. It advertises no
complete capability and never substitutes accepted sink PCM for acoustic input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import stat
import uuid
from adapters.native_feature_observation import decode,exact,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_chat_view import measured_keyboard
from adapters.pico4.audio_page_owner import PicoAudioPageOwner
from adapters.pico4 import audio_pages as pages,audio_settings_source as settings,lifecycle_source as ui
from adapters.recorded_preview_history import accept_history,measured_state,phases
from adapters.recorded_preview_evidence import validate as pcm_packet
from adapters.script_journey.history import pack,unpack
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=2
READS=(1,2)
PHASES=('prepared','start-issued','capturing','cancel-issued','mute-issued','restore-issued','awaiting','terminal','reading','retained')
KINDS=('input','sink')


class PicoAudioCaptureOwner:
    def __init__(self,path,parent,phase_source):
        need(isinstance(parent,PicoAudioPageOwner) and isinstance(phase_source,PhaseFixtureReader)
            and phase_source.area=='audio' and phase_source.run==parent.run)
        self.store,self.parent,self.source=PrivateFeatureState(path),parent,phase_source
        need(self.store.path.parent==parent.store.path.parent and self.store.path.name.startswith('audio-capture-cycle-')
            and self.store.path.name.endswith('.json'))
        self.preview,self.lock,self.run,self.binding=parent.preview,parent.lock,parent.run,parent.binding
        self.disk=self.state=None;self.version=VERSION
        with self.lock.held():self.load()
    def frame(self,row):
        exact(row,{'native','page'});packet=self.parent.raw(row['native'])
        native_packet(packet,packet['requestId'],self.parent.pid,packet['capturedEpochMs'],require_recorded_history=True)
        self.parent.packets(row['page']);return packet
    def validate(self,value):
        fields={'phase','operation','cancelOperation','beforeCycle','start','lastPhase','frames','original','artifacts','quiet'}
        if self.version==2:fields.update(('restoreOperation','terminalSource'))
        exact(value,fields)
        if self.version==2:need(ui.nonce(value['restoreOperation']) and value['restoreOperation'] not in (value['operation'],value['cancelOperation']))
        else:need(value['phase'] not in ('mute-issued','restore-issued'))
        need(value['phase'] in PHASES and ui.nonce(value['operation']) and ui.nonce(value['cancelOperation'])
            and value['operation']!=value['cancelOperation'] and integer(value['beforeCycle'],0,7)
            and type(value['frames']) is list and 1<=len(value['frames'])<=96
            and type(value['quiet']) is list and len(value['quiet'])<=2)
        for source in (value['start'],value['lastPhase']):
            phase_packet(source,run=self.run,area='audio',request=source['requestId'],epoch=source['capturedEpochMs'])
            need(source['active'] and source['activations'])
        start=value['start']['activations'][-1]
        need(start['stimulus']==dict(verb='record-start',inputs={}) and value['lastPhase']['instance']==value['start']['instance']
            and value['lastPhase']['activations'][:len(value['start']['activations'])]==value['start']['activations'])
        previous=None
        normal,audio,lifecycle,_=self.parent.packets(self.parent.state['frames'][-1])
        prior_settings,prior_pages,prior_ui=audio,normal['picoAudioPages'],ui.summary(lifecycle)
        native_instance=self.parent.packets(self.parent.state['frames'][0])[3]['instance']
        for row in value['frames']:
            packet=self.frame(row);voice=packet['audio']['recordedVoice'];accept_history(previous,voice)
            need(packet['instance']==native_instance and voice['cycle'] in (value['beforeCycle'],value['beforeCycle']+1))
            if previous is not None:need(packet['instance']==original_instance and packet['sequence']>original_sequence)
            previous=voice;original_instance,original_sequence=packet['instance'],packet['sequence']
            normal,audio,lifecycle,_=self.parent.packets(row['page'])
            prior_settings=settings.accept(prior_settings,audio);prior_pages=pages.accept(prior_pages,normal['picoAudioPages'])
            prior_ui=ui.accept(prior_ui,ui.summary(lifecycle));self.check(row)
        before=self.frame(value['frames'][0])['audio']['recordedVoice'];need(before['cycle']==value['beforeCycle'] and not before['active'])
        current=self.frame(value['frames'][-1])['audio']['recordedVoice']
        need(current['cycle'] in (value['beforeCycle'],value['beforeCycle']+1))
        if value['phase'] not in ('prepared','start-issued'):need(current['cycle']==value['beforeCycle']+1)
        if current['cycle']>value['beforeCycle']:
            fences=[row for row in value['frames'] if self.frame(row)['audio']['recordedVoice']['cycle']==value['beforeCycle']]
            fence=fences[-1];_,audio,lifecycle,_=self.parent.packets(fence['page'])
            need(current['startedEpochMs']>=max(start['activatedEpochMs'],self.frame(fence)['capturedEpochMs'],audio['capturedEpochMs'],lifecycle['capturedEpochMs']))
        if value['phase'] in ('terminal','reading','retained'):need(not current['active'] and current['event']['phase'] in ('cancelled','completed'))
        termination=value.get('terminalSource')
        if self.version==1 and value['lastPhase']['activations'][-1]['stimulus']['verb']=='record-cancel':
            active=[index for index,row in enumerate(value['frames']) if self.frame(row)['audio']['recordedVoice']['active']]
            need(active);termination=dict(source=value['lastPhase'],fence=active[-1])
        if termination is not None:
            exact(termination,{'source','fence'});source=termination['source']
            phase_packet(source,run=self.run,area='audio',request=source['requestId'],epoch=source['capturedEpochMs'])
            need(source['active'] and source['instance']==value['start']['instance']
                and value['lastPhase']['activations'][:len(source['activations'])]==source['activations']
                and source['activations'][-1]['stimulus'] in (dict(verb='record-cancel',inputs={}),dict(verb='mute',inputs=dict(enabled=True)))
                and integer(termination['fence'],0,len(value['frames'])-1))
            fence=value['frames'][termination['fence']];packet=self.frame(fence);normal,audio,lifecycle,_=self.parent.packets(fence['page'])
            need(packet['audio']['recordedVoice']['active'] and packet['audio']['recordedVoice']['cycle']==value['beforeCycle']+1)
            if not current['active']:
                need(current['event']['publishedEpochMs']>=max(source['activations'][-1]['activatedEpochMs'],packet['capturedEpochMs'],
                    normal['picoAudioPages']['capturedEpochMs'],audio['capturedEpochMs'],lifecycle['capturedEpochMs']))

        need(self.store.path.name==f'audio-capture-cycle-{value["beforeCycle"]+1:02d}.json')
        original=value['original'];need((original is not None)==(value['phase'] in ('reading','retained')))
        if original is not None:
            pcm_packet(original,original['requestId'],self.parent.pid,original['capturedEpochMs'])
            need(original['instance']==original_instance and original['source']['cycle']==current['cycle']
                and original['source']['events']==current['events'] and original['source']['startedEpochMs']==current['startedEpochMs'])
        artifacts=value['artifacts'];need(type(artifacts) is dict and set(artifacts)<=set(KINDS) and (not artifacts or original is not None))
        for kind,record in artifacts.items():self.artifact(record,kind,original,verify=record['phase']=='saved')
        if value['phase']=='retained':need(original is not None and set(artifacts)==set(KINDS) and all(a['phase']=='saved' for a in artifacts.values()))
        for window in value['quiet']:
            exact(window,{'first','last'});need(integer(window['first'],0,len(value['frames'])-1) and integer(window['last'],window['first']+1,len(value['frames'])-1))
            samples=value['frames'][window['first']:window['last']+1];clocks=[self.clocks(row) for row in samples]
            need(all(not self.frame(row)['audio']['recordedVoice']['active'] for row in samples)
                and all(all(0<=now-old<=500 for now,old in zip(b,a)) for a,b in zip(clocks,clocks[1:]))
                and all(now-old>=3000 for now,old in zip(clocks[-1],clocks[0])))
    def load(self):
        self.lock.assert_held();self.parent.load();need(self.parent.state is not None and self.parent.state['phase'] in ('claimed','restored'))
        disk=self.store.read()
        if self.disk is not None:need(disk==self.disk)
        if disk is None:need(self.state is None);return
        exact(disk,{'audioCaptureOwnerVersion','binding','runId','fixtureUrl','payload'})
        need(type(disk['audioCaptureOwnerVersion']) is int and disk['audioCaptureOwnerVersion'] in READS and disk['binding']==self.binding and disk['runId']==self.run and disk['fixtureUrl']==self.source.fixture_url)
        self.version=disk['audioCaptureOwnerVersion']
        value=unpack(disk['payload']);need(len(value)==1);self.validate(value[0]);self.disk,self.state=deepcopy(disk),deepcopy(value[0])
    def save(self,value):
        self.lock.assert_held();need(self.store.read()==self.disk);self.validate(value)
        disk=dict(audioCaptureOwnerVersion=self.version,binding=self.binding,runId=self.run,fixtureUrl=self.source.fixture_url,payload=pack([value]))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(value)
    def capture(self):
        started=self.parent.now();requested=self.parent.settings.clock_ms();packet=self.preview.read()
        raw=self.preview.native.original();native=ui_frame(raw);need(decode(raw)==packet)
        page=self.parent.capture();old=self.parent.anchor
        self.parent.anchor=(started,requested,min(old[2],packet['capturedEpochMs']))
        result=dict(native=native,page=page);self.check(result);return result
    def check(self,row):
        packet=self.frame_unchecked(row);normal,audio,lifecycle,_=self.parent.packets(row['page']);source=audio['source']
        original=pages.original(normal['picoAudioPages'],self.parent.state['originalId'])
        need(normal['open'] and normal['ready'] and normal['picoAudioPages']['current']==original['id'] and original['current']
            and lifecycle['source']['tabletShown'] and not lifecycle['source']['onHomeScreen'] and ui.current_editor(lifecycle) is None
            and source['inputPeakValuesEnabled'] is True and source['native']['previewCycle']==packet['audio']['recordedVoice']['cycle']
            and source['native']['previewActive']==packet['audio']['recordedVoice']['active']
            and source['native']['muted']==packet['audio']['muted']==source['properties']['muted']==source['properties']['mutedHMD']
            and not packet['audio']['recording'] and source['properties']['context']=='VR'
            and measured_keyboard(lifecycle['source']['keyboard']) is False)
        baseline=self.parent.packets(self.parent.state['frames'][0])[1]['source']
        need(original['originalPeakValuesEnabled']==baseline['inputPeakValuesEnabled'])
        need(source['mixerGains']==baseline['mixerGains'] and source['native']['localEcho']==baseline['native']['localEcho']
            and source['native']['serverEcho']==baseline['native']['serverEcho'])
        for key in settings.BOOLEANS+settings.NUMBERS:
            if key not in ('muted','mutedHMD'):need(source['properties'][key]==baseline['properties'][key])
        return packet
    def frame_unchecked(self,row):return self.parent.raw(row['native'])
    def phase(self,verb,inputs=None):
        need(not any(self.store.path.parent.glob('audio-final-*')))
        source=self.source.status(None if self.state is None else self.state['lastPhase'])
        need(source['active'] and source['activations'] and source['activations'][-1]['stimulus']==dict(verb=verb,inputs={} if inputs is None else inputs))
        return source
    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None);source=self.phase('record-start');row=self.capture();voice=self.frame(row)['audio']['recordedVoice']
            need(not voice['active'] and not self.frame(row)['audio']['muted'] and self.preview.owned()['releaseState']=='live')
            cycle=voice['cycle']+1;need(self.store.path.name==f'audio-capture-cycle-{cycle:02d}.json')
            need(not any(self.store.path.parent.glob(f'audio-capture-original-{self.run}-{cycle:02d}-*')))
            self.save(dict(phase='prepared',operation=uuid.uuid4().hex,cancelOperation=uuid.uuid4().hex,beforeCycle=cycle-1,
                start=source,lastPhase=source,frames=[row],original=None,artifacts={},quiet=[],restoreOperation=uuid.uuid4().hex,terminalSource=None));self.parent.fresh()
    def start(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='prepared');source=self.phase('record-start')
            need(source['activations']==self.state['start']['activations'])
            row=self.capture();need(self.frame(row)['audio']['recordedVoice']['cycle']==self.state['beforeCycle'])
            state=deepcopy(self.state);state.update(phase='start-issued',lastPhase=source);state['frames'].append(row);self.save(state);self.parent.fresh()
            self.preview.act(state['operation'],'record-start');return self.reconcile()
    def reconcile(self):
        with self.lock.held():
            self.load();need(self.state['phase'] in ('start-issued','cancel-issued','mute-issued','restore-issued','awaiting'))
            if self.state['phase']!='awaiting':
                operation=self.state['operation'] if self.state['phase']=='start-issued' else self.state['restoreOperation'] if self.state['phase']=='restore-issued' else self.state['cancelOperation']
                verb='record-start' if self.state['phase']=='start-issued' else 'mute' if self.state['phase'] in ('mute-issued','restore-issued') else 'record-cancel'
                owned=self.preview.owned()
                if owned['pending'] is not None:need(owned['pending']['operationId']==operation);self.preview.reconcile();owned=self.preview.owned()
                need(any(row['operationId']==operation and row['verb']==verb for row in owned['actions']))
            row=self.capture();voice=self.frame(row)['audio']['recordedVoice'];need(voice['cycle']==self.state['beforeCycle']+1)
            if self.state['phase'] in ('mute-issued','restore-issued'):
                need(self.frame(row)['audio']['muted']==(self.state['phase']=='mute-issued') and not voice['active']
                    and voice['event']['phase']=='cancelled' and voice['event']['error']=='microphone-muted')
            state=deepcopy(self.state);state['frames'].append(row)
            if voice['active']:need(state['phase']=='start-issued' and voice['event']['phase']=='capturing');state['phase']='capturing'
            else:need(voice['event']['phase'] in ('cancelled','completed'));state['phase']='terminal'
            self.save(state);result=self.report();self.parent.fresh();return result
    def observe(self):
        """A fresh original reading; requested capture counts never set state."""
        with self.lock.held():
            self.load();need(self.state['phase'] in ('capturing','terminal','retained'));row=self.capture()
            voice=self.frame(row)['audio']['recordedVoice'];need(voice['cycle']==self.state['beforeCycle']+1)
            state=deepcopy(self.state);state['frames'].append(row)
            if state['phase']=='capturing' and not voice['active']:
                need(voice['event']['phase'] in ('cancelled','completed'));state['phase']='terminal'
            self.save(state);result=self.report();self.parent.fresh();return result

    def cancel(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='capturing');source=self.phase('record-cancel');row=self.capture()
            voice=self.frame(row)['audio']['recordedVoice'];need(voice['active'] and voice['event']['phase']=='capturing')
            state=deepcopy(self.state);state.update(phase='cancel-issued',lastPhase=source);state['frames'].append(row)
            if self.version==2:state['terminalSource']=dict(source=source,fence=len(state['frames'])-1)
            self.save(state);self.parent.fresh()
            self.preview.act(state['cancelOperation'],'record-cancel');return self.reconcile()
    def mute_interrupt(self):
        with self.lock.held():
            self.load();need(self.version==2 and self.state['phase']=='capturing');source=self.phase('mute',dict(enabled=True));row=self.capture()
            voice=self.frame(row)['audio']['recordedVoice'];need(voice['active'] and voice['event']['phase']=='capturing' and not self.frame(row)['audio']['muted'])
            state=deepcopy(self.state);state.update(phase='mute-issued',lastPhase=source);state['frames'].append(row)
            state['terminalSource']=dict(source=source,fence=len(state['frames'])-1);self.save(state);self.parent.fresh()
            self.preview.act(state['cancelOperation'],'mute',enabled=True);return self.reconcile()
    def restore_mute(self):
        with self.lock.held():
            self.load();need(self.version==2 and self.state['phase']=='terminal');source=self.phase('mute',dict(enabled=False));row=self.capture()
            need(self.frame(row)['audio']['muted'] and not self.frame(row)['audio']['recordedVoice']['active']
                and self.frame(row)['audio']['recordedVoice']['event']['error']=='microphone-muted'
                and any(action['operationId']==self.state['cancelOperation'] and action['verb']=='mute' for action in self.preview.owned()['actions']))
            state=deepcopy(self.state);state.update(phase='restore-issued',lastPhase=source);state['frames'].append(row);self.save(state);self.parent.fresh()
            self.preview.act(state['restoreOperation'],'mute',enabled=False);return self.reconcile()

    def await_completion(self):
        with self.lock.held():
            self.load();need(self.state['phase'] in ('capturing','terminal'));source=self.phase('await-completion');row=self.capture()
            state=deepcopy(self.state);state.update(phase='awaiting',lastPhase=source);state['frames'].append(row);self.save(state);self.parent.fresh()
            self.preview.await_terminal();return self.reconcile()
    def clocks(self,row):
        _,audio,lifecycle,_=self.parent.packets(row['page']);normal=self.parent.raw(row['page']['pages'])
        return [self.frame(row)['capturedEpochMs'],audio['capturedEpochMs'],lifecycle['capturedEpochMs'],normal['picoAudioPages']['capturedEpochMs'],
            *(audio['source'][key] for key in settings.CLOCKS),row['page']['hostMonotonic']*1000]
    def quiet(self):
        with self.lock.held():
            self.load();need(self.state['phase'] in ('terminal','retained'));origin=prior=None;first=None;started=self.parent.now()
            for _ in range(41):
                row=self.capture();voice=self.frame(row)['audio']['recordedVoice'];need(not voice['active'] and voice['capturedBytes']==voice['playedBytes']==0)
                clocks=self.clocks(row)
                if prior is None or any(now-old>500 for now,old in zip(clocks,prior)):origin=clocks;first=len(self.state['frames'])
                prior=clocks;state=deepcopy(self.state);state['frames'].append(row);self.save(state);result=self.report();self.parent.fresh()
                if all(now-old>=3000 for now,old in zip(clocks,origin)):
                    state=deepcopy(self.state);state['quiet'].append(dict(first=first,last=len(state['frames'])-1));self.save(state)
                    result=self.report();self.parent.fresh();return result
                need(self.parent.now()-started<10);self.parent.settings.sleep(.25)
            need(False)
    def artifact(self,value,kind,original,*,verify):
        exact(value,{'name','phase','bytes','sha256','file'});need(kind in KINDS and original is not None)
        source=original['source'];name=f'audio-capture-original-{self.run}-{source["cycle"]:02d}-{kind}.pcm16le'
        need(value['name']==name and value['phase'] in ('planned','opened','saved')
            and value['bytes']==source[kind]['bytes'] and type(value['bytes']) is int and value['sha256']==source[kind]['sha256'])
        path=self.store.path.with_name(name)
        if value['phase']=='planned':need(value['file'] is None)
        else:
            need(type(value['file']) is list and len(value['file'])==8 and all(integer(v,0,2**64-1) for v in value['file']))
            if verify:self.read_file(value)
        return path
    @staticmethod
    def signature(info):
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600)
        return [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns]
    def read_file(self,value):
        path=self.store.path.with_name(value['name']);descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as stream:
            before=self.signature(os.fstat(stream.fileno()));need(before==value['file'] and before==self.signature(path.lstat()))
            raw=stream.read(32*1024*1024+1)
            need(self.signature(os.fstat(stream.fileno()))==before==self.signature(path.lstat())
                and len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
        return raw
    def retain_originals(self):
        with self.lock.held():
            self.load();need(self.state['phase']=='terminal');self.quiet();packet,raw=self.preview.originals()
            row=self.capture();need(packet['source']['events']==self.frame(row)['audio']['recordedVoice']['events'])
            started,requested,captured=self.parent.anchor;self.parent.anchor=(started,requested,min(captured,packet['capturedEpochMs']))
            state=deepcopy(self.state);state.update(phase='reading',original=packet);state['frames'].append(row);self.save(state);self.parent.fresh()
            for kind in KINDS:
                source=packet['source'][kind];value=dict(name=f'audio-capture-original-{self.run}-{packet["source"]["cycle"]:02d}-{kind}.pcm16le',
                    phase='planned',bytes=source['bytes'],sha256=source['sha256'],file=None)
                need(type(raw[kind]) is bytes and len(raw[kind])==value['bytes'] and hashlib.sha256(raw[kind]).hexdigest()==value['sha256'])
                state=deepcopy(self.state);state['artifacts'][kind]=value;self.save(state);self.parent.fresh()
                path=self.artifact(value,kind,packet,verify=False);descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(descriptor,'wb') as stream:
                    value=dict(value,phase='opened',file=self.signature(os.fstat(stream.fileno())))
                    state=deepcopy(self.state);state['artifacts'][kind]=value;self.save(state);self.parent.fresh()
                    need(stream.write(raw[kind])==len(raw[kind]));stream.flush();os.fsync(stream.fileno())
                    value=dict(value,phase='saved',file=self.signature(os.fstat(stream.fileno())))
                need(self.read_file(value)==raw[kind]);state=deepcopy(self.state);state['artifacts'][kind]=value;self.save(state);self.parent.fresh()
            state=deepcopy(self.state);state['phase']='retained';self.save(state);result=self.report();self.parent.fresh();return result
    def report(self):
        need(self.state is not None);packet=self.frame(self.state['frames'][-1]);measured=measured_state(packet)
        return dict(phase=self.state['phase'],cycle=packet['audio']['recordedVoice']['cycle'],state=measured,
            sourceTicket=self.state['start']['activations'][-1]['ticket'],originalPcmRetained=self.state['phase']=='retained',
            nativeQuietWindows=len(self.state['quiet']),independentAcousticObserved=False,fullAudioQualified=False,journalsRetained=True)


def ui_frame(raw):
    need(type(raw) is str);return dict(raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest())
