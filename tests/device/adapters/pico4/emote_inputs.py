"""Durable ordinary Pico Emote inputs; independent effect proofs stay mandatory.

The private archival/input architecture is selected from a fixed reviewed Phone
commit. Actual Pico VR pointer and OpenXR tablet transport replace Phone SDK/UI.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
from types import SimpleNamespace
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import control_id,snapshot,same_reference
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import validate as phase_packet
from adapters.pico4.emote_sources import PicoEmoteSources
from adapters.emote_originals import EmoteOriginals,BLOCK
from adapters.script_journey.history import pack,unpack,same,canonical
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from openxr_input.adapter_session import PicoOpenXrAdapterSession,PROFILE_PATH
from openxr_input.controller_protocol import validate_envelope

VERSION=2
PROFILE=json.loads(PROFILE_PATH.read_text())
MAX_INPUTS=256
VERBS={'open','play','sit','override','cancel','wait-complete','close'}


class PicoEmoteInputTransport:
    """One-send original Pico controller/Qt primitives with durable ownership."""
    @staticmethod
    def ui(frame):return PicoEmoteSources.ui(frame)

    def reference(self):
        need(self.source.frames and self.source.state['phase']=='ready')
        return dict(revision=len(self.source.frames),sha256=hashlib.sha256(canonical(self.source.frames[-1])).hexdigest())

    def original(self,reference):
        exact(reference,{'revision','sha256'})
        need(integer(reference['revision'],1,len(self.source.frames)))
        frame=self.source.frames[reference['revision']-1]
        need(reference['sha256']==hashlib.sha256(canonical(frame)).hexdigest());return frame

    @staticmethod
    def qt_intent(value):
        exact(value,{'controlId','action','sequence','instance','generation','direction','original'})
        original=snapshot(value['original']);scope=original['scope'];identifier=value['controlId']
        need(control_id(identifier) and identifier!='emote.page'
            and type(value['sequence']) is int and value['sequence']==scope['sequence']+1
            and value['instance']==scope['instance'] and value['generation']==scope['generation']
            and value['action']==('scroll' if identifier=='emote.grid' else 'activate')
            and (value['direction'] in ('up','down') if identifier=='emote.grid' else value['direction'] is None))
        rows=[row for row in original['controls'] if row['id']==identifier]
        need(original['open'] and original['ready'] and len(rows)==1 and rows[0]['enabled'] and rows[0]['inputReady'])
        return original

    @classmethod
    def qt_receipt(cls,intent,after):
        before=cls.qt_intent(intent);snapshot(after);left,right=before['scope'],after['scope']
        need(all(left[key]==right[key] for key in ('instance','generation','processId'))
            and right['sequence']==intent['sequence'] and right['sourceSequence']>left['sourceSequence']
            and right['elapsedMs']>=left['elapsedMs'] and right['capturedEpochMs']>=left['capturedEpochMs'])

    @staticmethod
    def same_ui_before_input(before,after):
        left,right=snapshot(before)['scope'],snapshot(after)['scope']
        need(all(left[key]==right[key] for key in ('instance','generation','processId','sequence'))
            and right['sourceSequence']>left['sourceSequence'] and right['elapsedMs']>=left['elapsedMs']
            and right['capturedEpochMs']>=left['capturedEpochMs'])

    def capture(self):
        started=self.source.monotonic();device=self.source.clock_ms();host=self.source.phase.epoch_ms()
        frame=self.source.read();self.active(self.state['current']['call'],frame['phaseAfter'])
        self.anchor=(started,device,host,frame);return self.reference()

    def host_fresh(self):
        need(self.anchor is not None);started,device,host,frame=self.anchor;now=self.source.monotonic()
        need(number(now,started,started+1.5))
        fresh(frame['group']['rootsBefore']['requestedEpochMs'],device+math.ceil((now-started)*1000))
        fresh(frame['phaseBefore']['capturedEpochMs'],host+math.ceil((now-started)*1000))

    def fresh_input(self):
        self.bound();need(self.anchor is not None);frame=self.anchor[3]
        phase=self.source.phase.status(frame['phaseAfter']);self.active(self.state['current']['call'],phase)
        need(same(phase['activations'],frame['phaseAfter']['activations']));self.host_fresh()
        self.bound();clock=self.source.clock_ms();self.host_fresh()
        fresh(frame['group']['rootsBefore']['requestedEpochMs'],clock)

    def intent(self,value):
        current=self.state['current'];need(current['phase']=='acting' and len(current['intents'])<64);self.qt_intent(value)
        barrier=self.capture();frame=self.original(barrier)
        same_reference(value['original'],self.ui(frame),value['controlId']);provider=frame['phaseAfter']
        if value['controlId'].startswith('emote.play.') and self.cancelling(current):self.cancel_barrier(frame,value)
        self.active(current['call'],provider)
        current['intents'].append(dict(kind='qt',input=deepcopy(value),provider=deepcopy(provider),barrier=barrier,after=None))
        current['phase']='issuing';self.save();self.fresh_input()

    def cancel_barrier(self,frame,value):
        pages=[row for row in value['original']['controls'] if row['id']=='emote.page']
        need(len(pages)==1 and pages[0]['activeName'] and value['controlId']=='emote.play.'+pages[0]['activeName']
            and frame['group']['native']['animation']['overrideActive'] is True)

    def receipt(self,value):
        exact(value,{'intent','after'});current=self.state['current'];need(current['phase']=='issuing')
        item=current['intents'][-1];need(item['kind']=='qt' and item['after'] is None and same(item['input'],value['intent']))
        self.qt_receipt(value['intent'],value['after']);item['after']=deepcopy(value['after'])
        current['phase']='acting';self.save()

    def controller(self,identifier):
        current=self.state['current'];need(identifier in ('tablet.open','tablet.close')
            and current['phase']=='acting' and len(current['intents'])<64)
        before=self.capture();need(self.ui(self.original(before))['open']==(identifier=='tablet.close'))
        item=dict(kind='controller',controlId=identifier,before=before,after=None,stream=dict(envelope=None,neutral=None));current['intents'].append(item)
        current['phase']='issuing';self.save();self.fresh_input()
        def intent(envelope):
            need(item['stream']['envelope'] is None);self.stream_packet(item,envelope)
            item['stream']['envelope']=deepcopy(envelope);self.persist(host_only=True)
        self.controller_session.stage(self.binding['processIdentity'],identifier,dict(holdMilliseconds=1000),intent=intent)
        neutral=self.controller_session.require_owned_neutral(self.binding['processIdentity'],item['stream']['envelope'])
        PicoLifecycleBack.neutral(neutral,item['stream']['envelope'],self.ui(self.original(before))['scope']['capturedEpochMs'])
        fresh(neutral['updatedEpochMs'],self.source.clock_ms())
        item['stream']['neutral']=deepcopy(neutral);self.save()
        after=self.capture();need(self.ui(self.original(after))['open']==(identifier=='tablet.open'))
        need(neutral['updatedEpochMs']<=self.ui(self.original(after))['scope']['capturedEpochMs']+250)
        item['after']=after;current['phase']='acting';self.save()

    def input_chain(self,row,call):
        if row['before'] is not None:
            first=self.original(row['before']);self.active(call,first['phaseAfter'])
            previous_ui,previous_provider=self.ui(first),first['phaseAfter']
        else:need(row['phase']=='acting' and not row['intents'])
        pending=0
        for index,item in enumerate(row['intents']):
            need(type(item) is dict and item.get('kind') in ('qt','controller'))
            if item['kind']=='qt':
                exact(item,{'kind','input','provider','barrier','after'});self.qt_intent(item['input']);self.active(call,item['provider'])
                self.same_ui_before_input(previous_ui,item['input']['original'])
                phase_packet(item['provider'],run=self.run,area='emotes',request=item['provider']['requestId'],
                    epoch=item['provider']['capturedEpochMs'],previous=previous_provider)
                frame=self.original(item['barrier']);self.active(call,frame['phaseAfter'])
                same_reference(item['input']['original'],self.ui(frame),item['input']['controlId'])
                need(same(frame['phaseAfter'],item['provider']))
                if item['after'] is not None:
                    self.qt_receipt(item['input'],item['after']);previous_ui=item['after']
                previous_provider=item['provider']
            else:
                exact(item,{'kind','controlId','before','after','stream'})
                need(item['controlId'] in ('tablet.open','tablet.close'))
                frame=self.original(item['before']);self.active(call,frame['phaseAfter'])
                self.same_ui_before_input(previous_ui,self.ui(frame))
                phase_packet(frame['phaseAfter'],run=self.run,area='emotes',request=frame['phaseAfter']['requestId'],
                    epoch=frame['phaseAfter']['capturedEpochMs'],previous=previous_provider)
                need(self.ui(frame)['open']==(item['controlId']=='tablet.close'))
                exact(item['stream'],{'envelope','neutral'});stream=item['stream']
                if stream['envelope'] is not None:self.stream_packet(item,stream['envelope'])
                else:need(stream['neutral'] is None)
                if stream['neutral'] is not None:
                    need(stream['envelope'] is not None);PicoLifecycleBack.neutral(stream['neutral'],stream['envelope'],self.ui(frame)['scope']['capturedEpochMs'])
                if item['after'] is not None:
                    need(stream['neutral'] is not None)
                    after=self.original(item['after']);self.active(call,after['phaseAfter'])
                    need(item['after']['revision']>item['before']['revision']
                        and self.ui(after)['open']==(item['controlId']=='tablet.open'))
                    self.controller_receipt(self.ui(frame),self.ui(after));previous_ui=self.ui(after)
                    previous_provider=after['phaseAfter']
            if item['after'] is None:pending+=1;need(index==len(row['intents'])-1)
        need(pending==(1 if row['phase']=='issuing' else 0))
        plays=[item for item in row['intents'] if item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.')]
        return plays

    @staticmethod
    def controller_receipt(before,after):
        left,right=snapshot(before)['scope'],snapshot(after)['scope']
        need(before['open'] is not after['open']
            and all(left[key]==right[key] for key in ('instance','processId','sequence'))
            and left['generation']!=right['generation'] and right['sourceSequence']>left['sourceSequence']
            and right['elapsedMs']>=left['elapsedMs'] and right['capturedEpochMs']>=left['capturedEpochMs'])

    def cancelling(self,current):
        return current['call']['verb']=='cancel'


class PicoEmoteInputs(PicoEmoteInputTransport):
    def __init__(self,source,store,controls,tablet,session,*,controller):
        need(isinstance(source,PicoEmoteSources) and source.role=='primary');source.lock.assert_held()
        need(isinstance(store,PrivateFeatureState) and store.path!=source.store.path
            and callable(controls) and isinstance(tablet,PicoScriptIO) and callable(session) and callable(controller))
        self.source,self.lock,self.controls,self.tablet,self.session=source,source.lock,controls,tablet,session
        self.run,self.fixture_url,self.binding=source.run,source.phase.fixture_url,source.binding
        self.store=store
        self.controller_factory,self._controller=controller,None;self.anchor=None
        self.previous=self.store.read();self.state=dict(history=[],current=None)
        self.history_state=dict(count=0,manifests=[],pendingArchive=None)
        self.history_store=EmoteOriginals(source.artifact_root,self.binding,self.run,'primary',source.guard,
            self.archive_intent,kind='inputs',monotonic=source.monotonic)
        self.started=self.clock=None;self.failed=False
        if self.previous is not None:
            try:self.state,self.history_state=self.decode(self.previous)
            except (KeyError,TypeError,ValueError,OSError):raise NativeUIError('Original Emote input journal is invalid') from None

    @property
    def controller_session(self):
        if self._controller is None:
            value=self.controller_factory();need(isinstance(value,PicoOpenXrAdapterSession));self._controller=value
        return self._controller

    @staticmethod
    def stream_packet(item,value):
        validate_envelope(value,PROFILE)
        need(value['commands']==[dict(id=item['controlId'].replace('.','-')+'-'+str(value['sequence']),
            operation=item['controlId'],arguments=dict(holdMilliseconds=1000))])

    @classmethod
    def archive(cls,value,source_header,*,phase,artifact_root,binding,guard,monotonic=time.monotonic):
        """Replay original input files against original primary sources only.

        No adapter, UI, transport, lock owner or usable input method is created.
        The returned decoded data is historical and retains unfinished inputs.
        """
        need(type(source_header) is dict and source_header.get('role')=='primary' and callable(guard) and callable(monotonic))
        started=monotonic();need(number(started,0,1e15));clock=started
        def bound():
            nonlocal clock
            need(guard() is not False);now=monotonic();need(number(now,clock,1e15) and now-started<5);clock=now
        bound()
        _state,frames=PicoEmoteSources.archive(source_header,phase=phase,artifact_root=artifact_root,binding=binding,
            guard=bound,monotonic=monotonic)
        scope=object.__new__(cls);scope.run,scope.fixture_url,scope.binding=phase.run,phase.fixture_url,deepcopy(context(binding))
        scope.source=SimpleNamespace(artifact_root=artifact_root,frames=frames,historical=True)
        scope.history_store=EmoteOriginals(artifact_root,binding,phase.run,'primary',bound,
            lambda *_args:need(False),kind='inputs',monotonic=monotonic)
        result=deepcopy(scope.decode(value));bound();return result

    def active(self,call,status):
        phase_packet(status,run=self.run,area='emotes',request=status['requestId'],epoch=status['capturedEpochMs'])
        need(status['active'] and status['activations'])
        row=status['activations'][-1]
        need(row['ticket']==call['ticket'] and row['stimulus']['verb']==call['verb']
            and same(row['stimulus']['inputs'],call['inputs']))

    def row(self,row):
        exact(row,{'call','phase','before','intents','idleReset'})
        call=arguments('feature.emotes.act',row['call'])
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url and call['verb'] in VERBS
            and row['phase'] in ('acting','issuing','acknowledged') and type(row['intents']) is list and len(row['intents'])<=64)
        plays=self.input_chain(row,call)
        if call['verb'] in ('play','sit','override','cancel'):
            need(len(plays)<=1)
            if row['phase']=='acknowledged':need(len(plays)==1 or call['verb']=='cancel' and row['idleReset'] is not None)
            if plays:
                if call['verb']=='cancel':
                    pages=[item for item in plays[0]['input']['original']['controls'] if item['id']=='emote.page']
                    need(len(pages)==1 and pages[0]['activeName'] and plays[0]['input']['controlId']=='emote.play.'+pages[0]['activeName'])
                else:need(plays[0]['input']['controlId']=='emote.play.'+('Sit' if call['verb']=='sit' else call['inputs']['name']))
        else:need(not plays)
        if row['idleReset'] is not None:
            need(call['verb']=='cancel' and not plays);frame=self.original(row['idleReset']);self.active(call,frame['phaseAfter'])
            pages=[item for item in self.ui(frame)['controls'] if item['id']=='emote.page']
            need(row['before'] is not None and row['idleReset']['revision']>row['before']['revision']
                and self.ui(frame)['open'] and self.ui(frame)['ready'] and len(pages)==1 and pages[0]['activeName']==''
                and frame['group']['native']['animation']['overrideActive'] is False)
        if call['verb']=='wait-complete':need(not row['intents'])
        if row['phase']=='acknowledged':need(row['before'] is not None)
        return row

    def decode(self,value):
        exact(value,{'picoEmoteInputsVersion','runId','fixtureUrl','binding','artifactRoot','payload'})
        need(type(value['picoEmoteInputsVersion']) is int and value['picoEmoteInputsVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and same(context(value['binding']),self.binding)
            and value['artifactRoot']==str(self.source.artifact_root))
        rows=unpack(value['payload']);need(len(rows)==1);stored=rows[0];exact(stored,{'historyCount','manifests','pendingArchive','current'})
        need(integer(stored['historyCount'],0,MAX_INPUTS) and (stored['current'] is None or stored['historyCount']<MAX_INPUTS))
        history=self.history_store.restore(stored['manifests'],stored['historyCount'])
        state=dict(history=history,current=stored['current']);tickets=set();last_stream=None
        for row in state['history']+([state['current']] if state['current'] is not None else []):
            self.row(row);need(row['call']['ticket'] not in tickets);tickets.add(row['call']['ticket'])
            for item in row['intents']:
                if item['kind']=='controller' and item['stream']['envelope'] is not None:
                    stream=item['stream']['envelope']
                    if last_stream is not None:need(stream['sessionNonce']==last_stream['sessionNonce'] and stream['sequence']>last_stream['sequence'])
                    last_stream=stream
        need(all(row['phase']=='acknowledged' for row in state['history']))
        pending=stored['pendingArchive']
        if pending is not None:
            exact(pending,{'original','manifest'})
            need(state['current'] is not None and state['current']['phase']=='acknowledged' and len(history)<MAX_INPUTS)
            if pending['original'] is not None:
                self.history_store.original(pending['original']);need(pending['original']['index']==len(history)+1)
            if pending['manifest'] is not None:
                item=pending['manifest'];exact(item,{'emoteManifestVersion','reference','phase'})
                need(type(item['emoteManifestVersion']) is int and item['emoteManifestVersion']==1 and item['phase'] in ('planned','saved')
                    and pending['original'] is not None and pending['original']['phase']=='saved')
                self.history_store.manifest_reference(item['reference'])
                need(item['reference']['block']==len(history)//BLOCK+1 and item['reference']['count']==len(history)%BLOCK+1)
        return state,dict(count=len(history),manifests=deepcopy(stored['manifests']),pendingArchive=deepcopy(pending))

    def bound(self):
        need(getattr(self.source,'historical',False) is False)
        now=self.source.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<45));self.clock=now
        self.lock.assert_held();need(not self.failed and self.source.guard() is not False and same(self.store.read(),self.previous)
            and same(self.source.store.read(),self.source.previous))

    def persist(self,*,host_only=False):
        try:
            if host_only:
                self.lock.assert_held();need(not self.failed and same(self.store.read(),self.previous)
                    and same(self.source.store.read(),self.source.previous));self.host_fresh()
            else:self.bound()
            stored=dict(historyCount=self.history_state['count'],manifests=self.history_state['manifests'],
                pendingArchive=self.history_state['pendingArchive'],current=self.state['current'])
            need(len(self.state['history'])==stored['historyCount'])
            value=dict(picoEmoteInputsVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,binding=self.binding,
                artifactRoot=str(self.source.artifact_root),payload=pack([stored]))
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
            if host_only:self.host_fresh()
        except Exception:
            self.failed=True
            # A failed final ACK write must not make this same live object
            # acknowledge an uncommitted state on the caller's next attempt.
            if not host_only and same(self.store.read(),self.previous):
                if self.previous is not None:self.state,self.history_state=self.decode(self.previous)
                else:self.state,self.history_state=dict(history=[],current=None),dict(count=0,manifests=[],pendingArchive=None)
            raise

    def save(self):
        need(self.history_state['pendingArchive'] is None)
        self.persist()

    def archive_intent(self,kind,value):
        need(kind in ('original','manifest') and self.history_state['pendingArchive'] is not None)
        pending=self.history_state['pendingArchive'];old=pending[kind]
        if kind=='original':
            self.history_store.original(value);need(value['index']==self.history_state['count']+1)
            if old is None:need(value['phase']=='planned')
            else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
                and (old['phase']=='planned' or same(old['file'],value['file'])))
        else:
            exact(value,{'emoteManifestVersion','reference','phase'})
            need(type(value['emoteManifestVersion']) is int and value['emoteManifestVersion']==1
                and pending['original'] is not None and pending['original']['phase']=='saved')
            self.history_store.manifest_reference(value['reference'])
            need(value['reference']['block']==self.history_state['count']//BLOCK+1
                and value['reference']['count']==self.history_state['count']%BLOCK+1)
            need(value['phase']=='planned' if old is None else old['phase']=='planned' and value['phase']=='saved'
                and same(old['reference'],value['reference']))
        pending[kind]=deepcopy(value);self.persist()

    def archive_current(self):
        self.bound();need(self.history_state['pendingArchive'] is None and self.state['current'] is not None
            and self.state['current']['phase']=='acknowledged' and len(self.state['history'])<MAX_INPUTS)
        current=deepcopy(self.row(self.state['current']))
        self.history_state['pendingArchive']=dict(original=None,manifest=None);self.persist()
        original=self.history_store.write(len(self.state['history'])+1,current)
        manifests=self.history_store.append(self.history_state['manifests'],original)
        self.state['history'].append(current);self.state['current']=None
        self.history_state=dict(count=len(self.state['history']),manifests=manifests,pendingArchive=None);self.persist()

    def recover_archive(self):
        """Finish only exact owned archival bytes, without input or queries."""
        self.started=self.source.monotonic();need(number(self.started,0,1e15));self.bound()
        need(self.history_state['pendingArchive'] is not None and self.state['current'] is not None)
        current=deepcopy(self.row(self.state['current']));need(current['phase']=='acknowledged')
        pending=self.history_state['pendingArchive'];index=len(self.state['history'])+1
        if pending['original'] is None:original=self.history_store.write(index,current)
        else:original=self.history_store.resume_write(index,current,pending['original'])
        manifests=self.history_store.resume_manifest(self.history_state['manifests'],original,pending['manifest'])
        self.bound();self.state['history'].append(current);self.state['current']=None
        self.history_state=dict(count=len(self.state['history']),manifests=manifests,pendingArchive=None);self.persist();self.bound()

    def controller_retirement(self):
        """Fresh final owned neutral, preserving all original input journals."""
        self.bound();need(self.state['current'] is not None and self.state['current']['phase']=='acknowledged'
            and self.state['current']['call']['verb']=='close' and self.history_state['pendingArchive'] is None)
        streams=[item for row in self.state['history']+[self.state['current']] for item in row['intents'] if item['kind']=='controller']
        need(streams and all(item['after'] is not None and item['stream']['envelope'] is not None
            and item['stream']['neutral'] is not None for item in streams))
        frame=self.source.read();need(not self.ui(frame)['open'])
        started=self.source.monotonic();epoch=self.source.clock_ms()
        value=self.controller_session.require_owned_neutral(self.binding['processIdentity'],streams[-1]['stream']['envelope'])
        PicoLifecycleBack.neutral(value,streams[-1]['stream']['envelope'],frame['widgets']['updatedEpochMs'])
        result=deepcopy(value);self.bound();clock=self.source.clock_ms();now=self.source.monotonic()
        need(number(now,started,started+1.5) and integer(clock,epoch))
        fresh(value['updatedEpochMs'],max(clock,epoch+math.ceil((now-started)*1000)));return result

    def act(self,call):
        call=deepcopy(arguments('feature.emotes.act',call));need(call['verb'] in VERBS and call['runId']==self.run
            and call['fixtureUrl']==self.fixture_url);self.lock.assert_held()
        self.started=self.source.monotonic();need(number(self.started,0,1e15));self.bound()
        need(self.history_state['pendingArchive'] is None)
        floor=self.source.frames[-1]['phaseAfter'] if self.source.frames else None
        self.active(call,self.source.phase.read(floor)['status']);self.bound()
        current=self.state['current']
        if current is not None:
            self.row(current)
            if current['call']['ticket']==call['ticket']:
                need(same(current['call'],call) and current['phase']=='acknowledged');self.bound();return {'performed':True}
            need(current['phase']=='acknowledged' and len(self.state['history'])<MAX_INPUTS-1)
            self.archive_current()
        need(len(self.state['history'])<MAX_INPUTS)
        self.state['current']=dict(call=call,phase='acting',before=None,intents=[],idleReset=None);self.save()
        with self.session():
            current=self.state['current'];current['before']=self.capture();self.save()
            self.bound()
            ui=self.controls(self.intent,self.receipt)
            verb=call['verb']
            if verb in ('open','play','sit','override','cancel'):
                if not self.ui(self.source.frames[-1])['open']:self.controller('tablet.open')
                ui.open()
                if verb in ('play','sit','override'):ui.play('Sit' if verb=='sit' else call['inputs']['name'])
                elif verb=='cancel':
                    page=ui.row(ui.capture(),'emote.page');need(page is not None)
                    if page['activeName']:ui.cancel()
                    if not any(item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.') for item in current['intents']):
                        current['idleReset']=self.capture();self.row(current);self.save()
            elif verb=='close':
                if self.ui(self.source.frames[-1])['open']:ui.close();self.controller('tablet.close')
            else:need(verb=='wait-complete') # No expected-duration sleep or product setter.
            current['phase']='acknowledged';self.row(current);self.save()
        self.bound();return {'performed':True} # Handled input/reset only; complete effect proofs remain mandatory.
