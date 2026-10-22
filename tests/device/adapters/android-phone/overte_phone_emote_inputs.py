"""One-send ordinary Emote input ownership, independently measured elsewhere."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from types import SimpleNamespace
import time

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import control_id,snapshot,same_reference
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_sources import PhoneEmoteSources,MAX_SEGMENTS
from overte_phone_emote_originals import PhoneEmoteOriginals,BLOCK
from overte_phone_script_history import pack,unpack,same,canonical
from overte_phone_script_ui import PhoneScriptUI

VERSION=2
MAX_INPUTS=256
VERBS={'open','play','sit','override','cancel','wait-complete','close'}


def input_name(segment):
    need(integer(segment,0,MAX_SEGMENTS-1))
    return 'phone-emote-inputs'+('-segment-'+str(segment) if segment else '')+'.json'


class PhoneEmoteInputTransport:
    """Shared one-send ordinary SDK/Qt primitives; owner supplies phase/storage."""
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
        frame=self.source.read();self.active(self.state['current']['call'],frame['phaseAfter']);return self.reference()

    def intent(self,value):
        current=self.state['current'];need(current['phase']=='acting' and len(current['intents'])<64);self.qt_intent(value)
        barrier=None
        if value['controlId'].startswith('emote.play.'):
            barrier=self.capture();frame=self.original(barrier)
            same_reference(value['original'],frame['ui'],value['controlId']);provider=frame['phaseAfter']
            if self.cancelling(current):
                self.cancel_barrier(frame,value)
        else:provider=self.source.phase.read(self.source.frames[-1]['phaseAfter'])['status']
        self.active(current['call'],provider)
        current['intents'].append(dict(kind='qt',input=deepcopy(value),provider=deepcopy(provider),barrier=barrier,after=None))
        current['phase']='issuing';self.save()

    def cancel_barrier(self,frame,value):
        pages=[row for row in value['original']['controls'] if row['id']=='emote.page']
        need(len(pages)==1 and pages[0]['activeName'] and value['controlId']=='emote.play.'+pages[0]['activeName']
            and frame['group']['native']['animation']['overrideActive'] is True)

    def receipt(self,value):
        exact(value,{'intent','after'});current=self.state['current'];need(current['phase']=='issuing')
        item=current['intents'][-1];need(item['kind']=='qt' and item['after'] is None and same(item['input'],value['intent']))
        self.qt_receipt(value['intent'],value['after']);item['after']=deepcopy(value['after'])
        current['phase']='acting';self.save()

    def sdk(self,tablet,identifier):
        current=self.state['current'];need(identifier in ('tablet.open','tablet.close')
            and current['phase']=='acting' and len(current['intents'])<64)
        before=self.capture();need(self.original(before)['ui']['open']==(identifier=='tablet.close'))
        item=dict(kind='sdk',controlId=identifier,before=before,after=None);current['intents'].append(item)
        current['phase']='issuing';self.save()
        if identifier=='tablet.open':tablet.open_tablet()
        else:need(identifier=='tablet.close');tablet.close_tablet();tablet.wait_tablet_absent()
        after=self.capture();need(self.original(after)['ui']['open']==(identifier=='tablet.open'))
        item['after']=after;current['phase']='acting';self.save()

    def input_chain(self,row,call):
        if row['before'] is not None:
            first=self.original(row['before']);self.active(call,first['phaseAfter'])
            previous_ui,previous_provider=first['ui'],first['phaseAfter']
        else:need(row['phase']=='acting' and not row['intents'])
        pending=0
        for index,item in enumerate(row['intents']):
            need(type(item) is dict and item.get('kind') in ('qt','sdk'))
            if item['kind']=='qt':
                exact(item,{'kind','input','provider','barrier','after'});self.qt_intent(item['input']);self.active(call,item['provider'])
                self.same_ui_before_input(previous_ui,item['input']['original'])
                phase_packet(item['provider'],run=self.run,area='emotes',request=item['provider']['requestId'],
                    epoch=item['provider']['capturedEpochMs'],previous=previous_provider)
                if item['input']['controlId'].startswith('emote.play.'):
                    frame=self.original(item['barrier']);self.active(call,frame['phaseAfter'])
                    same_reference(item['input']['original'],frame['ui'],item['input']['controlId'])
                    need(same(frame['phaseAfter'],item['provider']))
                else:need(item['barrier'] is None)
                if item['after'] is not None:
                    self.qt_receipt(item['input'],item['after']);previous_ui=item['after']
                previous_provider=item['provider']
            else:
                exact(item,{'kind','controlId','before','after'})
                need(item['controlId'] in ('tablet.open','tablet.close'))
                frame=self.original(item['before']);self.active(call,frame['phaseAfter'])
                self.same_ui_before_input(previous_ui,frame['ui'])
                phase_packet(frame['phaseAfter'],run=self.run,area='emotes',request=frame['phaseAfter']['requestId'],
                    epoch=frame['phaseAfter']['capturedEpochMs'],previous=previous_provider)
                need(frame['ui']['open']==(item['controlId']=='tablet.close'))
                if item['after'] is not None:
                    after=self.original(item['after']);self.active(call,after['phaseAfter'])
                    need(item['after']['revision']>item['before']['revision']
                        and after['ui']['open']==(item['controlId']=='tablet.open'))
                    self.same_ui_before_input(frame['ui'],after['ui']);previous_ui=after['ui']
                    previous_provider=after['phaseAfter']
            if item['after'] is None:pending+=1;need(index==len(row['intents'])-1)
        need(pending==(1 if row['phase']=='issuing' else 0))
        plays=[item for item in row['intents'] if item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.')]
        return plays

    def cancelling(self,current):
        return current['call']['verb']=='cancel'


class PhoneEmoteInputs(PhoneEmoteInputTransport):
    def __init__(self,source):
        need(isinstance(source,PhoneEmoteSources) and source.role=='primary');source.lock.assert_held()
        self.source=source;self.adapter,self.selector,self.lock=source.adapter,source.selector,source.lock
        self.run,self.fixture_url,self.binding=source.run,source.phase.fixture_url,source.binding
        self.store=PrivateFeatureState(source.store.path.with_name(input_name(source.segment)))
        self.previous=self.store.read();self.state=dict(history=[],current=None)
        self.history_state=dict(count=0,manifests=[],pendingArchive=None)
        self.history_store=PhoneEmoteOriginals(source.artifact_root,self.binding,self.run,'primary',source.guard,
            self.archive_intent,kind='inputs',monotonic=source.monotonic)
        self.started=self.clock=None;self.failed=False
        if self.previous is not None:
            try:self.state,self.history_state=self.decode(self.previous)
            except (KeyError,TypeError,ValueError,OSError):raise NativeUIError('Original Emote input journal is invalid') from None

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
        _state,frames=PhoneEmoteSources.archive(source_header,phase=phase,artifact_root=artifact_root,binding=binding,
            guard=bound,monotonic=monotonic)
        scope=object.__new__(cls);scope.run,scope.fixture_url,scope.binding=phase.run,phase.fixture_url,deepcopy(context(binding))
        scope.source=SimpleNamespace(artifact_root=artifact_root,frames=frames,historical=True)
        scope.history_store=PhoneEmoteOriginals(artifact_root,binding,phase.run,'primary',bound,
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
            pages=[item for item in frame['ui']['controls'] if item['id']=='emote.page']
            need(row['before'] is not None and row['idleReset']['revision']>row['before']['revision']
                and frame['ui']['open'] and frame['ui']['ready'] and len(pages)==1 and pages[0]['activeName']==''
                and frame['group']['native']['animation']['overrideActive'] is False)
        if call['verb']=='wait-complete':need(not row['intents'])
        if row['phase']=='acknowledged':need(row['before'] is not None)
        return row

    def decode(self,value):
        exact(value,{'emoteInputsVersion','runId','fixtureUrl','binding','artifactRoot','payload'})
        need(type(value['emoteInputsVersion']) is int and value['emoteInputsVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and same(context(value['binding']),self.binding)
            and value['artifactRoot']==str(self.source.artifact_root))
        rows=unpack(value['payload']);need(len(rows)==1);stored=rows[0];exact(stored,{'historyCount','manifests','pendingArchive','current'})
        need(integer(stored['historyCount'],0,MAX_INPUTS) and (stored['current'] is None or stored['historyCount']<MAX_INPUTS))
        history=self.history_store.restore(stored['manifests'],stored['historyCount'])
        state=dict(history=history,current=stored['current']);tickets=set()
        for row in state['history']+([state['current']] if state['current'] is not None else []):
            self.row(row);need(row['call']['ticket'] not in tickets);tickets.add(row['call']['ticket'])
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

    def persist(self):
        try:
            self.bound()
            stored=dict(historyCount=self.history_state['count'],manifests=self.history_state['manifests'],
                pendingArchive=self.history_state['pendingArchive'],current=self.state['current'])
            need(len(self.state['history'])==stored['historyCount'])
            value=dict(emoteInputsVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,binding=self.binding,
                artifactRoot=str(self.source.artifact_root),payload=pack([stored]))
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:
            self.failed=True
            # A failed final ACK write must not make this same live object
            # acknowledge an uncommitted state on the caller's next attempt.
            if same(self.store.read(),self.previous):
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
        with self.adapter.existing_input_session(self.selector):
            current=self.state['current'];current['before']=self.capture();self.save()
            native,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector)
            need(same(context(binding),self.binding) and guard() is not False)
            tablet=PhoneScriptUI(native,'io.github.noah_be.overte.phone')
            ui=self.adapter._emote_controls(self.selector,self.intent,receipt=self.receipt)
            verb=call['verb']
            if verb in ('open','play','sit','override','cancel'):
                if not tablet.tablet_visible():self.sdk(tablet,'tablet.open')
                ui.open()
                if verb in ('play','sit','override'):ui.play('Sit' if verb=='sit' else call['inputs']['name'])
                elif verb=='cancel':
                    page=ui.row(ui.capture(),'emote.page');need(page is not None)
                    if page['activeName']:ui.cancel()
                    if not any(item['kind']=='qt' and item['input']['controlId'].startswith('emote.play.') for item in current['intents']):
                        current['idleReset']=self.capture();self.row(current);self.save()
            elif verb=='close':
                if tablet.tablet_visible():ui.close();self.sdk(tablet,'tablet.close')
            else:need(verb=='wait-complete') # No expected-duration sleep or product setter.
            current['phase']='acknowledged';self.row(current);self.save()
        self.bound();return {'performed':True} # Handled input/reset only; complete effect proofs remain mandatory.
