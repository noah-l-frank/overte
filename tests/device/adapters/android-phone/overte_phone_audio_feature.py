"""Normal Phone Audio v17 composition with independent original measurements.

Input journals authorize delivery only. Public states come exclusively from
new native/UI reads; original microphone/sink/PC PCM are acquired separately.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from pathlib import Path
import time
import uuid
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.recorded_preview_history import accept_history,measured_state
from adapters.recorded_preview_evidence import validate_absence
from adapters.restart_inputs import validate_native_restart
from adapters.native_process_presence import validate as presence_packet
from feature_journeys.contract import arguments,identifier,result
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.phase_fixture import PhasePending,PhaseRetired
from feature_journeys.witness import projection
from feature_journeys.evidence import audio_observation
from overte_phone_audio_fixture import AudioFixtureReader
from overte_phone_audio_peer import PhoneAudioPeer,configuration
from overte_phone_audio_files import PhoneAudioFiles,record as file_record,wav
from overte_phone_audio_source import validate as input_packet
from overte_phone_audio import validate as ui_packet
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=1


class PhoneAudioFeature:
    def __init__(self,adapter,selector,source,config,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,AudioFixtureReader) and role in ('primary','actor'))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.config=configuration(config);self.root=Path(config['artifactRoot'])
        self.monotonic,self.sleep=monotonic,sleep;self.jobs={};self.executor=None
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-audio-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('phone-audio-'+role+'.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('phone-audio-retirement.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.originals={}

    def load(self,store,kind):
        value=store.read();self.originals[store.path]=deepcopy(value)
        if value is None:return None
        exact(value,{'audioFeatureVersion','kind','runId','fixtureUrl','configuration','payload'})
        need(type(value['audioFeatureVersion']) is int and value['audioFeatureVersion']==VERSION and value['kind']==kind and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and same(value['configuration'],self.config))
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def save(self,store,kind,state):
        self.lock.assert_held();need(store.path in self.originals and same(store.read(),self.originals[store.path]))
        value=dict(audioFeatureVersion=VERSION,kind=kind,runId=self.run,fixtureUrl=self.fixture_url,configuration=self.config,payload=pack([state]))
        store.write(value,self.originals[store.path]);need(same(store.read(),value));self.originals[store.path]=deepcopy(value)

    def control(self,archive=None):
        state=self.load(self.store,'owner')
        if state is None and archive is not None:state=deepcopy(archive)
        if state is not None:
            exact(state,{'phase','binding','original','initialFiles','peerSessionHash','ticket','call','steps','intents','cycle','recordTicket','phaseSource','httpSource','restart','quiet'})
            need(state['phase'] in ('baseline','waiting-peer','acting','active','cleaning','cleaned','retiring') and integer(state['cycle']) and type(state['steps']) is list and len(state['steps'])<=16 and type(state['intents']) is list and len(state['intents'])<=256 and type(state['peerSessionHash']) is str and len(state['peerSessionHash'])==64)
            context(state['binding']);native_packet(state['original'],state['original']['requestId'],state['original']['processId'],state['original']['capturedEpochMs'],require_recorded_history=True)
            proof=state['initialFiles'];validate_absence(proof,proof['requestId'],state['original']['processId'],proof['capturedEpochMs'],instance=state['original']['instance'])
            if state['ticket'] is not None:identifier(state['ticket'])
            if state['recordTicket'] is not None:identifier(state['recordTicket'])
            if state['call'] is not None:arguments('feature.audio.act',state['call']);need(state['call']['runId']==self.run and state['call']['ticket']==state['ticket'] and state['call']['fixtureUrl']==self.fixture_url)
            for step in state['steps']:exact(step,{'kind','phase'});need(type(step['kind']) is str and step['phase'] in ('issued','observed'))
            for intent in state['intents']:
                exact(intent,{'verb','control','ui'});ui=intent['ui'];ui_packet(ui,ui['commandId'],ui['processId'],ui['capturedEpochMs'])
            restart=state['restart']
            if restart is not None:
                exact(restart,{'phase','oldBinding','oldNative','newBinding','native','exit'});old=context(restart['oldBinding'])
                need(restart['phase'] in ('stop-issued','launch-issued','observed'))
                if restart['phase']!='observed':need(same(old,state['binding']))
                packet=restart['oldNative'];native_packet(packet,packet['requestId'],int(old['processIdentity'].split(':')[0]),packet['capturedEpochMs'],require_recorded_history=True)
                if restart['phase']=='observed':
                    new=context(restart['newBinding']);need(same(new,state['binding']) and all(new[k]==old[k] for k in old if k!='processIdentity') and new['processIdentity']!=old['processIdentity'])
                    after=restart['native'];native_packet(after,after['requestId'],int(new['processIdentity'].split(':')[0]),after['capturedEpochMs'],require_recorded_history=True)
                    validate_native_restart(dict(pid=packet['processId'],instance=packet['instance'],lifecycle=packet['lifecycle']),dict(pid=after['processId'],instance=after['instance'],lifecycle=after['lifecycle']))
                    exit=restart['exit'];presence_packet(exit,dict(schemaVersion=1,commandId=exit['commandId'],action='feature-process-presence',queryProcessId=packet['processId']),after['processId'],exit['capturedEpochMs'])
                    need(exit['presence']=='absent' and exit['instance']==after['instance'] and exit['capturedEpochMs']>=after['capturedEpochMs'] and after['graphics']==packet['graphics'])
                else:need(restart['newBinding'] is restart['native'] is restart['exit'] is None)
        return state

    def role_state(self,role=None,archive=None):
        role=self.role if role is None else role
        store=PrivateFeatureState(self.store.path.with_name('phone-audio-'+role+'.json'));state=self.load(store,role)
        if state is None and archive is not None:state=deepcopy(archive)
        if state is None:return dict(sequence=0,binding=None,last=None,files=[],jobs=[],quiet=None,pending=None,retired=False,position=None)
        exact(state,{'sequence','binding','last','files','jobs','quiet','pending','retired','position'})
        need(integer(state['sequence'],0,4096) and type(state['files']) is list and len(state['files'])<=64 and type(state['jobs']) is list and len(state['jobs'])<=32 and type(state['retired']) is bool)
        if state['binding'] is not None:context(state['binding'])
        for row in state['files']:file_record(row);need(row['runId']==self.run and row['role']==role)
        need(len({row['name'] for row in state['files']})==len(state['files']))
        if state['files']:
            files=PhoneAudioFiles(self.root,self.run,role,lambda *_:need(False),lambda:None,state['binding'])
            for row in state['files']:
                need(row['phase'] in ('saved','retiring','retired'))
                if row['phase']=='saved' or row['phase']=='retiring' and files.path(row).exists():files.read(row)
                else:need(not files.path(row).exists() and not files.path(row).is_symlink())
        for job in state['jobs']:
            exact(job,{'ticket','phase','seconds','original','absence'});identifier(job['ticket']);need(job['phase'] in ('issued','capturing','saved','retired') and number(job['seconds'],3,10))
            if job['phase']=='saved':need(type(job['original']) is dict and job['original']['captureId']==job['ticket'])
            if job['phase']=='retired':need(type(job['absence']) is dict and job['absence']['exists'] is False and job['absence']['retired'] is True)
        if state['last'] is not None:
            frame=state['last'];exact(frame,{'ticket','native','input','ui','phase','http','previewFiles'})
            pid=int(state['binding']['processIdentity'].split(':')[0]);native=frame['native']
            native_packet(native,native['requestId'],pid,native['capturedEpochMs'],require_recorded_history=True)
            input_packet(frame['input'],frame['input']['requestId'],pid,frame['input']['capturedEpochMs'])
            ui_packet(frame['ui'],frame['ui']['commandId'],pid,frame['ui']['capturedEpochMs'])
            if frame['previewFiles'] is not None:
                proof=frame['previewFiles'];validate_absence(proof,proof['requestId'],pid,proof['capturedEpochMs'],instance=native['instance'])
        if state['quiet'] is not None:
            quiet=state['quiet'];exact(quiet,{'first','last','count','complete'})
            need(integer(quiet['first'],1) and integer(quiet['last'],quiet['first']) and integer(quiet['count'],1) and type(quiet['complete']) is bool
                and quiet['complete']==(quiet['count']>=3 and quiet['last']-quiet['first']>=3000) and state['last'] is not None and state['last']['native']['capturedEpochMs']>=quiet['last'])
            need(state['last']['previewFiles'] is not None)
        if state['position'] is not None:
            exact(state['position'],{'phase','voice'});need(state['position']['phase'] in ('issued','observed') and type(state['position']['voice']) is dict)
        if state['pending'] is not None:
            exact(state['pending'],{'ticket','actor','actorSequence','capturedEpochMs','facts'});need(state['pending']['actor']=='owned-observer' and state['pending']['actorSequence']==state['sequence'])
        return state

    def binding(self,expected):
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(context(binding),expected));guard();return guard

    def peer(self,state):return PhoneAudioPeer(self.config,state['peerSessionHash'],lambda:self.binding(state['binding']))

    def prepare(self):
        need(self.role=='primary')
        with self.lock.held():
            state=self.control()
            if state is not None:return state
            if hasattr(self.adapter,'audio_mute_store'):need(self.adapter.audio_mute_store(self.selector).read() is None)
            need(self.retirement_store.read() is None and all(self.store.path.with_name('phone-audio-'+role+'.json').exists() is False for role in ('primary','actor')))
            active=self.source.read();need(active['verb']=='baseline')
            _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
            native=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_recorded_history=True)
            controls=self.adapter._audio_controls(self.selector,lambda *_:need(False),read_only=True);ui=controls.capture()
            source=self.adapter._audio_source(self.selector,read_only=True).query();voice=self.adapter._audio_voice_status(self.selector)
            files=self.adapter._recorded_preview_evidence(self.selector,read_only=True).require_absent()
            need(measured_state(native)==dict(recording=False,preview=False,muted=False,recordedFrames=0,playedFrames=0,bufferedFrames=0,phase='idle',history=[],error='none') and controls.row(ui,'audio.page') is None and not native['audio']['recording'] and source['source']['inputAvailable'] and not source['pending'] and not source['source']['armed'] and not voice.get('sourceEnabled') and voice.get('connected') is True and str(uuid.UUID(voice['domainId'].strip('{}')))==self.config['domainId'])
            peer=PhoneAudioPeer(self.config,None,guard);peer.status();session_hash=peer.session()
            state=dict(phase='baseline',binding=deepcopy(binding),original=native,initialFiles=files,peerSessionHash=session_hash,ticket=None,call=None,steps=[],intents=[],cycle=0,recordTicket=None,phaseSource=active['status'],httpSource=active['http'],restart=None,quiet=None)
            self.save(self.store,'owner',state);return state

    def phase(self,state):
        value=self.source.read(state['phaseSource']);self.source.provider(state['httpSource']);return value

    def controls(self,state):
        def intent(verb,ui,control):
            self.lock.assert_held();need(self.role=='primary' and len(state['intents'])<256)
            state['intents'].append(dict(verb=verb,control=control,ui=deepcopy(ui)));self.save(self.store,'owner',state)
        return self.adapter._audio_controls(self.selector,intent)

    def step(self,state,kind,perform,observed):
        found=[row for row in state['steps'] if row['kind']==kind];need(len(found)<=1)
        if found and found[0]['phase']=='observed':return
        if not found:
            state['steps'].append(dict(kind=kind,phase='issued'));self.save(self.store,'owner',state)
            perform()
        # An interrupted send is never redelivered. Only fresh actual state can
        # finish that exact intent. An absent effect retains the red journal.
        need(observed());next(row for row in state['steps'] if row['kind']==kind)['phase']='observed';self.save(self.store,'owner',state)

    def open_page(self,state):
        ui=self.controls(state);current=ui.capture()
        if ui.row(current,'audio.page') is not None:
            need(any(row['kind'] in ('open-audio','open-audio-settings') for row in state['steps'])
                and any(row['verb'] in ('open-audio','open-audio-settings') for row in state['intents']))
            ui.current_mode();return
        if ui.row(current,'audio.entry',ready=True):
            self.step(state,'open-audio',lambda:ui.activate('audio.entry','open-audio'),lambda:ui.row(ui.wait(lambda value:ui.row(value,'audio.page') is not None),'audio.page') is not None)
        else:
            self.step(state,'open-settings',lambda:ui.activate('settings.entry','open-settings'),lambda:ui.row(ui.wait(lambda value:ui.row(value,'audio.settings-entry',ready=True) is not None),'audio.settings-entry') is not None)
            self.step(state,'open-audio-settings',lambda:ui.activate('audio.settings-entry','open-audio-settings'),lambda:ui.row(ui.wait(lambda value:ui.row(value,'audio.page') is not None),'audio.page') is not None)
        ui.current_mode()

    def prepare_input(self,state):
        source=self.adapter._audio_source(self.selector)
        self.step(state,'release-input',lambda:source.release(),lambda:not source.query()['source']['armed'])
        def arm():source.query('arm',runId=self.run,ticket=state['ticket'],url=self.fixture_url+'tickets/'+state['ticket']+'/preview-input.v1.pcm16le')
        def original():
            started=self.monotonic()
            for attempt in range(51):
                value=source.query()
                if not value['pending']:
                    need(value['error']=='' and value['source']['armed'] and value['receipt']['ticket']==state['ticket'])
                    status=self.source.provider(state['httpSource']);receipt=value['receipt']
                    matches=[r for r in status['responses'] if r['responseId']==receipt['responseId']]
                    need(len(matches)==1 and all(matches[0][key]==receipt[key] for key in ('ticket','status','bytes','sha256')))
                    need(receipt['completedEpochMs']>=matches[0]['startedEpochMs']);return True
                need(self.monotonic()-started<5 and attempt<50);self.sleep(.1)
            return False
        self.step(state,'arm-input',arm,original)

    def act(self,call):
        need(self.role=='primary');call=deepcopy(arguments('feature.audio.act',call));need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url);self.prepare()
        with self.lock.held():
            state=self.control();active=self.phase(state);need(active['ticket']==call['ticket'] and active['verb']==call['verb'] and same(active['inputs'],call['inputs']))
            if state['ticket']==call['ticket']:
                need(same(state['call'],call))
                if state['phase']=='active':return {'performed':True}
            else:
                need(state['phase'] in ('baseline','active'));state.update(phase='waiting-peer',ticket=call['ticket'],call=call,steps=[],intents=[],phaseSource=active['status'],httpSource=active['http']);self.save(self.store,'owner',state)
        # Actor must start an actual independent receiver before Record. This
        # wait deliberately releases the shared lock used by its own sampler.
        if call['verb']=='record-start':
            started=self.monotonic()
            for attempt in range(51):
                status=self.peer(state).status()
                if status.get('receivingPreview')==call['ticket']:break
                need(self.monotonic()-started<5 and attempt<50);self.sleep(.1)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            state=self.control();need(same(state['call'],call));self.binding(state['binding']);state['phase']='acting';self.save(self.store,'owner',state)
            ui=self.controls(state);verb=call['verb']
            if verb=='open':self.open_page(state)
            elif verb=='close':self.step(state,'close',lambda:ui.activate('audio.back','back-audio'),lambda:ui.row(ui.wait(lambda value:ui.row(value,'audio.page') is None),'audio.page') is None)
            elif verb=='mute':
                enabled=call['inputs']['enabled'];self.step(state,'mute',lambda:ui.mute(enabled),lambda:(ui.visible('audio.mute')['nativeMuted'] is enabled))
            elif verb=='record-start':
                self.prepare_input(state)
                before=state['cycle']
                self.step(state,'record-start',lambda:ui.start(),lambda:ui.visible('audio.record')['cycle']==before+1)
                state['cycle']=ui.visible('audio.record')['cycle'];state['recordTicket']=call['ticket']
            elif verb=='record-cancel':self.step(state,'record-cancel',lambda:ui.cancel(state['cycle']),lambda:ui.visible('audio.record')['phase']=='cancelled')
            elif verb=='background-resume':self.background(state)
            else:need(verb=='await-completion') # This product has no Preview/Save/Stop input.
            active=self.phase(state);state.update(phase='active',phaseSource=active['status'],httpSource=active['http']);self.save(self.store,'owner',state)
            return {'performed':True}

    def background(self,state):
        status=lambda:self.adapter._graphics_lifecycle_status(self.selector,state['binding'])
        def wait_background():
            started=self.monotonic()
            for attempt in range(51):
                if status()['foreground'] is False:return True
                need(self.monotonic()-started<5 and attempt<50);self.sleep(.1)
            return False
        self.step(state,'background',lambda:self.adapter.invoke(self.selector,'lifecycle.background',{}),wait_background)
        self.step(state,'resume',lambda:self.adapter.invoke(self.selector,'app.launch',{}),lambda:status()['foreground'] is True)
        self.binding(state['binding'])

    def file_owner(self,role_state,role=None):
        role=self.role if role is None else role
        def intent(value):
            rows=role_state['files'];found=[row for row in rows if row['name']==value['name']]
            if found:rows[rows.index(found[0])]=deepcopy(value)
            else:need(len(rows)<64);rows.append(deepcopy(value))
            store=PrivateFeatureState(self.store.path.with_name('phone-audio-'+role+'.json'));self.save(store,role,role_state)
        return PhoneAudioFiles(self.root,self.run,role,intent,lambda:self.binding(role_state['binding']),role_state['binding'])

    def keep_file(self,role_state,ticket,kind,raw,provenance):
        files=self.file_owner(role_state);found=[row for row in role_state['files'] if row['sourceId']==ticket and row['kind']==kind]
        need(len(found)<=1)
        if found:need(files.read(found[0])==raw);return found[0]
        return files.write(ticket,kind,ticket,raw,provenance)

    def native_frame(self,state,role_state,active):
        self.binding(state['binding']);native=self.adapter._native_feature_observer(self.selector,read_only=True)
        before=role_state['last']
        if before is not None and same(role_state['binding'],state['binding']):
            packet=before['native'];native.instance=packet['instance'];native.sequence=packet['sequence'];native.lifecycle=packet['lifecycle'];native.voice_history=packet['audio']['recordedVoice'];native.voice_event_sequence=packet['audio']['recordedVoice']['event'].get('eventSequence',0)
        packet=native.read(native.sequence,require_recorded_history=True)
        need(not packet['audio']['recording'])
        if before is not None and not same(role_state['binding'],state['binding']):
            need(state['restart'] is not None and state['restart']['phase']=='observed'
                and same(role_state['binding'],state['restart']['oldBinding']) and same(state['binding'],state['restart']['newBinding']))
            old=before['native'];validate_native_restart(dict(pid=old['processId'],instance=old['instance'],lifecycle=old['lifecycle']),
                dict(pid=packet['processId'],instance=packet['instance'],lifecycle=packet['lifecycle']))
            self.adapter._process_presence(self.selector,read_only=True).require_absent(old['processId'])
        source=self.adapter._audio_source(self.selector,read_only=True)
        if before is not None and same(role_state['binding'],state['binding']):source.previous=deepcopy(before['input'])
        input_source=source.query();ui=self.adapter._audio_controls(self.selector,lambda *_:need(False),read_only=True);controls=ui.capture()
        need(packet['processId']==input_source['processId']==controls['processId'])
        if before is not None and same(role_state['binding'],state['binding']):
            old=before['ui'];need(controls['instance']==old['instance'] and controls['generation']==old['generation'] and controls['sourceSequence']>old['sourceSequence'] and controls['elapsedMs']>=old['elapsedMs'] and controls['lastCommandSequence']>=old['lastCommandSequence'])
        current=self.phase(state)
        if current['ticket']!=active['ticket']:raise PhasePending('Original Audio phase crossed a product observation')
        epoch=native.clock_ms();need(all(-250<=epoch-value['capturedEpochMs']<=1500 for value in (packet,input_source,controls)))
        files=self.adapter._recorded_preview_evidence(self.selector,read_only=True).require_absent() if active['verb'] in ('baseline','cleanup') else None
        role_state['binding']=deepcopy(state['binding']);frame=dict(ticket=active['ticket'],native=packet,input=input_source,ui=controls,phase=current['status'],http=current['http'],previewFiles=files)
        return frame

    def artifacts(self,state,role_state,frame,sequence):
        native=frame['native'];actual=measured_state(native);active=frame['phase']['activations'][-1];ticket=active['ticket'];artifacts=[]
        if actual['phase']=='completed':
            need(state['recordTicket'] is not None)
            evidence=self.adapter._recorded_preview_evidence(self.selector,read_only=True);packet,raw=evidence.read(0,after_cycle=state['cycle']-1)
            source=packet['source'];input_source=frame['input']['source']
            need(source['cycle']==state['cycle']==input_source['cycle'] and input_source['receipt']['ticket']==state['recordTicket'] and source['events'][-1]['phase']=='completed' and input_source['packetEmits']>input_source['silentEmits'] and input_source['encodedBytes']>0)
            recorded=wav(raw['input'],source['sampleRate'],source['channels']);sink=wav(raw['sink'],source['sampleRate'],source['channels'])
            # Independently inspect actual output-device accepted writes too.
            if not any(row['kind']=='sink' and row['sourceId']==state['recordTicket'] for row in role_state['files']):
                audio_observation(sink,self.run,state['recordTicket'],profile='recorded-preview-v1')
            file=self.keep_file(role_state,state['recordTicket'],'input',recorded,packet);self.keep_file(role_state,state['recordTicket'],'sink',sink,packet)
            artifacts.append(dict(kind='file',name=file['name'],sequence=sequence,ticket=ticket,capturedEpochMs=packet['capturedEpochMs']))
        source_ticket=state['recordTicket'] if actual['phase']=='completed' else ticket
        if source_ticket is not None:
            peer=self.peer(state);status=peer.status()
            if status.get('receivingPreview')!=source_ticket:
                peer_source,raw=peer.original(self.run,source_ticket)
                if raw is not None:
                    file=self.keep_file(role_state,source_ticket,'peer',raw,peer_source)
                    artifacts.append(dict(kind='audio',name=file['name'],sequence=sequence,ticket=ticket,capturedEpochMs=peer_source['capturedEpochMs']))
        return artifacts

    def observe_locked(self,state,call,*,publish=False):
        active=self.phase(state);role_state=self.role_state()
        if state['phase'] not in ('baseline','active','cleaned'):raise PhasePending('Normal Audio input or cleanup is pending')
        if active['verb'] not in ('baseline','cleanup') and active['ticket']!=state['ticket']:raise PhasePending('Normal Audio action has not been delivered')
        if active['verb']=='cleanup' and state['phase']!='cleaned':raise PhasePending('Audio cleanup is incomplete')
        frame=self.native_frame(state,role_state,active);sequence=max(role_state['sequence'],call.get('afterSequence',0))+1;need(sequence<=4096)
        actual=measured_state(frame['native']);actual['open']=any(row['id']=='audio.page' for row in frame['ui']['controls'])
        artifacts=[] if active['verb'] in ('baseline','cleanup','open','close') else self.artifacts(state,role_state,frame,sequence)
        # Artifact I/O has its own fresh source fence, never a retimed PCM.
        native=self.adapter._native_feature_observer(self.selector,read_only=True);after=native.read(frame['native']['sequence'],require_recorded_history=True)
        need(after['instance']==frame['native']['instance'] and not after['audio']['recording']);accept_history(frame['native']['audio']['recordedVoice'],after['audio']['recordedVoice'])
        after_actual=measured_state(after)
        if any(after_actual[k]!=actual[k] for k in ('phase','muted','recording','preview')):artifacts=[]
        actual.update(after_actual);captured=after['capturedEpochMs'];frame['native']=after
        need(all(-250<=captured-item['capturedEpochMs']<=1500 for item in [frame['input'],frame['ui'],*artifacts]))
        resources=[]
        if actual['open']:resources.append('panel:audio')
        if actual['recording'] or actual['preview']:resources.append('input:recorded-preview')
        if frame['input']['source']['armed']:resources.append('input:preview-fixture')
        value=result('feature.audio.observe',dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=sequence,capturedEpochMs=captured,state=actual,artifacts=artifacts,resources=resources,lifecycle=after['lifecycle']))
        role_state.update(sequence=sequence,last=frame,binding=deepcopy(state['binding']))
        if active['verb']=='cleanup':
            need(actual=={**measured_state(state['original']), 'open':False} and resources==[]
                and frame['input']['source']['inputAvailable'] and frame['input']['source']['lifecycleRunning'] and not frame['input']['source']['paused'])
            if role_state['quiet'] is None:role_state['quiet']=dict(first=captured,last=captured,count=1,complete=False)
            else:
                quiet=role_state['quiet'];need(captured>=quiet['last']);quiet.update(last=captured,count=quiet['count']+1,complete=quiet['count']+1>=3 and captured-quiet['first']>=3000)
        self.save(self.role_store,self.role,role_state)
        if publish:
            sample=dict(ticket=active['ticket'],actor='owned-observer',actorSequence=sequence,capturedEpochMs=captured,facts=projection('audio',actual))
            role_state['pending']=sample;self.save(self.role_store,self.role,role_state)
            self.source.client.request('/runs/'+self.run+'/samples',sample)
            self.publication_receipt(sample)
            role_state['pending']=None;self.save(self.role_store,self.role,role_state)
        return value

    def publication_receipt(self,sample):
        journal=self.source.client.request('/runs/'+self.run)
        need(journal['runId']==self.run and journal['area']=='audio' and type(journal['entries']) is list)
        rows=[row for row in journal['entries'] if row.get('actorSequence')==sample['actorSequence']]
        need(len(rows)==1 and all(same(rows[0][key],value) for key,value in sample.items()))
        need(-250<=self.source.epoch_ms()-journal['sampleEpochMs']<=1500)
        return rows[0]

    def observe(self,call):
        call=arguments('feature.audio.observe',call);need(call['runId']==self.run)
        if self.role=='primary':self.prepare()
        with self.lock.held():
            state=self.control();need(state is not None);return self.observe_locked(state,call)

    def tick_peer(self,state,role_state,active):
        need(self.role=='actor');peer=self.peer(state);status=peer.status()
        for job in role_state['jobs']:
            if job['phase'] in ('saved','retired'):continue
            ticket=job['ticket'];future=self.jobs.get(ticket)
            if future is not None and future.done():future.result()
            if status.get('receivingPreview')==ticket:job['phase']='capturing'
            else:
                source,raw=peer.original(self.run,ticket)
                if raw is not None:job.update(phase='saved',original=source['original'])
                elif future is None:raise NativeUIError('Original PC preview delivery is uncertain; no replay is permitted')
        verb=active['verb'];needed=verb=='record-start' or verb in ('record-cancel','background-resume') or verb=='mute' and active['inputs']['enabled']
        if needed and not any(row['ticket']==active['ticket'] for row in role_state['jobs']) and not status.get('receivingPreview'):
            need(len(role_state['jobs'])<32);seconds=8 if verb=='record-start' and not self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_recorded_history=True)['audio']['muted'] else 3.25
            job=dict(ticket=active['ticket'],phase='issued',seconds=seconds,original=None,absence=None);role_state['jobs'].append(job);self.save(self.role_store,'actor',role_state)
            if self.executor is None:self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='owned-audio-preview')
            self.jobs[job['ticket']]=self.executor.submit(peer.receive,self.run,job['ticket'],seconds)
        self.save(self.role_store,'actor',role_state)

    def publish(self):
        need(self.role=='actor');pending=None
        with self.lock.held():
            try:return self.publish_locked()
            except PhasePending as error:pending=error
        raise pending

    def publish_locked(self):
        state=self.control()
        if state is None:raise PhasePending('Audio owner is not prepared')
        try:active=self.phase(state)
        except PhaseRetired:
            self.retire_actor(state);raise
        role_state=self.role_state()
        if role_state['pending'] is not None:
            self.publication_receipt(role_state['pending']);role_state['pending']=None;self.save(self.role_store,'actor',role_state)
        # Original position/domain data configures the independent fixture,
        # never the tested client's requested Audio state.
        if role_state['position'] is None:
            voice=self.adapter._audio_voice_status(self.selector);need(voice.get('connected') is True and str(uuid.UUID(voice['domainId'].strip('{}')))==self.config['domainId'])
            role_state['position']=dict(phase='issued',voice=voice);self.save(self.role_store,'actor',role_state)
            position=voice['position'];self.peer(state).request('position',x=position['x']+.5,y=position['y'],z=position['z'])
        if role_state['position']['phase']=='issued':
            position=role_state['position']['voice']['position'];actual=self.peer(state).status()['client']['position']
            need(sum((actual[k]-position[k])**2 for k in ('x','y','z'))<=1)
            role_state['position']['phase']='observed';self.save(self.role_store,'actor',role_state)
        self.tick_peer(state,role_state,active)
        return self.observe_locked(state,dict(afterSequence=role_state['sequence']),publish=True)

    def cleanup(self,call):
        need(self.role=='primary');call=arguments('feature.audio.cleanup',call);need(call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            state=self.control();need(state is not None);active=self.phase(state);need(active['verb']=='cleanup')
            if state['phase']!='cleaned':
                state.update(phase='cleaning',ticket=active['ticket'],call=None,phaseSource=active['status'],httpSource=active['http']);self.save(self.store,'owner',state)
                self.restore_and_restart(state)
                state['phase']='cleaned';self.save(self.store,'owner',state)
            # Hold the source lock through the primary's quiet window. The
            # independent actor starts its own window after return, during the
            # common three-second cleanup checkpoint. Publishing early samples
            # while cleanup blocks would leave stale, unseen peer entries.
            started=self.monotonic()
            for attempt in range(41):
                self.observe_locked(state,dict(afterSequence=0));role=self.role_state()
                if role['quiet'] is not None and role['quiet']['complete']:return {'performed':True}
                need(self.monotonic()-started<10 and attempt<40);self.sleep(.25)
        need(False)

    def restore_and_restart(self,state):
        # No private synthetic idle/reset setter exists: actual native history
        # is restored only through an owned normal process stop/new launch.
        if state['restart'] is None:
            ui=self.controls(state);current=ui.capture()
            if ui.row(current,'audio.page') is None:
                state['steps']=[];self.save(self.store,'owner',state);self.open_page(state)
            row=ui.visible('audio.record')
            if row['nativeActive']:ui.cancel(row['cycle'])
            ui.mute(False);ui.echo(False)
            self.adapter._audio_source(self.selector).release();self.adapter._recorded_preview_evidence(self.selector).release()
            ui.activate('audio.back','back-audio');need(ui.row(ui.wait(lambda v:ui.row(v,'audio.page') is None),'audio.page') is None)
            old=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_recorded_history=True)
            state['restart']=dict(phase='stop-issued',oldBinding=deepcopy(state['binding']),oldNative=old,newBinding=None,native=None,exit=None);self.save(self.store,'owner',state)
            self.adapter.invoke(self.selector,'app.stop',{})
        restart=state['restart']
        if restart['phase']=='stop-issued':
            target=self.adapter.target(self.selector);client,session,session_state=self.adapter.existing_session(self.selector)
            process=self.adapter.process_state(self.selector,client,session,session_state,target)
            need(process.get('running') is False and self.adapter.query_app_state(client,session,target)==1)
            restart['phase']='launch-issued';self.save(self.store,'owner',state);self.adapter.invoke(self.selector,'app.launch',{})
        if restart['phase']=='launch-issued':
            _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
            old=restart['oldBinding'];need(all(binding[k]==old[k] for k in old if k!='processIdentity') and binding['processIdentity']!=old['processIdentity'])
            native=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_recorded_history=True)
            validate_native_restart(dict(pid=restart['oldNative']['processId'],instance=restart['oldNative']['instance'],lifecycle=restart['oldNative']['lifecycle']),dict(pid=native['processId'],instance=native['instance'],lifecycle=native['lifecycle']))
            exit=self.adapter._process_presence(self.selector,read_only=True).require_absent(restart['oldNative']['processId'])
            need(native['audio']['recordedVoice']['cycle']==0 and measured_state(native)==measured_state(state['original']))
            restart.update(phase='observed',newBinding=deepcopy(binding),native=native,exit=exit);state['binding']=deepcopy(binding);self.save(self.store,'owner',state)
        need(restart['phase']=='observed');self.binding(state['binding'])

    def retire_actor(self,state):
        role=self.role_state();need(state['phase']=='cleaned' and role['pending'] is None and role['quiet'] is not None and role['quiet']['complete'])
        peer=self.peer(state)
        for job in role['jobs']:
            future=self.jobs.get(job['ticket'])
            if future is not None:need(future.done());future.result()
            proof=peer.release(job['ticket']);job.update(phase='retired',absence=proof)
        role['retired']=True;self.save(self.role_store,'actor',role)
        if self.executor is not None:self.executor.shutdown(wait=False);self.executor=None

    def finalize(self):
        need(self.role=='primary')
        started=self.monotonic()
        for attempt in range(21):
            with self.lock.held():
                metadata=self.store.read()
                if metadata is None:break
                state=self.control();actor=self.role_state('actor')
                if actor['retired']:break
                need(state['phase']=='cleaned')
            need(self.monotonic()-started<5 and attempt<20);self.sleep(.25)
        with self.lock.held():
            plan=self.load(self.retirement_store,'retirement');state=self.control(plan['owner'] if plan is not None else None)
            if state is None:return
            status=self.source.status(state['phaseSource']);need(not status['active'] and status['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}) and state['phase'] in ('cleaned','retiring'))
            provider=self.source.provider(state['httpSource']);need(not provider['active'])
            roles={role:self.role_state(role,plan['roles'][role] if plan is not None else None) for role in ('primary','actor')}
            need(all(role['quiet'] is not None and role['quiet']['complete'] and role['pending'] is None for role in roles.values()) and roles['actor']['retired'])
            # Always reacquire actual native/file absence, including when an
            # earlier finalization already removed some host files.
            self.binding(state['binding']);source=self.adapter._audio_source(self.selector,read_only=True).query()
            need(not source['pending'] and not source['source']['armed'] and source['pendingBytes']==0)
            self.adapter._recorded_preview_evidence(self.selector,read_only=True).require_absent()
            native=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_recorded_history=True)
            need(measured_state(native)==measured_state(state['original']) and not native['audio']['recording'])
            ui=self.adapter._audio_controls(self.selector,lambda *_:need(False),read_only=True);need(ui.row(ui.capture(),'audio.page') is None)
            self.adapter._process_presence(self.selector,read_only=True).require_absent(state['restart']['oldNative']['processId'])
            peer=self.peer(state)
            for job in roles['actor']['jobs']:
                observed=peer.packet(job['ticket']);need(not observed['exists'] and observed['retired'] and observed['instance']==job['absence']['instance'])
            state['phase']='retiring'
            if self.store.read() is not None:self.save(self.store,'owner',state)
            for role,role_state in roles.items():
                files=self.file_owner(role_state,role)
                for row in list(role_state['files']):files.retire(row)
            # Preserve a concrete plan before any journal pruning. An old plan
            # never substitutes for the fresh original checks above.
            if plan is None:self.save(self.retirement_store,'retirement',dict(owner=deepcopy(state),roles=deepcopy(roles),provider=provider,phase=status))
            for role in ('primary','actor'):
                store=PrivateFeatureState(self.store.path.with_name('phone-audio-'+role+'.json'));value=store.read()
                if value is not None:store.discard(value)
            current=self.store.read()
            if current is not None:self.store.discard(current)
            self.retirement_store.discard(self.retirement_store.read())
