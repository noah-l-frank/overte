"""Retained normal Assets picker Cancel; independent originals, never a whole claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time
from urllib.parse import unquote,urlsplit
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.phase_input_fence import PhaseInputFence
from adapters.pico4.assets_inventory import original as ui_inventory,inventory
from adapters.pico4 import assets_source,assets_uploads
from adapters.script_journey.history import pack,unpack,same,canonical,MAX_RAW,MAX_FRAMES
from adapters.token_assets_ui import control_id
from adapters.pico4.navigation import identifier as native_id,validate_snapshot
from adapters.token_create_ui import scope
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=1


class CancelPhaseFence(PhaseInputFence):
    def __init__(self,source,owner):super().__init__(source);self.owner=owner
    def original(self):return self.owner.state()['phaseOriginal']


class OwnedAssetsCancel:
    def __init__(self,store,binding,run,fixture_url,files,mappings,uploads,capture,controls,phase,guard,clock_ms,*,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,PhaseFixtureReader) and phase.area=='assets' and phase.run==run
            and phase.fixture_url==fixture_url and all(callable(value) for value in (capture,controls,guard,clock_ms,monotonic,sleep)))
        self.store,self.binding,self.run,self.url=store,deepcopy(context(binding)),identifier(run),fixture_url
        self.files,self.mappings,self.uploads=files,mappings,uploads
        self.capture,self.controls,self.guard,self.clock_ms=capture,controls,guard,clock_ms
        self.monotonic,self.sleep=monotonic,sleep;self.previous=store.read();self.clock=None;self.draft=None;self.active_ui=None
        self.fence=CancelPhaseFence(phase,self);self.final_input=self.before_send
        self.mapping_intent=lambda command:self.source_intent('mappings',command)
        self.upload_intent=lambda command:self.source_intent('uploads',command)
        mappings.intent=self.mapping_intent;uploads.intent=self.upload_intent
        if self.previous is not None:
            self.validate(self.previous);frames=unpack(self.previous['originals'])
            for role,reader in (('mappings',mappings),('uploads',uploads)):
                history=[deepcopy(frame['frame']) for frame in frames if frame['role']==role]
                pending=self.previous['pendingSource'];reader.restore(history,pending['command'] if pending is not None and pending['role']==role else None)

    def validate(self,value):
        exact(value,{'assetsCancelOwnerVersion','binding','runId','fixtureUrl','openTicket','stage','phase','phaseOriginal',
            'attempted','pendingInput','unresolvedInputs','pendingSource','inputs','uiOriginals','inputCount','lastInput','directory','browserId','modelId','baselineMappings','baselineUploads','originals'})
        need(type(value['assetsCancelOwnerVersion']) is int and value['assetsCancelOwnerVersion']==VERSION and context(value['binding'])==self.binding
            and value['runId']==self.run and value['fixtureUrl']==self.url and value['stage']==self.files.native.stage
            and value['phase'] in ('reserved','opening','open','canceling','cancel-observed-files-retired')
            and type(value['attempted']) is list and value['attempted'] in ([],['open'],['open','cancel'])
            and integer(value['inputCount'],0,128) and type(value['unresolvedInputs']) is list and len(value['unresolvedInputs'])<=128)
        identifier(value['openTicket']);phase=value['phaseOriginal'];phase_packet(phase,run=self.run,area='assets',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        need(value['pendingSource'] is None or type(value['pendingSource']) is dict and set(value['pendingSource'])=={'role','command'}
            and value['pendingSource']['role'] in ('mappings','uploads'))
        if value['pendingSource'] is not None:
            (assets_source.command if value['pendingSource']['role']=='mappings' else assets_uploads.command)(value['pendingSource']['command'])
        need(value['pendingInput'] is None or type(value['pendingInput']) is dict and set(value['pendingInput'])=={'input','value','native'}
            and type(value['pendingInput']['input']) is dict and (value['pendingInput']['native'] is None or type(value['pendingInput']['native']) is dict))
        rows=[row for row in phase['activations'] if row['ticket']==value['openTicket']]
        need(len(rows)==1 and rows[0]['stimulus']=={'verb':'upload-picker-open','inputs':{'resource':'gltf-bundle/main.gltf'}}
            and all(type(item) is dict and set(item)=={'input','value','native'} for item in value['unresolvedInputs']))
        for key in ('browserId','modelId'):need(value[key] is None or assets_source.nonce(value[key]))
        need(value['directory'] is None or type(value['directory']) is str and value['directory'].endswith('/feature-assets-'+self.run+('' if value['stage'] is None else '-stage'+str(value['stage']))))
        frames=unpack(value['originals']);need(type(frames) is list and len(frames)<=128)
        for frame in frames:
            exact(frame,{'role','frame'});need(frame['role'] in ('mappings','uploads'))
        commands=unpack(value['inputs']);need(len(commands)<=value['inputCount']);seen=set()
        for item in commands:
            exact(item,{'ticket','input','value','native','after'});identifier(item['ticket']);original=item['input'];native=item['native']
            exact(original,{'assetsInputVersion','action','controlId','controlToken','scope'});scope(original['scope'])
            need(type(original['assetsInputVersion']) is int and original['assetsInputVersion']==1 and control_id(original['controlId'])
                and native_id(original['controlToken']) and original['scope']['instance']==self.binding['sessionId'] and original['scope']['processId']==self.mappings.pid)
            exact(native,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'}
                | ({'text'} if native.get('action')=='replace' else {'index'} if native.get('action')=='select-index' else {'direction'} if native.get('action')=='scroll' else set()))
            need(type(native['schemaVersion']) is int and native['schemaVersion']==1 and native_id(native['commandId']) and native['commandId'] not in seen
                and all(native[key]==original[key] for key in ('controlId','controlToken','action')) and native['bridgeId']==original['scope']['instance']
                and native['generation']==original['scope']['generation'] and native['sequence']==original['scope']['sequence']+1
                and native['observedElapsedMs']==original['scope']['elapsedMs'])
            seen.add(native['commandId'])
            if item['after'] is not None:
                scope(item['after']);need(item['after']['instance']==native['bridgeId'] and item['after']['sequence']==native['sequence'])
        for pending in ([value['pendingInput']] if value['pendingInput'] is not None else [])+value['unresolvedInputs']:
            if pending['native'] is not None:need(pending['native']['commandId'] in seen)
        ui_frames=unpack(value['uiOriginals']);need(len(ui_frames)<=128)
        need(len(frames)+len(commands)+len(ui_frames)+len(self.files.native.history)+len(value['unresolvedInputs'])<=MAX_FRAMES
            and sum(value[key]['bytes'] for key in ('originals','inputs','uiOriginals'))+self.files.state['originals']['bytes']
                +len(canonical([value['baselineMappings'],value['baselineUploads'],value['unresolvedInputs']]))<=MAX_RAW)
        for packet in ui_frames:
            validate_snapshot(packet,self.mappings.pid,packet['updatedEpochMs']);need(packet['bridgeId']==self.binding['sessionId']);ui_inventory(packet)
        if value['baselineMappings'] is not None:
            need(same(value['baselineMappings'],next(frame['frame'] for frame in frames if frame['role']=='mappings')))
            frame=value['baselineMappings'];assets_source.validate(decode(frame['raw']),frame['command'],self.mappings.pid,decode(frame['raw'])['capturedEpochMs'])
        if value['baselineUploads'] is not None:
            need(same(value['baselineUploads'],next(frame['frame'] for frame in frames if frame['role']=='uploads')))
            frame=value['baselineUploads'];assets_uploads.validate(decode(frame['raw']),frame['command'],self.uploads.pid,decode(frame['raw'])['capturedEpochMs'])

    def state(self):
        value=self.store.read();need(value is not None and value==self.previous);self.validate(value);return value
    def write(self,value):
        self.validate(value);retained=deepcopy(value);self.store.write(value,self.previous);self.previous=retained
    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.clock is None or value>=self.clock));self.clock=value;return value
    def admit(self,verb):
        result=self.fence.source.read(self.previous['phaseOriginal'] if self.previous is not None else None)
        need(result['verb']==verb and result['status']['active']);return result
    def same_phase(self,expected):
        result=self.fence.source.read(expected);need(same(result['status']['activations'],expected['activations'])
            and result['ticket']==expected['activations'][-1]['ticket']);return result['status']
    def source_intent(self,role,command):
        value=self.state();need(value['pendingSource'] is None);self.same_phase(value['phaseOriginal'])
        value['pendingSource']=dict(role=role,command=deepcopy(command));self.write(value)
    def read_source(self,role):
        reader=self.mappings if role=='mappings' else self.uploads;value=reader.read(self.run);state=self.state()
        need(state['pendingSource']==dict(role=role,command=reader.history[-1]['command']))
        frames=unpack(state['originals']);need(len(frames)<128);frames.append(dict(role=role,frame=deepcopy(reader.history[-1])))
        state['originals']=pack(frames);state['pendingSource']=None;self.write(state);return value
    def sample(self):
        state=self.state();need(state['pendingSource'] is None);started=self.now();epoch=self.clock_ms();need(integer(epoch,1));self.guard()
        mappings=self.read_source('mappings');uploads=self.read_source('uploads');raw=self.capture();ui=ui_inventory(raw)
        files=self.files.read() if self.files.previous is not None else None
        need(ui['complete'] and raw['processId']==self.mappings.pid==self.uploads.pid
            and mappings['instance']==uploads['instance'] and raw['bridgeId']==self.binding['sessionId'])
        connection=uploads['source']['connection'];source=mappings['source']
        need(all(source[key]==connection[key] for key in connection))
        state=self.state();ui_frames=unpack(state['uiOriginals']);need(len(ui_frames)<128);ui_frames.append(deepcopy(raw));state['uiOriginals']=pack(ui_frames);self.write(state)
        result=dict(mappings=deepcopy(mappings),uploads=deepcopy(uploads),ui=deepcopy(ui),files=deepcopy(files),started=started,epoch=epoch)
        self.check_sample(result);return result
    def check_sample(self,sample):
        state=self.state();self.same_phase(state['phaseOriginal']);self.guard();native=self.clock_ms();now=self.now()
        need(integer(native,sample['epoch']) and now-sample['started']<1.5)
        epoch=max(native,sample['epoch']+math.ceil((now-sample['started'])*1000))
        for key in ('mappings','uploads'):fresh(sample[key]['capturedEpochMs'],epoch)
        fresh(sample['ui']['capturedEpochMs'],epoch)
        if sample['files'] is not None:fresh(sample['files']['capturedEpochMs'],epoch)
    def audit(self,phase,value):
        if phase=='intent':self.draft=deepcopy(value);return True
        need(phase=='receipt');state=self.state();need(state['pendingInput'] is not None)
        pending=state['pendingInput'];need(pending['native'] is not None and pending['native']['sequence']==value['after']['scope']['sequence'])
        history=unpack(state['inputs']);need(history and history[-1]['native']==pending['native'])
        history[-1]['after']=deepcopy(value['after']['scope']);state['inputs']=pack(history)
        state['pendingInput']=None;self.write(state);return True
    def intent(self,original):
        state=self.state();need(state['pendingInput'] is None and state['inputCount']<128 and self.draft is not None)
        scope(original['scope']);need(original['scope']['processId']==self.mappings.pid and original['scope']['instance']==self.binding['sessionId'])
        need(original['controlId']==self.draft['controlId'] and original['action']==self.draft['action'])
        self.fence.mark();state['pendingInput']=dict(input=deepcopy(original),value=deepcopy(self.draft['value']),native=None);state['lastInput']=deepcopy(original)
        state['inputCount']+=1;self.write(state);self.fence.check()
    def before_send(self,command,navigation):
        self.fence.check();state=self.state();pending=state['pendingInput'];need(pending is not None and pending['native'] is None)
        intent=pending['input'];need(all(command[key]==intent[key] for key in ('controlId','controlToken','action'))
            and command['sequence']==intent['scope']['sequence']+1 and command['bridgeId']==intent['scope']['instance'])
        if command['action']=='replace':need(command['text']==pending['value'])
        elif command['action']=='select-index':need(command['index']==pending['value'])
        elif command['action']=='scroll':need(command['direction']==pending['value'])
        else:need(pending['value'] is None)
        # Keep the exact native command before its original one-shot writer.
        pending['native']=deepcopy(command);history=unpack(state['inputs']);need(len(history)<128)
        history.append(dict(ticket=state['phaseOriginal']['activations'][-1]['ticket'],input=deepcopy(intent),value=deepcopy(pending['value']),native=deepcopy(command),after=None))
        state['inputs']=pack(history);self.write(state);self.fence.check()
    def ui(self):
        if self.active_ui is None:self.active_ui=self.controls(self.intent,before_send=self.final_input,audit=self.audit)
        return self.active_ui
    def open(self):
        if self.previous is not None:
            need(self.state()['phase']=='open');return self.reconcile()
        phase=self.admit('upload-picker-open');need(phase['inputs']=={'resource':'gltf-bundle/main.gltf'})
        value=dict(assetsCancelOwnerVersion=VERSION,binding=self.binding,runId=self.run,fixtureUrl=self.url,openTicket=phase['ticket'],
            stage=self.files.native.stage,phase='reserved',phaseOriginal=phase['status'],attempted=[],pendingInput=None,unresolvedInputs=[],pendingSource=None,
            inputs=pack([]),uiOriginals=pack([]),inputCount=0,lastInput=None,directory=None,browserId=None,modelId=None,baselineMappings=None,baselineUploads=None,originals=pack([]))
        self.write(value);before=self.sample();need(not before['ui']['browsers'] and before['uploads']['source']['originalActiveBundles']==0
            and before['uploads']['source']['activeBundles']==before['uploads']['source']['liveRequests']==0)
        state=self.state();state['baselineMappings']=deepcopy(self.mappings.history[-1]);state['baselineUploads']=deepcopy(self.uploads.history[-1]);self.write(state)
        directory=self.files.prepare();state=self.state();state['directory']=directory;state['attempted']=['open'];state['phase']='opening';self.write(state)
        try:
            ui=self.ui();ui.open_picker();ui.navigate_files(unquote(urlsplit(directory).path)+'/gltf-bundle');ui.select_file(directory+'/gltf-bundle/main.gltf')
        except Exception:raise NativeUIError('Original Assets picker delivery remains unresolved') from None
        current=self.sample();self.unchanged(current);need(len(current['ui']['browsers'])==1);browser=current['ui']['browsers'][0]
        need(browser['rootAlive'] and browser['modelAlive'] and browser['inCurrentTree'] and not browser['pendingDocuments'])
        state=self.state();state.update(browserId=browser['id'],modelId=browser['modelId'],phase='open');self.write(state);self.check_sample(current)
        return dict(pickerObserved=True,retained=True)
    def unchanged(self,sample):
        state=self.state();before=decode(state['baselineMappings']['raw']);uploads=decode(state['baselineUploads']['raw'])
        need(before['source']==sample['mappings']['source'] and uploads['source']==sample['uploads']['source'])
    def cancel(self):
        state=self.state();need('open' in state['attempted'] and 'cancel' not in state['attempted'])
        phase=self.admit('upload-picker-cancel');need(phase['inputs']=={})
        state['phaseOriginal']=phase['status'];state['attempted'].append('cancel');state['phase']='canceling'
        if state['pendingInput'] is not None:
            state['unresolvedInputs'].append(deepcopy(state['pendingInput']));state['pendingInput']=None
        self.write(state)
        try:self.ui().cancel_picker()
        except Exception:raise NativeUIError('Original Assets Cancel delivery remains unresolved') from None
        return self.reconcile()
    def retired_consumers(self,sample):
        state=self.state();self.unchanged(sample);need(sample['ui']['complete'])
        rows=sample['ui']['browsers'];need(state['browserId'] is not None and len(rows)==1)
        row=rows[0];need(row['id']==state['browserId'] and row['modelId']==state['modelId'])
        return not row['rootAlive'] and not row['modelAlive'] and not row['inCurrentTree'] and not row['pendingDocuments']
    def reconcile(self):
        state=self.state();sample=self.sample();self.unchanged(sample)
        if state['phase'] in ('reserved','opening','open'):
            # No uncertain input or partially issued recipe is repeated.
            return dict(pickerObserved=bool(sample['ui']['browsers']),retained=True)
        if not self.retired_consumers(sample):return dict(cancelObserved=False,retained=True)
        first=sample;previous=sample;started=self.now()
        for attempt in range(41):
            need(self.now()-started<=5)
            if self.now()-started>=3 and sample['ui']['elapsedMs']-first['ui']['elapsedMs']>=3000:break
            self.sleep(.1);sample=self.sample();need(self.retired_consumers(sample))
            need(0<sample['ui']['elapsedMs']-previous['ui']['elapsedMs']<=500
                and 0<sample['ui']['capturedEpochMs']-previous['ui']['capturedEpochMs']<=500)
            previous=sample
        else:raise NativeUIError('Original Assets Cancel quiet interval remains unresolved')
        need(self.now()-started>=3 and sample['ui']['elapsedMs']-first['ui']['elapsedMs']>=3000)
        self.check_sample(sample)
        def consumers():
            actual=self.sample();need(self.retired_consumers(actual));return True
        self.files.release(consumers);final=self.sample();need(self.retired_consumers(final) and final['files'] is not None
            and final['files']['source']['retired'] is True and final['files']['source']['exists'] is False)
        state=self.state();state['phase']='cancel-observed-files-retired';self.write(state);self.check_sample(final)
        # Context/window survivors are retained original obligations, never GC'd here.
        return dict(cancelObserved=True,filesRetired=True,retained=True,browser=final['ui']['browsers'][0])
