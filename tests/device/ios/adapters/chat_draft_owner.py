"""Owned Chat drafts and local Send/history effects; no whole Chat capability.

Normal controls authorize input. Separate native model/settings and actual
keyboard originals prove local effects. No remote delivery, mixer control, configuration mutation,
native lifetime retirement or successful whole-area result is available here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_chat_view import NativeChatView,measured_view,validate as view_packet,command as view_command
from adapters.native_script_roots import NativeScriptRoots,command as roots_command,validate as roots_packet
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from adapters.token_chat_ui import TokenChatUI
from feature_journeys.contract import arguments,identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.chat_controls import IOSChatIO,IOSPeerChatUI,project
from ios.adapters.chat_draft_clock import operation
from ios.adapters.graphics_history import follow_native
from ios.adapters.normal_input import observation as ui_packet
from ios.adapters import chat_script_sources

VERSION=3
RESTORE_STEPS=frozenset(('cleanup-open','cleanup-settings','cleanup-erase','cleanup-discard','cleanup-rebuild-close','cleanup-rebuild-open'))
RESTORE_READ='cleanup-inspect'
PEER_STEPS=frozenset(('open','select-channel','type','send'))


class IOSChatDraftOwner:
    def __init__(self,store,root,binding,run,lock,guard,*,native,io,view,phase,epoch_ms,monotonic,sleep,
            source_bound=False,code_sources=None,code_roots=None,peer_actor=False,peer_receipts=None):
        need(type(store) is PrivateFeatureState and isinstance(lock,ScriptSourceLock)
            and isinstance(native,NativeFeatureObservation) and native.ios and not native.native_clock_bound
            and isinstance(io,IOSChatIO) and isinstance(view,NativeChatView) and view.ios
            and isinstance(phase,PhaseFixtureReader) and phase.area=='chat' and phase.run==run
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic,sleep)))
        self.store,self.root,self.binding,self.run,self.lock=store,Path(root),deepcopy(context(binding)),identifier(run),lock
        need(store.path==lock.path.with_name('ios-chat-draft-owner.json') and self.root.is_absolute()
            and self.root.resolve(strict=True)==self.root and native.pid==view.pid==int(self.binding['processIdentity']))
        PrivateFeatureState(self.root/'boundary')._parent();lock.assert_held()
        self.guard,self.native,self.io,self.view,self.phase=guard,native,io,view,phase
        self.fixture_url,self.epoch_ms,self.monotonic,self.sleep=phase.fixture_url,epoch_ms,monotonic,sleep
        need(type(source_bound) is bool and (isinstance(code_sources,chat_script_sources.IOSChatScriptSources)
            and isinstance(code_roots,NativeScriptRoots) and code_roots.ios and code_roots.pid==code_sources.pid==native.pid
            if source_bound else code_sources is None and code_roots is None))
        need(type(peer_actor) is bool and (not peer_actor or source_bound))
        from ios.adapters.chat_peer_receipts import IOSChatPeerReceipts
        need(peer_receipts is None or isinstance(peer_receipts,IOSChatPeerReceipts) and source_bound and not peer_actor)
        self.peer_receipts=peer_receipts
        self.source_bound,self.peer_actor,self.code_sources,self.code_roots=source_bound,peer_actor,code_sources,code_roots
        self.historical=False;self.previous=store.read();self.version=self.read_version(self.previous,source_bound=source_bound,peer_actor=peer_actor,peer_receipts=peer_receipts is not None);self.state=self.empty()
        self.frames=self.frame_store();self.ui=(IOSPeerChatUI if peer_actor else TokenChatUI)(io,self.input_intent,run,monotonic=monotonic,sleep=sleep)
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.inventory(self.state)
        if self.state['records']:
            last=self.original(self.state['records'][-1]);restore(native,last['clockJoin']['nativeAfter'])
            original=last['originals']['view'];view.run,view.instance,view.sequence,view.captured=(original[key] for key in ('runId','instance','sequence','capturedEpochMs'))
            view.version=original['chatViewVersion']
            if view.version>=3:view.ownership=deepcopy(original['source']['rootOwnership'])
            if self.source_bound:
                code_roots.restore(last['originals']['scriptRoots']);code_sources.last=deepcopy(last['originals']['scriptSources'])

    @staticmethod
    def empty():return dict(records=[],baseline=None,operations=[],failures=[],pending=None,observation=None,interrupted=[])

    @classmethod
    def archive(cls,store,root,binding,run,lock,fixture_url,*,source_bound=False,peer_actor=False,peer_receipts=None):
        owner=object.__new__(cls);owner.store,owner.root,owner.binding,owner.run,owner.lock=store,Path(root),deepcopy(context(binding)),identifier(run),lock
        lock.assert_held();need(store.path==lock.path.with_name('ios-chat-draft-owner.json'))
        owner.fixture_url,owner.historical,owner.guard,owner.monotonic=fixture_url,True,lambda:True,time.monotonic
        owner.source_bound,owner.peer_actor,owner.code_sources,owner.code_roots=source_bound,peer_actor,None,None
        from ios.adapters.chat_peer_receipts import IOSChatPeerReceipts
        need(peer_receipts is None or isinstance(peer_receipts,IOSChatPeerReceipts) and source_bound and not peer_actor)
        owner.peer_receipts=peer_receipts
        owner.previous=store.read();need(owner.previous is not None);owner.version=owner.read_version(owner.previous,source_bound=source_bound,peer_actor=peer_actor,peer_receipts=peer_receipts is not None)
        owner.state=owner.empty();owner.frames=owner.frame_store()
        owner.state=owner.decode(owner.previous);return owner

    @staticmethod
    def read_version(value,*,source_bound=False,peer_actor=False,peer_receipts=False):
        need(all(type(flag) is bool for flag in (source_bound,peer_actor,peer_receipts))
            and (not peer_actor or source_bound) and (not peer_receipts or source_bound and not peer_actor))
        version=(6 if peer_receipts else 5 if peer_actor else 4 if source_bound else VERSION) if value is None else value.get('iosChatDraftOwnerVersion')
        need(type(version) is int and version in (1,2,3,4,5,6) and (version>=4)==source_bound
            and (version==5)==peer_actor and (version==6)==peer_receipts);return version

    def frame_store(self):
        return OriginalFrameStore(self.root,self.binding,self.run,'primary',self.bound,self.storage_intent,
            namespace='ios-chat-draft',schema_prefix='iosChatDraft',monotonic=self.monotonic)
    def envelope(self,state):
        return dict(iosChatDraftOwnerVersion=self.version,runId=self.run,binding=self.binding,artifactRoot=str(self.root),fixtureUrl=self.fixture_url,payload=pack([state]))
    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.guard() is not False)
        if self.peer_receipts is not None:self.peer_receipts.bound(self)
        return True
    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def phase_original(self,value,ticket,verb,inputs,previous=None):
        phase_packet(value,run=self.run,area='chat',request=value['requestId'],epoch=value['capturedEpochMs'],previous=previous)
        if self.version==6 and verb=='peer-receive':
            need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==ticket
                and value['activations'][-1]['stimulus']['verb']=='peer-send' and inputs=={})
            return
        if self.peer_actor and verb in PEER_STEPS and value['activations'] and value['activations'][-1]['stimulus']['verb']=='peer-send':
            activation=value['activations'][-1];stimulus=activation['stimulus']['inputs']
            need(value['active'] and activation['ticket']==ticket)
            if verb=='type':need(inputs==dict(text=stimulus['text']))
            elif verb=='select-channel':need(inputs==dict(channel=stimulus['channel']))
            else:need(inputs=={})
            return
        if self.version>=3 and verb in RESTORE_STEPS|{RESTORE_READ}:verb='cleanup'
        need(value['active'] and value['activations'] and value['activations'][-1]['ticket']==ticket
            and same(value['activations'][-1]['stimulus'],dict(verb=verb,inputs=inputs)))

    def frame(self,value,previous=None):
        exact(value,{'iosChatDraftObservationVersion','ticket','verb','inputs','phaseBefore','phaseAfter','originals','clockJoin','queries'}
            |({'peerReceipt'} if self.version==6 else set()))
        need(type(value['iosChatDraftObservationVersion']) is int and value['iosChatDraftObservationVersion']==self.version)
        self.call(value['ticket'],value['verb'],value['inputs'])
        if self.version==6:
            if value['verb']=='peer-receive':
                fact,*_=self.peer_receipts.read(value['peerReceipt']);need(fact['ticket']==value['ticket'])
            else:need(value['peerReceipt'] is None)
        self.phase_original(value['phaseBefore'],value['ticket'],value['verb'],value['inputs'])
        self.phase_original(value['phaseAfter'],value['ticket'],value['verb'],value['inputs'],value['phaseBefore'])
        exact(value['originals'],{'uiBefore','view','uiAfter','uiBeforeReceipt','uiAfterReceipt'}
            |({'scriptRoots','scriptSources'} if self.source_bound else set()));raw=value['originals'];join=validate_join(value['clockJoin'],raw)
        need(type(value['queries']) is list and len(value['queries'])<=64);commands={}
        for query in value['queries']:
            self.query(query);need(query['commandId'] not in commands);commands[query['commandId']]=query
        first,last=join['nativeBefore'],join['nativeAfter'];pid=int(self.binding['processIdentity'])
        need(first['processId']==last['processId']==pid and same(first['lifecycle'],last['lifecycle']))
        for packet in (first,last):need(commands.get(packet['requestId'])==dict(schemaVersion=1,commandId=packet['requestId'],action='feature-native-observe'))
        if self.source_bound:
            roots,code=raw['scriptRoots'],raw['scriptSources'];root_query=dict(schemaVersion=1,commandId=roots['commandId'],action='feature-script-roots-observe')
            roots_packet(roots,root_query,pid,last['capturedEpochMs'],previous=None if previous is None else previous['originals']['scriptRoots'])
            source_query=dict(schemaVersion=1,commandId=code['requestId'],action=chat_script_sources.ACTION,runId=self.run)
            chat_script_sources.validate(code,source_query,pid,last['capturedEpochMs'],None if previous is None else previous['originals']['scriptSources'])
            actual=chat_script_sources.admit(code,roots['source']['defaultScriptsUrl'])
            need(commands.get(roots['commandId'])==root_query and commands.get(code['requestId'])==source_query
                and first['capturedEpochMs']<=roots['requestedEpochMs']<=roots['capturedEpochMs']
                <=code['clockBefore']['epochMs']<=code['clockAfter']['epochMs']<=raw['uiBefore']['sampleEpochMs']<=last['capturedEpochMs'])
            if previous is not None:
                old=chat_script_sources.admit(previous['originals']['scriptSources'],previous['originals']['scriptRoots']['source']['defaultScriptsUrl'])
                need(same(actual['membership'],old['membership']) and same(actual['code'],old['code']))
        for key in ('uiBefore','uiAfter'):
            receipt=raw[key+'Receipt'];exact(receipt,{'schemaVersion','commandId','observation'})
            need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and same(receipt['observation'],raw[key])
                and commands.get(receipt['commandId'])==dict(schemaVersion=1,commandId=receipt['commandId'],action='normal-ui-input',operation='observe'))
        need(raw['uiBeforeReceipt']['commandId']!=raw['uiAfterReceipt']['commandId'])
        a,b=[ui_packet(raw[key],pid,last['capturedEpochMs']) for key in ('uiBefore','uiAfter')]
        need(a['instance']==b['instance'] and a['lastSequence']==b['lastSequence'] and a['elapsedMs']<=b['elapsedMs'])
        controls,end=project(a),project(b);need(same(controls['controls'],end['controls']))
        original=raw['view'];view_packet(original,dict(schemaVersion=1,action='feature-chat-view-observe',
            commandId=original['commandId'],runId=self.run),pid,last['capturedEpochMs'])
        need(commands.get(original['commandId'])==dict(schemaVersion=1,commandId=original['commandId'],action='feature-chat-view-observe',runId=self.run))
        if original['chatViewVersion']>=3:
            from adapters.chat_root_ownership import validate as roots
            owned=roots(original['source']['rootOwnership'],pid=pid,epoch=last['capturedEpochMs'],
                previous=None if previous is None else previous['originals']['view']['source'].get('rootOwnership'))
            if owned['available']:need(first['capturedEpochMs']<=owned['capturedEpochMs']<=original['capturedEpochMs'])
        local=self.local(value);source=original['source'];page=TokenChatUI.row(end,'chat.page',enabled=False)
        if self.peer_actor and value['verb'] in ('type','send'):
            activation=value['phaseBefore']['activations'][-1];stimulus=activation['stimulus']
            need(stimulus['verb']=='peer-send' and local['channel']==stimulus['inputs']['channel'])
            if local['draft']:need(local['draft']==stimulus['inputs']['text'])
        stored=source['storage'];need(stored['unowned']==0)
        if self.version==1:need(stored['count']==0 and stored['events']==[])
        else:need(stored['count']==len(stored['events']))
        need(bool(page)==local['open'])
        if page is not None:
            editor=TokenChatUI.row(end,'chat.input',enabled=False)
            if self.version>=3 and local['channel']=='settings':need(editor is None and local['draft']=='')
            else:need(editor is not None and editor['text']==local['draft'] and editor['focused']==local['focused'])
            need(page['channel']==local['channel']
                and page['keyboardRequested']==source['ui']['keyboardRequested']
                and page['localRowCount']==source['ui']['localRowCount']
                and page['domainRowCount']==source['ui']['domainRowCount'])
            histories={channel:[row['text'] for row in stored['events'] if row['channel']==channel] for channel in ('local','domain')}
            for channel in ('local','domain'):
                need(source['ui'][channel+'Messages']==histories[channel] and source['ui'][channel+'RowCount']==len(histories[channel]))
            visible=[] if local['channel']=='settings' else histories[local['channel']]
            need(source['ui']['visibleMessages']==visible and source['ui']['visibleRowCount']==len(visible))
        need(source['editorHasDraft'] is bool(local['draft']) and (not local['keyboard'] or local['focused']))
        if previous is not None:
            old=previous['originals'];follow_native(previous['clockJoin']['nativeAfter'],first)
            need(same(first['lifecycle'],previous['clockJoin']['nativeAfter']['lifecycle'])
                and a['instance']==old['uiAfter']['instance'] and a['lastSequence']>=old['uiAfter']['lastSequence']
                and a['elapsedMs']>=old['uiAfter']['elapsedMs'] and original['instance']==old['view']['instance']
                and original['chatViewVersion']==old['view']['chatViewVersion'] and original['sequence']>old['view']['sequence'] and original['capturedEpochMs']>=old['view']['capturedEpochMs']
                and join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic']
                and join['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs'])
            phase_packet(value['phaseBefore'],run=self.run,area='chat',request=value['phaseBefore']['requestId'],
                epoch=value['phaseBefore']['capturedEpochMs'],previous=previous['phaseAfter'])
            if self.version>=2:
                prior=old['view']['source']['storage']
                operations=self.state['operations']+self.state['failures']+([] if self.state['pending'] is None else [self.state['pending']])
                if not same(stored['events'][:len(prior['events'])],prior['events']):
                    causes=[op for op in operations if op['ticket']==value['ticket'] and op['verb']=='cleanup-erase']
                    need(self.version>=3 and value['verb']=='cleanup-erase' and len(causes)==1);self.erase_effect(causes[0],value)
                elif len(stored['events'])>len(prior['events']):
                    causes=[op for op in operations if op['ticket']==value['ticket'] and op['verb']=='send']
                    if self.version==6 and value['verb']=='peer-receive':
                        causes=[op for op in operations if op['ticket']==value['ticket'] and op['verb']=='peer-receive']
                        need(len(causes)==1);self.peer_receipts.effect(self,causes[0],value)
                    else:need(value['verb']=='send' and len(causes)==1);self.send_history(causes[0],value)
        return value

    def original(self,reference):return self.frame(self.frames.read(self.frames.expand(reference)))
    @staticmethod
    def local(frame):
        value=frame['originals']['view'];source=value['source'];ui=source['ui']
        if frame['iosChatDraftObservationVersion']>=3 and ui['present'] and ui['channel']=='settings':
            view_packet(value,dict(schemaVersion=1,action='feature-chat-view-observe',commandId=value['commandId'],runId=value['runId']),value['processId'],value['capturedEpochMs'])
            need(value['chatViewVersion']>=2 and source['keyboard']['available']
                and (not source['keyboard']['visible'] or source['editorFocused']))
            return dict(open=True,channel='settings',draft=ui['draft'],focused=source['editorFocused'],keyboard=source['keyboard']['visible'],messages=[])
        return measured_view(value)
    def storage(self,frame):
        if self.state['baseline'] is not None:
            actual=frame['originals']['view']['source']['storage'];initial=self.original(self.state['baseline'])['originals']['view']['source']['storage']
            if self.version==1:need(same(actual,initial))
            else:need(actual['configSha256']==initial['configSha256'] and (actual['kind']=='array' if actual['events'] else actual['kind']==initial['kind']))
    def inventory(self,state):
        expected={self.frames.path(self.frames.expand(ref)) for ref in state['records']}|{self.store.path}
        if state['observation'] is not None and state['observation']['wire'] is not None:expected.add(self.frames.path(state['observation']['wire']))
        for root in {self.root,self.store.path.parent}:
            for index,path in enumerate(root.iterdir()):
                need(index<4096)
                if path.name.startswith('ios-chat-draft-'):need(path in expected)

    def decode(self,value):
        exact(value,{'iosChatDraftOwnerVersion','runId','binding','artifactRoot','fixtureUrl','payload'});rows=unpack(value['payload'])
        need(type(value['iosChatDraftOwnerVersion']) is int and value['iosChatDraftOwnerVersion']==self.version and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,set(self.empty()))
        need(type(state['records']) is list and len(state['records'])<=128 and all(type(state[key]) is list and len(state[key])<=32 for key in ('operations','failures','interrupted')))
        need(state['baseline'] is not None or not state['operations'] and not state['failures'] and state['pending'] is None)
        old=self.state;self.state=state
        try:
            previous=None
            for index,ref in enumerate(state['records'],1):
                need(ref['index']==index);current=self.original(ref);self.frame(current,previous);previous=current
            if state['baseline'] is not None:
                need(state['baseline'] in state['records']);self.baseline(self.original(state['baseline']))
                for ref in state['records']:self.storage(self.original(ref))
            tickets={}
            for op in state['operations']+state['failures']+([] if state['pending'] is None else [state['pending']]):
                exact(op,{'ticket','verb','inputs','before','intents','queries','after','quiet'}|({'peerReceipt'} if self.version==6 else set()));self.call(op['ticket'],op['verb'],op['inputs'])
                if self.version==6:
                    if op['verb']=='peer-receive':
                        fact,*_=self.peer_receipts.read(op['peerReceipt']);need(fact['ticket']==op['ticket'])
                    else:need(op['peerReceipt'] is None)
                need(op['verb']!=RESTORE_READ and op['before'] in state['records'] and op['before']['index']>=state['baseline']['index'])
                prior=tickets.setdefault(op['ticket'],set())
                need(not prior or self.version>=3 and op['verb'] in RESTORE_STEPS|{'cleanup'} and prior<=RESTORE_STEPS|{'cleanup'}
                    or self.peer_actor and op['verb'] in PEER_STEPS and prior<=PEER_STEPS)
                need(op['verb'] not in prior);prior.add(op['verb'])
                need(type(op['intents']) is list and len(op['intents'])<=2 and type(op['queries']) is list and len(op['queries'])<=128
                    and type(op['quiet']) is list and len(op['quiet'])<=3)
                for index,intent in enumerate(op['intents']):self.intent_original(op,index,intent)
                for query in op['queries']:self.query(query)
                if op['after'] is not None:
                    need(op in state['operations'] and op['after'] in state['records'] and op['after']['index']>op['before']['index'])
                    self.effect(op,self.original(op['after']));self.quiet(op)
                else:need(op is state['pending'] or op in state['failures'])
            for observation in state['interrupted']+([] if state['observation'] is None else [state['observation']]):
                exact(observation,{'ticket','verb','inputs','queries','partial','wire'});self.call(observation['ticket'],observation['verb'],observation['inputs'])
                need(type(observation['queries']) is list and len(observation['queries'])<=64 and type(observation['partial']) is dict
                    and set(observation['partial'])<=({'start','uiBefore','view','uiAfter','uiBeforeReceipt','uiAfterReceipt','join'}
                        |({'scriptRoots','scriptSources'} if self.source_bound else set())))
                for query in observation['queries']:self.query(query)
                if observation['wire'] is not None:self.frames.original(observation['wire'])
            self.inventory(state)
        finally:self.state=old
        return deepcopy(state)

    def call(self,ticket,verb,inputs):
        identifier(ticket);need(verb in ('open','type','close','cleanup') or self.version>=2 and verb in ('send','select-channel')
            or self.version>=3 and verb in RESTORE_STEPS|{RESTORE_READ} or self.version==6 and verb=='peer-receive')
        if verb=='cleanup' or verb in RESTORE_STEPS|{RESTORE_READ,'peer-receive'}:need(inputs=={} and type(inputs) is dict)
        elif self.peer_actor and verb=='type':
            exact(inputs,{'text'})
            arguments('feature.chat.act',dict(contractVersion=16,runId=self.run,fixtureUrl=self.fixture_url,
                ticket=ticket,verb='peer-send',inputs=dict(text=inputs['text'],channel='domain')))
        else:arguments('feature.chat.act',dict(contractVersion=16,runId=self.run,fixtureUrl=self.fixture_url,ticket=ticket,verb=verb,inputs=inputs))
    def query(self,command):
        if self.source_bound and type(command) is dict:
            if command.get('action')=='feature-script-roots-observe':roots_command(command,ios=True);return
            if command.get('action')==chat_script_sources.ACTION:
                chat_script_sources.command(command);need(command['runId']==self.run);return
        need(type(command) is dict and command.get('action') in ('feature-native-observe','normal-ui-input','feature-chat-view-observe'))
        if command['action']=='feature-chat-view-observe':view_command(command,ios=True)
        else:
            exact(command,{'schemaVersion','commandId','action'}|({'operation'} if command['action']=='normal-ui-input' else set()))
            need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and type(command['commandId']) is str
                and command['commandId'].startswith('ios-'));identifier(command['commandId'][4:])
            if command['action']=='normal-ui-input':need(command['operation']=='observe')
    def query_intent(self,command):
        self.bound();need(not self.historical);self.query(command)
        holder=self.state['observation'] or self.state['pending'];need(holder is not None and len(holder['queries'])<(64 if self.state['observation'] is not None else 128))
        holder['queries'].append(deepcopy(command));self.save()
    def intent_original(self,op,index,entry):
        exact(entry,{'input','phase'});value=entry['input'];exact(value,{'controlId','action','instance','generation','sequence'})
        sequence=[('chat.entry','activate')] if op['verb'] in ('open','cleanup-open','cleanup-rebuild-open') else [('chat.input','activate'),('chat.input','replace')] if op['verb']=='type' else (
            [('chat.settings','activate')] if op['verb']=='cleanup-settings' else [('chat.erase','activate')] if op['verb']=='cleanup-erase' else
            [('chat.send','activate')] if op['verb']=='send' else [('chat.'+op['inputs']['channel'],'activate')] if op['verb']=='select-channel' else [('chat.close','activate')])
        need(index<len(sequence) and (value['controlId'],value['action'])==sequence[index] and integer(value['sequence'],1))
        before=self.original(op['before'])['originals']['uiAfter']
        need(value['instance']==before['instance'] and value['generation']==before['chatGeneration'] and value['sequence']==before['lastSequence']+index+1)
        self.phase_original(entry['phase'],op['ticket'],op['verb'],op['inputs'])
    def input_intent(self,value):
        self.bound();op=self.state['pending'];need(op is not None)
        status=self.phase.read();entry=dict(input=deepcopy(value),phase=status['status'])
        self.intent_original(op,len(op['intents']),entry);op['intents'].append(entry);self.save()
    def storage_intent(self,event,wire):
        need(not self.historical and event=='original' and self.state['observation'] is not None)
        self.state['observation']['wire']=deepcopy(wire);self.save()
    def recover_observation(self):
        pending=self.state['observation']
        if pending is None:return
        wire=pending['wire']
        if wire is None:
            need(len(self.state['interrupted'])<32);self.state['interrupted'].append(deepcopy(pending));self.state['observation']=None;self.save();return
        need(wire['phase'] in ('opened','saved') and wire['index']==len(self.state['records'])+1)
        frame=self.frame(self.frames.read(wire),None if not self.state['records'] else self.original(self.state['records'][-1]))
        need(frame['ticket']==pending['ticket'] and frame['verb']==pending['verb'] and same(frame['inputs'],pending['inputs']))
        self.storage(frame);self.state['records'].append(self.frames.compact(dict(wire,phase='saved')));self.state['observation']=None;self.save()

    @operation
    def capture(self,ticket,verb,inputs):
        self.bound();need(not self.historical);self.call(ticket,verb,inputs);self.recover_observation()
        limit=96 if self.version>=3 and verb not in RESTORE_STEPS|{RESTORE_READ,'cleanup'} else 128
        need(len(self.state['records'])<limit)
        status=self.phase.read();self.phase_original(status['status'],ticket,verb,inputs)
        self.state['observation']=dict(ticket=ticket,verb=verb,inputs=deepcopy(inputs),queries=[],partial={},wire=None);self.save()
        partial=self.state['observation']['partial'];clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        clock.begin(status['status']['activations'][-1]['activatedEpochMs']);partial['start']=deepcopy(clock.started);self.save()
        if self.source_bound:
            partial['scriptRoots']=self.code_roots.read(0 if self.code_roots.last is None else self.code_roots.last['sequence']);self.save()
            partial['scriptSources']=self.code_sources.read(self.run,native_before_floor=clock.started['nativeBefore']);self.save()
        partial['uiBefore']=deepcopy(self.io.original.capture());partial['uiBeforeReceipt']=deepcopy(self.io.original.native.last_receipt);self.save()
        partial['view']=self.view.read(self.run);self.save()
        partial['uiAfter']=deepcopy(self.io.original.capture());partial['uiAfterReceipt']=deepcopy(self.io.original.native.last_receipt);self.save()
        raw={key:deepcopy(partial[key]) for key in ('uiBefore','view','uiAfter','uiBeforeReceipt','uiAfterReceipt')
            +(('scriptRoots','scriptSources') if self.source_bound else ())}
        fields=[('uiBefore','sampleEpochMs'),('view','capturedEpochMs'),('uiAfter','sampleEpochMs')]
        if self.source_bound:fields.append(('scriptRoots','capturedEpochMs'))
        join=clock.finish(raw,fields);partial['join']=deepcopy(join);self.save()
        after=self.phase.status(status['status'])
        value=dict(iosChatDraftObservationVersion=self.version,ticket=ticket,verb=verb,inputs=deepcopy(inputs),phaseBefore=status['status'],phaseAfter=after,originals=raw,clockJoin=join,
            queries=deepcopy(self.state['observation']['queries']))
        if self.version==6:value['peerReceipt']=deepcopy(self.state['pending']['peerReceipt']) if verb=='peer-receive' else None
        self.frame(value,None if not self.state['records'] else self.original(self.state['records'][-1]));self.storage(value)
        ref=self.frames.write(len(self.state['records'])+1,value);self.state['records'].append(ref);self.state['observation']=None;self.save();return ref

    def baseline(self,frame):
        local=self.local(frame);controls=project(frame['originals']['uiAfter'])
        need(not local['open'] and not local['draft'] and not local['focused'] and not local['keyboard']
            and TokenChatUI.row(controls,'chat.entry') is not None
            and frame['originals']['view']['source']['storage']['count']==0)
    def send_history(self,op,frame):
        before=self.original(op['before']);prior=self.local(before)
        if self.peer_actor:
            arguments('feature.chat.act',dict(contractVersion=16,runId=self.run,fixtureUrl=self.fixture_url,
                ticket=op['ticket'],verb='peer-send',inputs=dict(text=prior['draft'],channel=prior['channel'])))
            phase=before['phaseBefore']['activations'][-1]
            need(phase['ticket']==op['ticket'] and phase['stimulus']==dict(verb='peer-send',inputs=dict(text=prior['draft'],channel=prior['channel'])))
        previous=before['originals']['view']['source']['storage']['events'];current=frame['originals']['view']['source']['storage']['events']
        need(len(op['intents'])==1 and len(current)==len(previous)+1 and same(current[:-1],previous)
            and frame['originals']['uiAfter']['lastSequence']==before['originals']['uiAfter']['lastSequence']+1)
        last=current[-1]
        need(last['channel']==prior['channel'] and last['text']==prior['draft']
            and before['clockJoin']['nativeAfter']['capturedEpochMs']<=last['timestamp']<=frame['originals']['view']['capturedEpochMs'])
    def erase_effect(self,op,frame):
        from ios.adapters.chat_history_value import unchanged_empty
        before=self.original(op['before']);need(self.local(before)['channel']=='settings' and self.local(frame)['channel']=='settings'
            and before['originals']['view']['source']['storage']['count']>0
            and len(op['intents'])==1 and frame['originals']['uiAfter']['lastSequence']==before['originals']['uiAfter']['lastSequence']+1)
        baseline=self.original(self.state['baseline'])['originals']['view'];need(baseline['source']['storage']['kind']=='null')
        unchanged_empty(baseline,frame['originals']['view'])
    def effect(self,op,frame):
        need(frame['ticket']==op['ticket'] and frame['verb']==op['verb'] and same(frame['inputs'],op['inputs']))
        before=self.original(op['before']);local=self.local(frame);prior=self.local(before)
        expected=2 if op['verb']=='type' else 0 if (op['verb']=='peer-receive' or op['verb'] in ('cleanup','cleanup-discard','cleanup-rebuild-close') and not prior['open']
            or op['verb']=='cleanup-settings' and prior['channel']=='settings'
            or op['verb']=='select-channel' and prior['channel']==op['inputs']['channel']) else 1
        need(len(op['intents'])==expected and frame['originals']['uiAfter']['lastSequence']==before['originals']['uiAfter']['lastSequence']+expected)
        if op['verb']=='peer-receive':self.peer_receipts.effect(self,op,frame)
        elif op['verb'] in ('open','cleanup-open','cleanup-rebuild-open'):
            need(not prior['open'] and local['open'] and local['channel']=='local' and local['draft']=='')
            earlier=[item for item in self.state['operations'] if item['verb'] in ('open','cleanup-open','cleanup-rebuild-open') and item['after']['index']<op['before']['index']]
            if earlier:need(frame['originals']['view']['source']['ui']['generation']!=self.original(earlier[-1]['after'])['originals']['view']['source']['ui']['generation'])
        elif op['verb']=='type':need(local['open'] and local['draft']==op['inputs']['text'] and local['focused'] and local['keyboard'])
        elif op['verb']=='send':need(prior['open'] and prior['draft'] and local['open'] and local['channel']==prior['channel'] and local['draft']=='')
        elif op['verb']=='select-channel':need(local['open'] and local['channel']==op['inputs']['channel'] and local['draft']==prior['draft'])
        elif op['verb']=='cleanup-settings':need(prior['open'] and local['open'] and local['channel']=='settings' and local['draft']=='')
        elif op['verb']=='cleanup-erase':self.erase_effect(op,frame)
        else:need(not local['open'] and local['draft']=='' and not local['focused'] and not local['keyboard'])
        if self.version>=2:
            previous=before['originals']['view']['source']['storage']['events'];current=frame['originals']['view']['source']['storage']['events']
            if op['verb']=='send':self.send_history(op,frame)
            elif op['verb'] not in ('cleanup-erase','peer-receive'):need(same(current,previous))
        self.storage(frame);return local
    def quiet(self,op):
        if op['verb'] not in ('close','cleanup','cleanup-discard','cleanup-rebuild-close'):need(op['quiet']==[]);return
        need(len(op['quiet'])==3 and op['quiet'][-1]==op['after'] and all(ref in self.state['records'] for ref in op['quiet'])
            and [ref['index'] for ref in op['quiet']]==sorted({ref['index'] for ref in op['quiet']}))
        frames=[self.original(ref) for ref in op['quiet']]
        for frame in frames:self.effect(op,frame)
        first,last=frames[0],frames[-1];a,b=first['clockJoin'],last['clockJoin']
        need(b['hostBeforeMonotonic']-a['hostAfterMonotonic']>=3 and b['hostBeforeEpochMs']-a['hostAfterEpochMs']>=3000
            and b['nativeBefore']['capturedEpochMs']-a['nativeAfter']['capturedEpochMs']>=3000
            and last['originals']['uiBefore']['elapsedMs']-first['originals']['uiAfter']['elapsedMs']>=3000)
    @operation
    def resolve(self):
        self.bound();need(not self.historical);self.recover_observation();op=self.state['pending'];need(op is not None)
        ref=self.capture(op['ticket'],op['verb'],op['inputs']);frame=self.original(ref)
        if op['verb'] in ('send','peer-receive'):
            before=self.original(op['before'])
            while same(frame['originals']['view']['source']['storage']['events'],before['originals']['view']['source']['storage']['events']):
                # Editor clearing only proves input consumption. Wait for a
                # real model/history callback under the same operation budget,
                # keeping every original cut and never repeating Send.
                local=self.local(frame);prior=self.local(before)
                if op['verb']=='send':
                    need(len(op['intents'])==1 and local['open'] and local['channel']==prior['channel'] and local['draft']==''
                        and frame['originals']['uiAfter']['lastSequence']==before['originals']['uiAfter']['lastSequence']+1)
                else:
                    need(op['intents']==[] and all(same(local[key],prior[key]) for key in ('open','channel','draft','focused','keyboard'))
                        and frame['originals']['uiAfter']['lastSequence']==before['originals']['uiAfter']['lastSequence'])
                self.sleep(.25);ref=self.capture(op['ticket'],op['verb'],op['inputs']);frame=self.original(ref)
        self.effect(op,frame);quiet=[]
        if op['verb'] in ('close','cleanup','cleanup-discard','cleanup-rebuild-close'):
            quiet.append(ref)
            for _index in range(2):
                self.sleep(1.6);ref=self.capture(op['ticket'],op['verb'],op['inputs']);self.effect(op,self.original(ref));quiet.append(ref)
        completed=dict(deepcopy(op),after=ref,quiet=quiet);self.quiet(completed)
        self.state['operations'].append(completed);self.state['pending']=None;self.save()
        return dict(verifiedDraftAction=op['verb'],original=deepcopy(ref),local=self.local(self.original(ref)),failed=bool(self.state['failures']))
    @operation
    def act(self,ticket,verb,inputs):
        self.bound();need(not self.historical and verb not in (RESTORE_READ,'peer-receive'));self.call(ticket,verb,inputs);self.recover_observation()
        if self.state['pending'] is not None:
            op=self.state['pending'];need(op['ticket']==ticket and op['verb']==verb and same(op['inputs'],inputs));return self.resolve()
        group=[op for op in self.state['operations']+self.state['failures'] if op['ticket']==ticket]
        if group:need(verb==group[0]['verb'] or self.version>=3 and verb in RESTORE_STEPS|{'cleanup'} and all(op['verb'] in RESTORE_STEPS|{'cleanup'} for op in group)
            or self.peer_actor and verb in PEER_STEPS and all(op['verb'] in PEER_STEPS for op in group))
        retained=next((op for op in self.state['operations'] if op['ticket']==ticket and (op['verb']==verb or self.version<3)),None)
        if retained is not None:
            need(retained['verb']==verb and same(retained['inputs'],inputs));ref=self.capture(ticket,verb,inputs)
            return dict(verifiedDraftAction=verb,original=ref,local=self.effect(retained,self.original(ref)),failed=bool(self.state['failures']))
        need(len(self.state['operations'])<32);ref=self.capture(ticket,verb,inputs);before=self.original(ref)
        if self.state['baseline'] is None:self.baseline(before);self.state['baseline']=ref;self.save()
        local=self.local(before)
        if verb in RESTORE_STEPS:
            baseline=self.original(self.state['baseline'])['originals']['view']
            need(baseline['chatViewVersion']>=2 and baseline['source']['storage']['kind']=='null')
        if verb in ('open','cleanup-open','cleanup-rebuild-open'):need(not local['open'] and TokenChatUI.row(project(before['originals']['uiAfter']),'chat.entry') is not None)
        elif verb=='type':need(local['open'] and local['draft']=='')
        elif verb=='send':
            need(local['open'] and local['draft'] in self.ui.allowed())
            if self.peer_actor:
                arguments('feature.chat.act',dict(contractVersion=16,runId=self.run,fixtureUrl=self.fixture_url,
                    ticket=ticket,verb='peer-send',inputs=dict(text=local['draft'],channel=local['channel'])))
        elif verb=='select-channel':need(local['open'])
        elif verb=='cleanup-settings':need(local['open'] and local['draft']=='')
        elif verb=='cleanup-erase':
            baseline=self.original(self.state['baseline'])['originals']['view']
            need(self.version>=3 and baseline['chatViewVersion']>=2 and baseline['source']['storage']['kind']=='null'
                and local['channel']=='settings' and before['originals']['view']['source']['storage']['count']>0)
        elif verb=='close':need(local['open'])
        elif local['open']:
            # An actual owned entry and unchanged consumed cursor must precede
            # closing a page during failed-action cleanup. A readable empty
            # foreign page is not an ownership grant.
            prior=self.state['operations']+self.state['failures']
            entries=[item for item in prior if item['verb']=='open' and item['intents']]
            intents=[entry['input']['sequence'] for item in prior for entry in item['intents']]
            need(entries and intents and before['originals']['uiAfter']['lastSequence']==max(intents))
        self.state['pending']=dict(ticket=ticket,verb=verb,inputs=deepcopy(inputs),before=ref,intents=[],queries=[],after=None,quiet=[])
        if self.version==6:self.state['pending']['peerReceipt']=None
        self.save()
        if verb in ('open','cleanup-open','cleanup-rebuild-open'):self.ui.open()
        elif verb=='type':self.ui.type(inputs['text'])
        elif verb=='send':self.ui.send()
        elif verb=='select-channel':self.ui.select_channel(inputs['channel'])
        elif verb=='cleanup-settings':self.ui.settings()
        elif verb=='cleanup-erase':self.ui.erase_history()
        else:self.ui.close()
        return self.resolve()

    @operation
    def receive_peer(self,ticket,link):
        """Observe an already independently received peer Send without input.

        The before reference is the actual last main-client cut, not a newly
        acquired cut that already contains the incoming effect. All dependency
        originals are checked before the passive query intent is persisted.
        """
        self.bound();need(self.version==6);self.call(ticket,'peer-receive',{})
        fact,*_=self.peer_receipts.read(link);need(fact['ticket']==ticket)
        if self.historical:need(self.state['pending'] is None and self.state['observation'] is None)
        else:self.recover_observation()
        completed=[op for op in self.state['operations'] if op['ticket']==ticket]
        need(not any(op['ticket']==ticket for op in self.state['failures']))
        if completed:
            need(len(completed)==1 and completed[0]['verb']=='peer-receive'
                and same(completed[0]['peerReceipt'],link) and self.state['pending'] is None)
            op=completed[0];ref=op['after'];frame=self.original(ref)
            return dict(verifiedDraftAction='peer-receive',original=deepcopy(ref),
                local=self.effect(op,frame),failed=bool(self.state['failures']))
        need(not self.historical)
        pending=self.state['pending']
        if pending is not None:
            need(pending['ticket']==ticket and pending['verb']=='peer-receive' and same(pending['peerReceipt'],link))
            if self.state['records'][-1]['index']>pending['before']['index']:
                ref=self.state['records'][-1];frame=self.original(ref);before=self.original(pending['before'])
                if (frame['ticket']==ticket and frame['verb']=='peer-receive'
                        and frame['originals']['view']['source']['storage']['events']!=before['originals']['view']['source']['storage']['events']):
                    self.effect(pending,frame);completed=dict(deepcopy(pending),after=deepcopy(ref),quiet=[]);self.quiet(completed)
                    self.state['operations'].append(completed);self.state['pending']=None;self.save()
                    return dict(verifiedDraftAction='peer-receive',original=deepcopy(ref),local=self.local(frame),failed=bool(self.state['failures']))
        else:
            need(self.state['baseline'] is not None and self.state['records'] and len(self.state['operations'])<32)
            before=self.state['records'][-1];self.peer_receipts.before(self,self.original(before),link)
            self.state['pending']=dict(ticket=ticket,verb='peer-receive',inputs={},before=deepcopy(before),
                intents=[],queries=[],after=None,quiet=[],peerReceipt=deepcopy(link));self.save()
        return self.resolve()

    @operation
    def cleanup(self,ticket):
        """Explicitly cancel an owned pending action without making it passed."""
        self.bound();need(not self.historical);self.recover_observation()
        if self.state['pending'] is not None:
            pending=self.state['pending']
            if pending['verb']=='cleanup':need(pending['ticket']==ticket);return self.resolve()
            need(len(self.state['failures'])<32);self.state['failures'].append(deepcopy(pending));self.state['pending']=None;self.save()
        return self.act(ticket,'cleanup',{})

    @operation
    def restore_history(self,ticket):
        from ios.adapters.chat_history_cleanup import restore
        return restore(self,ticket)
