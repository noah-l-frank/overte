"""Public Phone Chat owner over ordinary inputs and independently read originals.

Closed fixture input phases authorize actions; neither input ACKs nor requested
fields supply received messages, actual histories, keyboard or mixer effects.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import math
import re
from pathlib import Path
import time
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.native_chat_observation import ChatCaptureOwner,OwnedChatCapture
from adapters.native_phone_touch_state import released as touch_released
from feature_journeys.contract import arguments,result,identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from feature_journeys.witness import projection
from overte_phone_script_history import pack,unpack,same,canonical
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_script_ui import PhoneScriptUI
from overte_phone_world_web_feature import PhoneWorldWebFeature
from overte_phone_chat_measurements import ChatSettling,measurement,script_identity,source_pins

VERSION=1
AREA='chat'


class PhoneChatFeature:
    area=AREA
    verify_images=PhoneWorldWebFeature.verify_images
    screenshot=PhoneWorldWebFeature.screenshot

    def __init__(self,adapter,selector,source,config,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,PhaseFixtureReader) and source.area==AREA and role in ('primary','actor'))
        from adapters.feature_fixture_access import AdapterFixtureClient
        if role=='actor':need(not isinstance(source.client,AdapterFixtureClient))
        self.adapter,self.selector,self.source,self.config,self.role=adapter,selector,source,deepcopy(config),role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.root=self.artifact_root=Path(config['artifactRoot']);PrivateFeatureState(self.root/'chat-boundary.json')._parent()
        self.monotonic,self.sleep=monotonic,sleep;self.pins=source_pins()
        self.store=PrivateFeatureState(adapter.state_path(selector).with_name('phone-chat-feature.json'))
        self.role_store=self.role_file(role);self.retirement_store=self.file('retirement')
        self.completed=PrivateFeatureState(self.root/('chat-retired-'+self.run+'.json'))
        self.lock=PhoneScriptSourceLock(self.store.path.with_name('phone-script-sources.lock'))
        self.previous={};self.state=self.local=None

    def file(self,kind):return PrivateFeatureState(self.store.path.with_name('phone-chat-'+kind+'.json'))
    def role_file(self,role):return PrivateFeatureState(self.store.path.with_name('phone-chat-'+role+'.json'))

    def load_record(self,store,kind):
        value=store.read();self.previous[store.path]=deepcopy(value)
        if value is None:return None
        exact(value,{'chatFeatureVersion','kind','runId','fixtureUrl','configuration','payload'})
        need(type(value['chatFeatureVersion']) is int and value['chatFeatureVersion']==VERSION and value['kind']==kind
             and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and same(value['configuration'],self.config))
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def save(self,store,kind,value):
        self.lock.assert_held();need(store.path in self.previous and same(store.read(),self.previous[store.path]))
        record=dict(chatFeatureVersion=VERSION,kind=kind,runId=self.run,fixtureUrl=self.fixture_url,configuration=self.config,payload=pack([value]))
        store.write(record,self.previous[store.path]);need(same(store.read(),record));self.previous[store.path]=deepcopy(record)

    write=save # Existing native-screen artifact owner uses this CAS callback.

    def blob(self,value=None,*,reference=None):
        self.lock.assert_held()
        if reference is not None:
            exact(reference,{'chatBlobVersion','name','sha256'});need(type(reference['chatBlobVersion']) is int and reference['chatBlobVersion']==1)
            need(type(reference['sha256']) is str and re.fullmatch('[0-9a-f]{64}',reference['sha256'])
                 and reference['name']=='chat-'+self.run+'-'+reference['sha256'][:32]+'.json')
            record=PrivateFeatureState(self.root/reference['name']).read();exact(record,{'chatBlobVersion','runId','payload'})
            need(type(record['chatBlobVersion']) is int and record['chatBlobVersion']==1 and record['runId']==self.run)
            rows=unpack(record['payload']);need(len(rows)==1 and hashlib.sha256(canonical(rows[0])).hexdigest()==reference['sha256']);return rows[0]
        sha=hashlib.sha256(canonical(value)).hexdigest();name='chat-'+self.run+'-'+sha[:32]+'.json'
        record=dict(chatBlobVersion=1,runId=self.run,payload=pack([value]));store=PrivateFeatureState(self.root/name);old=store.read()
        if old is None:store.write(record,None)
        else:need(same(old,record))
        need(same(store.read(),record));return dict(chatBlobVersion=1,name=name,sha256=sha)

    def load(self):
        self.state=self.load_record(self.store,'owner');self.local=self.load_record(self.role_store,self.role)
        if self.state is not None:
            exact(self.state,{'phase','binding','original','origins','ticket','call','phaseStatus','steps','intents','initial','cleanup','final'})
            context(self.state['binding']);need(self.state['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned'))
            need(type(self.state['steps']) is list and len(self.state['steps'])<=64 and type(self.state['intents']) is list and len(self.state['intents'])<=256)
        if self.local is None:self.local=dict(sequence=0,last=None,frames=[],images=[],pending=None,published=None,quiet=None,retired=None,abandoned=[])
        exact(self.local,{'sequence','last','frames','images','pending','published','quiet','retired','abandoned'})
        need(integer(self.local['sequence'],0,1000000000) and type(self.local['frames']) is list and len(self.local['frames'])<=512)
        self.verify_images(self.local,self.role)

    def owner_save(self):self.save(self.store,'owner',self.state)
    def role_save(self):self.save(self.role_store,self.role,self.local)

    @contextmanager
    def serialized(self):
        pending=None
        with self.lock.held():
            try:yield
            except PhasePending as error:pending=error
            except ChatSettling:pending=PhasePending('Original Chat sources have not settled')
        if pending is not None:raise pending

    def runtime(self,owner=None):
        owner=self.state if owner is None else owner
        _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(owner is not None and same(context(binding),owner['binding']) and guard() is not False)
        return binding,guard

    @contextmanager
    def peer(self,*,read_only=True,attach_files=True):
        self.runtime();peer=self.adapter._chat_peer(self.selector,self.run,self.config['peer'],read_only=read_only,attach_files=attach_files)
        try:yield peer
        finally:peer.detach()

    def phase(self,*,retired=False):
        status=self.source.status(self.state['phaseStatus'] if self.state else None)
        if self.state is not None:self.state['phaseStatus']=status
        if not status['active']:
            if retired:return status
            raise PhaseRetired(status)
        active=self.source.read(status);need(active['ticket']==status['activations'][-1]['ticket'])
        return active

    def ui(self):
        def intent(value):
            self.runtime();need(len(self.state['intents'])<256);self.state['intents'].append(deepcopy(value));self.owner_save()
        return self.adapter._chat_controls(self.selector,intent,self.run)

    def tablet(self):
        native,_s,_b,_g,_i=self.adapter.normal_feature_runtime(self.selector,read_only=False)
        return PhoneScriptUI(native,'io.github.noah_be.overte.phone')

    def history(self,operation,previous=None):
        reader=self.adapter._chat_history(self.selector,read_only=operation=='inspect')
        if previous is not None:reader.restore_source(previous)
        return reader.perform(self.run,operation)

    def step(self,kind,perform,observed):
        found=[row for row in self.state['steps'] if row['kind']==kind];need(len(found)<=1)
        if found:
            if found[0]['phase']=='observed':return
            need(found[0]['phase']=='issued')
        else:
            row=dict(kind=kind,phase='issued');self.state['steps'].append(row);self.owner_save()
            perform()
        start=self.monotonic()
        for attempt in range(81):
            try:ready=observed()
            except ChatSettling:ready=False
            if ready:
                next(row for row in self.state['steps'] if row['kind']==kind)['phase']='observed';self.owner_save();return
            now=self.monotonic();need(number(now,start,start+10) and attempt<80);self.sleep(.125)
        raise NativeUIError('Original Chat input effect was not observed')

    def prepare(self):
        need(self.role=='primary')
        if self.state is None:
            _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True);guard()
            need(self.role_store.read() is None and self.role_file('actor').read() is None and self.adapter.chat_capture_store(self.selector).read() is None
                 and self.file('peer-capture').read() is None and self.file('peer-files').read() is None)
            view=self.adapter._chat_view(self.selector,read_only=True).read(self.run)
            need(not view['source']['tabletShown'] and not view['source']['ui']['present'] and not view['source']['editorFocused'] and not view['source']['editorHasDraft']
                 and view['source']['keyboard'].get('available') is True and view['source']['keyboard']['visible'] is False
                 and view['source']['storage']['count']==0)
            original=self.adapter._chat_history(self.selector,read_only=True).perform(self.run,'inspect')
            need(not original['source']['scopePresent'] and not original['source']['retired'])
            self.state=dict(phase='preparing',binding=deepcopy(context(binding)),original=self.blob(dict(view=view,history=original)),origins={},ticket=None,
                            call=None,phaseStatus=None,steps=[],intents=[],initial=None,cleanup=None,final=None)
            self.owner_save()
        if self.state['phase']!='preparing':self.runtime();return
        original=self.blob(reference=self.state['original'])
        if 'history' not in self.state['origins']:
            self.state['origins']['history']=dict(phase='issued',source=None);self.owner_save()
        actual=self.history('inspect',original['history'])
        if not actual['source']['scopePresent']:
            actual=self.history('capture',actual)
        need(actual['source']['scopePresent'] and not actual['source']['retired']
             and actual['source']['originalSha256']==original['history']['source']['currentSha256']
             and actual['source']['originalKind']==original['view']['source']['storage']['kind'])
        self.state['origins']['history']=dict(phase='observed',source=actual);self.owner_save()
        primary=self.adapter._chat_capture(self.selector,self.run).observe()
        with self.peer(read_only=False) as peer:
            owner=ChatCaptureOwner(self.file('peer-capture'),peer.binding,peer.process.guard)
            secondary=OwnedChatCapture(peer.receive,owner,self.run).observe()
            previous=self.state['origins'].get('peer')
            if previous is None:
                initial=peer.control.perform(self.run,'inspect');need(not initial['source']['leasePresent'] and not initial['source']['restored'])
                self.state['origins']['peer']=dict(phase='issued',source=initial);self.owner_save()
            else:peer.control.restore_source(previous['source'])
            source=peer.control.perform(self.run,'inspect')
            if not source['source']['leasePresent']:source=peer.control.perform(self.run,'lease')
            start=self.monotonic()
            while not source['source']['admitted']:
                need(self.monotonic()-start<5);self.sleep(.125);source=peer.control.perform(self.run,'inspect')
            need(source['source']['selfSha256']==secondary['source']['selfSha256'])
            self.state['origins']['peer']=dict(phase='observed',source=source);self.owner_save()
            mixer=peer.mixer();need(mixer['running'])
        self.state['origins']['primary']=primary;self.state['origins']['secondary']=secondary;self.owner_save()
        frame=self.frame(previous=None,initial=True)
        need(frame['state']==dict(draft='',messages=[],localMessages=[],domainMessages=[],peerMessages=[],channel='none',mixerConnected=True,focused=False,keyboard=False,open=False))
        feet=frame['avatar']['source']['pose']['feetPosition'];position=frame['peerControl']['source']['position']
        need(math.dist(feet,[position[k] for k in 'xyz'])<10)
        self.state.update(initial=self.blob(frame),phase='baseline');self.owner_save()

    def frame(self,previous=None,*,initial=False,cleaned=None):
        self.runtime();started=self.monotonic()
        if previous is None and self.local['last'] is not None:previous=self.blob(reference=self.local['last'])
        if previous is None and self.state['initial'] is not None:previous=self.blob(reference=self.state['initial'])
        def original(reader,key,read):
            if previous is not None:reader.restore_source(previous[key])
            return read(reader)
        view=original(self.adapter._chat_view(self.selector,read_only=True),'view',lambda r:r.read(self.run))
        primary=original(self.adapter._chat_receive(self.selector,read_only=True),'primary',lambda r:r.perform(self.run,'inspect'))
        history=original(self.adapter._chat_history(self.selector,read_only=True),'history',lambda r:r.perform(self.run,'inspect'))
        with self.peer() as peer:
            secondary=original(peer.receive,'peer',lambda r:r.perform(self.run,'inspect'))
            control=original(peer.control,'peerControl',lambda r:r.perform(self.run,'inspect'));mixer=peer.mixer()
            need(secondary['processId']==int(peer.binding['processIdentity'].split(':')[0]))
        roots=self.adapter._script_roots(self.selector,read_only=True)
        if previous is not None:roots.restore(previous['roots'])
        roots=roots.read(previous['roots']['sequence'] if previous is not None else 0)
        scripts=self.adapter._script_execution_observer(self.selector,read_only=True)
        if previous is not None:scripts.restore_history([previous['scripts']])
        scripts=scripts.read(previous['scripts']['sequence'] if previous is not None else 0,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True)
        code=script_identity(roots,scripts,self.pins['chat'])
        if previous is not None:need(code==previous['code'])
        native=self.adapter._native_feature_observer(self.selector,read_only=True)
        if previous is not None:
            native.instance=previous['native']['instance'];native.sequence=previous['native']['sequence'];native.lifecycle=previous['native']['lifecycle']
        native_value=native.read(native.sequence)
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True)
        if previous is not None:avatar.restore([previous['avatar']])
        avatar=avatar.read()
        touch=self.adapter._touch_state_observer(self.selector,read_only=True)
        if previous is not None:touch.restore([previous['touch']])
        touch=touch.read();touch_released(touch)
        value=dict(view=view,primary=primary,peer=secondary,peerControl=control,history=history,mixer=mixer,roots=roots,scripts=scripts,
                   code=code,native=native_value,avatar=avatar,touch=touch)
        if cleaned is None:cleaned=self.state['phase']=='cleaned'
        value['state']=measurement(self.run,value,cleaned=cleaned)
        for source in (view,primary,secondary,control,history,roots,scripts,native_value,avatar,touch):fresh(source['capturedEpochMs'],native.clock_ms())
        need(self.monotonic()-started<10)
        if previous is not None:
            need(history['source']['configSha256']==previous['history']['source']['configSha256']
                 and view['source']['storage']['configSha256']==previous['view']['source']['storage']['configSha256'])
        if self.state['initial'] is not None:
            baseline=self.blob(reference=self.state['initial'])
            need(math.dist(avatar['source']['pose']['feetPosition'],baseline['avatar']['source']['pose']['feetPosition'])<=.08)
            for key in ('primary','peer'):

                need(value[key]['instance']==baseline[key]['instance'] and value[key]['source']['selfSha256']==baseline[key]['source']['selfSha256'])
        if not initial:
            self.local['last']=self.blob(value);self.local['frames'].append(self.local['last']);self.role_save()
        return value

    def act(self,value):
        call=deepcopy(arguments('feature.chat.act',value));need(self.role=='primary' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            self.load();self.prepare();phase=self.phase();need(phase['ticket']==call['ticket'] and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs']))
            if self.state['ticket']==call['ticket']:
                need(same(self.state['call'],call))
                if self.state['phase']=='active':return {'performed':True}
            else:
                need(self.state['phase'] in ('baseline','active'));before=self.frame();self.state.update(phase='acting',ticket=call['ticket'],call=call,steps=[])
                self.state['cleanup']=self.blob(before);self.owner_save()
            self.deliver(call)
            self.state['phase']='active';self.owner_save();return {'performed':True}

    def deliver(self,call):
        verb,inputs=call['verb'],call['inputs'];before=self.blob(reference=self.state['cleanup'])
        def current():return self.frame()
        if verb=='open':
            self.step('tablet-open',lambda:self.tablet().open_tablet() if not self.tablet().tablet_visible() else None,lambda:self.tablet().tablet_visible())
            self.step('open',lambda:self.ui().open(),lambda:current()['state']['open'])
        elif verb=='close':self.step('close',lambda:self.ui().close(),lambda:not current()['state']['open'])
        elif verb=='select-channel':self.step('select',lambda:self.ui().select_channel(inputs['channel']),lambda:current()['state']['channel']==inputs['channel'])
        elif verb=='type':
            def recover_or_type():
                ui=self.ui();captured=ui.capture();editor=ui.row(captured,'chat.input',enabled=False)
                if editor is not None and editor['focused']:ui.input('chat.input','replace',inputs['text'])
                else:ui.type(inputs['text'])
            if any(row['kind']=='type' and row['phase']=='issued' for row in self.state['steps']):
                current_type=current()['state']
                if not all(current_type[k]==v for k,v in dict(draft=inputs['text'],focused=True,keyboard=True).items()):recover_or_type()
            self.step('type',recover_or_type,lambda:all(current()['state'][k]==v for k,v in dict(draft=inputs['text'],focused=True,keyboard=True).items()))
        elif verb=='send':
            def sent():
                frame=current();channel=before['state']['channel'];text=before['state']['draft']
                if frame['state']['draft']!='' or frame['state'][channel+'Messages']!=before['state'][channel+'Messages']+[text]:return False
                events=frame['primary']['source']['events'][len(before['primary']['source']['events']):]
                if len(events)!=1 or events[0]['senderSha256']!=frame['primary']['source']['selfSha256'] or events[0]['text']!=text or events[0]['channel']!=channel:return False
                need(events[0]['localOnly'] is (not before['state']['mixerConnected']))
                return frame['state']['peerMessages']==before['state']['peerMessages']+([text] if before['state']['mixerConnected'] else [])
            self.step('send',lambda:self.ui().send(),sent)
        elif verb in ('peer-send','peer-send-distant'):
            suffix='hidden' if inputs['text'].startswith('hidden-') else 'reply'
            operation='send-local-distant' if verb=='peer-send-distant' else 'send-'+inputs['channel']+'-'+suffix
            def send_peer():
                with self.peer(read_only=False) as peer:
                    peer.control.restore_source(before['peerControl']);peer.control.perform(self.run,operation)
            def received():
                frame=current();c=frame['peerControl']['source'];p=frame['primary']['source'];q=frame['peer']['source']
                if c['inputSequence']!=before['peerControl']['source']['inputSequence']+1 or c['lastInput']['operation']!=operation:return False
                events=p['events'][len(before['primary']['source']['events']):]
                if len(events)!=1 or events[0]['text']!=inputs['text'] or events[0]['channel']!=inputs['channel'] or events[0]['senderSha256']!=q['selfSha256'] or events[0]['localOnly']:return False
                if verb=='peer-send-distant':
                    feet=frame['avatar']['source']['pose']['feetPosition'];position=c['lastInput']['position']
                    return math.dist(feet,[position[k] for k in 'xyz'])>=30 and all(frame['state'][k]==before['state'][k] for k in ('localMessages','domainMessages','messages'))
                return frame['state'][inputs['channel']+'Messages']==before['state'][inputs['channel']+'Messages']+[inputs['text']]
            self.step('peer-send',send_peer,received)
        elif verb in ('network-remove-mixer','network-restore-mixer'):
            online=verb=='network-restore-mixer'
            def transition():
                with self.peer(read_only=False) as peer:peer.mixer('online' if online else 'offline')
            def changed():
                frame=current();present=frame['state']['mixerConnected']
                if present!=online or frame['mixer']['generation']<=before['mixer']['generation']:return False
                if online:
                    initial=self.blob(reference=self.state['initial'])
                    need(frame['primary']['source']['mixerSha256']!=initial['primary']['source']['mixerSha256'])
                return True
            self.step('mixer',transition,changed)
        elif verb=='background-resume':
            self.step('background',lambda:self.adapter.invoke(self.selector,'lifecycle.background',{}),
                      lambda:self.adapter._graphics_lifecycle_status(self.selector,self.state['binding'])['foreground'] is False)
            self.step('resume',lambda:self.adapter.invoke(self.selector,'app.launch',{}),
                      lambda:self.adapter._graphics_lifecycle_status(self.selector,self.state['binding'])['foreground'] is True)
            frame=current();need(frame['native']['lifecycle']['backgrounds']>before['native']['lifecycle']['backgrounds']
                and frame['native']['lifecycle']['activations']>before['native']['lifecycle']['activations'])
        elif verb=='await-no-replay':
            frame=current();need(frame['state']==before['state'] and frame['primary']['source']['events']==before['primary']['source']['events']
                and frame['peer']['source']['events']==before['peer']['source']['events'])
        else:need(False)

    def acquire(self,phase,after=0):
        need(integer(after) and after<=self.local['sequence']);frame=self.frame()
        need(all(frame[key]['capturedEpochMs']>=phase['afterEpochMs'] for key in ('view','primary','peer','peerControl','history','roots','scripts','native','avatar','touch')))
        frame['phase']=deepcopy(phase['status'])
        sequence=self.local['sequence']+1;artifacts=[]
        if frame['state']['open']:
            artifacts.append(self.screenshot(self.state,phase['ticket'],sequence,self.role,self.local))
            after_view=self.adapter._chat_view(self.selector,read_only=True);after_view.restore_source(frame['view']);after_view=after_view.read(self.run)
            need(same(after_view['source'],frame['view']['source']))
        resources=[]
        if frame['state']['open']:resources.append('panel:chat')
        if frame['state']['focused']:resources.append('input:chat-editor')
        if frame['state']['keyboard']:resources.append('input:chat-keyboard')
        # These are product input/surface resources. Measurement caches and
        # the controlled peer/history fixture leases remain durably owned and
        # are verified separately by mandatory v18 retirement, including when
        # the product baseline itself has no UI resources.
        value=result('feature.chat.observe',dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=sequence,
            capturedEpochMs=frame['native']['capturedEpochMs'],state=frame['state'],artifacts=artifacts,resources=resources,lifecycle=frame['native']['lifecycle']))
        end=self.phase();need(end['ticket']==phase['ticket'] and end['verb']==phase['verb'] and same(end['inputs'],phase['inputs']))
        self.local.update(sequence=sequence,last=self.blob(frame));self.role_save();return value

    def observe(self,value):
        call=arguments('feature.chat.observe',value);need(self.role=='primary' and call['runId']==self.run)
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            self.load();self.prepare();phase=self.phase()
            if phase['verb'] not in ('baseline','cleanup'):need(self.state['phase']=='active' and self.state['ticket']==phase['ticket'])
            return self.acquire(phase,call['afterSequence'])

    def publication(self,phase):
        pending=self.local['pending']
        if pending is None:return
        exact(pending,{'sample','frame','issued'});sample=pending['sample'];frame=self.blob(reference=pending['frame'])
        need(type(pending['issued']) is bool and sample['facts']==projection(AREA,frame['state']) and sample['capturedEpochMs']==frame['native']['capturedEpochMs']
             and sample['ticket']==frame['phase']['activations'][-1]['ticket'])
        def accepted():
            original=self.source.client.request('/runs/'+self.run)
            exact(original,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
            need(type(original['schemaVersion']) is int and original['schemaVersion']==1 and original['runId']==self.run and original['area']==AREA
                 and type(original['entries']) is list and len(original['entries'])<=512)
            fresh(original['sampleEpochMs'],self.source.epoch_ms())
            rows=[row for row in original['entries'] if row['actorSequence']==sample['actorSequence']]
            need(len(rows)<=1)
            if rows:
                row=rows[0];exact(row,set(sample)|{'sequence','receivedEpochMs'});need(all(same(row[k],sample[k]) for k in sample)
                    and integer(row['sequence'],1) and number(row['receivedEpochMs'],sample['capturedEpochMs'],original['sampleEpochMs']+250))
                self.local.update(pending=None,published=dict(sample=deepcopy(sample),receipt=deepcopy(row)));self.role_save();return True
            return False
        if accepted():return
        expired=self.source.epoch_ms()-sample['capturedEpochMs']>1500
        if phase['ticket']!=sample['ticket'] or expired:
            need(len(self.local['abandoned'])<512);self.local['abandoned'].append(self.blob(dict(original=pending,phase=phase['status'],reason='phase-changed' if phase['ticket']!=sample['ticket'] else 'expired')))
            self.local['pending']=None;self.role_save();return
        if not pending['issued']:
            pending['issued']=True;self.role_save()
            self.source.client.request('/runs/'+self.run+'/samples',sample)
            if accepted():return
        raise PhasePending('Original Chat actor publication is awaiting its own journal entry')

    def publish(self):
        need(self.role=='actor')
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            self.load()
            if self.state is None or self.state['phase'] in ('preparing','acting','cleaning'):raise PhasePending('Original Chat input transaction has not completed')
            phase=self.phase();self.publication(phase)
            if phase['verb'] not in ('baseline','cleanup') and not (self.state['phase']=='active' and self.state['ticket']==phase['ticket']):
                raise PhasePending('Original Chat input transaction has not completed')
            value=self.acquire(phase)
            sample=dict(ticket=phase['ticket'],actor='owned-observer',actorSequence=value['sequence'],capturedEpochMs=value['capturedEpochMs'],facts=projection(AREA,value['state']))
            self.local['pending']=dict(sample=sample,frame=self.local['last'],issued=False);self.role_save();self.publication(phase);return value

    def cleanup(self,value):
        call=arguments('feature.chat.cleanup',value);need(self.role=='primary' and call['runId']==self.run)
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            self.load()
            if self.state is None:return {'performed':True}
            # Recover an already journaled acquisition before retiring its actual
            # native leases. Missing required sources keep the original journal.
            if self.state['phase']=='preparing':self.prepare()
            phase=self.phase();need(phase['verb']=='cleanup')
            if self.state['phase']=='cleaned':
                self.state['ticket']=phase['ticket'];self.owner_save();self.frame(cleaned=True);return {'performed':True}
            self.state.update(phase='cleaning',ticket=phase['ticket'])
            if self.state['final'] is None:self.state['final']=dict(stage='ui',ui=None,history=None,peer=None,mixer=None)
            self.owner_save();progress=self.state['final'];original=self.blob(reference=self.state['original'])
            if progress['stage']=='ui':
                source=self.adapter._chat_view(self.selector,read_only=True).read(self.run)
                need(source['source']['storage']['unowned']==0)
                last=self.state['intents'][-1] if self.state['intents'] else None
                already_closed=(not source['source']['ui']['present'] and source['source']['storage']['count']==0
                    and source['source']['storage']['kind']=='null' and last is not None and last['controlId']=='chat.close')
                if not already_closed:
                    if not source['source']['ui']['present']:
                        if not self.tablet().tablet_visible():self.tablet().open_tablet()
                        self.ui().open()
                    source=self.adapter._chat_view(self.selector,read_only=True).read(self.run);ui=source['source']['ui']
                    need(source['source']['storage']['unowned']==0)
                    if source['source']['storage']['kind']!='null' or source['source']['storage']['count'] or ui['localRowCount'] or ui['domainRowCount']:
                        self.ui().erase_history()
                    self.ui().close()
                self.tablet().native.release_actions()
                if not original['view']['source']['tabletShown']:self.tablet().close_tablet();self.tablet().wait_tablet_absent()
                current=self.adapter._chat_view(self.selector,read_only=True).read(self.run)
                need(not current['source']['ui']['present'] and current['source']['storage']['count']==0
                    and not current['source']['editorHasDraft'] and not current['source']['editorFocused'] and not current['source']['keyboard'].get('visible',True))
                progress.update(stage='history',ui=self.blob(current));self.owner_save()
            if progress['stage']=='history':
                source=self.history('inspect',self.state['origins']['history']['source'])
                if not source['source']['restored']:source=self.history('restore',source)
                self.state['origins']['history']['source']=source;self.owner_save()
                if not source['source']['retired']:source=self.history('retire',source)
                self.state['origins']['history']['source']=source;progress.update(stage='peer',history=self.blob(source));self.owner_save()
            if progress['stage']=='peer':
                with self.peer(read_only=False) as peer:
                    peer.control.restore_source(self.state['origins']['peer']['source']);source=peer.control.perform(self.run,'inspect')
                    if not source['source']['restored']:source=peer.control.perform(self.run,'restore')
                    self.state['origins']['peer']['source']=source;progress.update(stage='mixer',peer=self.blob(source));self.owner_save()
            if progress['stage']=='mixer':
                with self.peer(read_only=False) as peer:
                    controller=peer.mixer()
                    if not controller['running']:controller=peer.mixer('online')
                    started=self.monotonic()
                    for attempt in range(81):
                        primary=self.adapter._chat_receive(self.selector,read_only=True).perform(self.run,'inspect')
                        secondary=peer.receive.perform(self.run,'inspect')
                        p,q=primary['source'],secondary['source']
                        if p['mixerPresent'] and q['mixerPresent'] and p['mixerSha256']==q['mixerSha256']:break
                        need(self.monotonic()-started<10 and attempt<80);self.sleep(.125)
                    initial=self.blob(reference=self.state['initial'])
                    if controller['generation']>initial['mixer']['generation']:
                        need(p['mixerSha256']!=initial['primary']['source']['mixerSha256'])
                    progress.update(stage='peer-cache',mixer=self.blob(dict(controller=controller,primary=primary,peer=secondary)));self.owner_save()
            if progress['stage']=='peer-cache':
                with self.peer(read_only=False) as peer:
                    OwnedChatCapture(peer.receive,ChatCaptureOwner(self.file('peer-capture'),peer.binding,peer.process.guard),self.run).retire()
                progress['stage']='primary-cache';self.owner_save()
            if progress['stage']=='primary-cache':
                self.adapter._chat_capture(self.selector,self.run).retire();progress['stage']='verified';self.owner_save()
            need(progress['stage']=='verified')
            proof=self.frame(cleaned=True);self.state.update(phase='cleaned',cleanup=self.blob(proof));self.owner_save()
            return {'performed':True}

    def retire_actor(self):
        need(self.role=='actor')
        with self.serialized(),self.adapter.existing_input_session(self.selector):
            self.load();need(self.state is not None and self.state['phase']=='cleaned')
            status=self.phase(retired=True);need(not status['active'])
            frame=self.frame(cleaned=True)
            if self.local['pending'] is not None:
                # Closure fences late publisher requests. Preserve the exact
                # uncertain original and closure; never invent an acceptance.
                self.local['abandoned'].append(self.blob(dict(original=self.local['pending'],phase=status,reason='fixture-retired')))
                self.local['pending']=None
            if self.local['published'] is not None and self.local['published']['sample']['ticket']==self.state['ticket']:
                need(frame['state']==self.local['published']['sample']['facts'])
            if self.local['retired'] is None:
                self.local['retired']=dict(status=status,frame=self.blob(frame));self.role_save()
            return True

    def final_sources(self,plan):
        self.runtime();need(not self.source.status(plan['closure'])['active'])
        original=self.blob(reference=plan['proof'])
        view=self.adapter._chat_view(self.selector,read_only=True);view.restore_source(original['view']);view=view.read(self.run)
        history=self.adapter._chat_history(self.selector,read_only=True);history.restore_source(original['history']);history=history.perform(self.run,'inspect')
        primary=self.adapter._chat_receive(self.selector,read_only=True);primary.restore_source(original['primary']);primary=primary.perform(self.run,'inspect')
        need(view['source']==original['view']['source'] and history['source']==original['history']['source']
             and primary['source']['retired'] and not primary['source']['scopePresent'] and not primary['source']['events'])
        touch=self.adapter._touch_state_observer(self.selector,read_only=True);touch.restore([original['touch']]);touch=touch.read();touch_released(touch)
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True);avatar.restore([original['avatar']]);avatar=avatar.read()
        need(math.dist(avatar['source']['pose']['feetPosition'],original['avatar']['source']['pose']['feetPosition'])<=.08)
        native=self.adapter._native_feature_observer(self.selector,read_only=True)
        native.instance=original['native']['instance'];native.sequence=original['native']['sequence'];native.lifecycle=original['native']['lifecycle']
        lifecycle=native.read(native.sequence)
        for value in (view,history,primary,touch,avatar,lifecycle):fresh(value['capturedEpochMs'],native.clock_ms())
        need(self.adapter._graphics_lifecycle_status(self.selector,self.state['binding'])['foreground'] is True)
        need(self.adapter.chat_capture_store(self.selector).read() is None and self.file('peer-capture').read() is None)
        return True

    def final_peer(self,plan):
        retirement=plan['peerRetirement'];need(retirement is not None)
        with self.peer(read_only=False,attach_files=self.file('peer-files').read() is not None) as peer:
            need(same(peer.binding,retirement['binding']) and same(peer.source_stamp,retirement['sourceStamp']) and peer.source_sha==retirement['sourceSha256'])
            if peer.files is not None:peer.files.close()
            from adapters.chat_actor_files import COMMAND,RESULT
            need(self.file('peer-files').read() is None and not (peer.directory/COMMAND).exists() and not (peer.directory/RESULT).exists()
                 and peer.process.released(retirement['resultNode']) is True)
        return True

    def finalize(self):
        need(self.role=='primary');started=previous=self.monotonic()
        for attempt in range(161):
            now=self.monotonic();need(number(now,previous,started+45));previous=now;pending=False
            with self.serialized(),self.adapter.existing_input_session(self.selector):
                self.load();archive=self.completed.read();plan=self.load_record(self.retirement_store,'retirement')
                if self.state is None and plan is None:
                    need(archive is not None and archive['runId']==self.run and self.role_store.read() is None and self.role_file('actor').read() is None)
                    plan=self.blob(reference=archive['retirement']);self.state=unpack(self.blob(reference=plan['owner'])['payload'])[0]
                    self.final_sources(plan);self.final_peer(plan);return True
                if plan is None:
                    need(self.state is not None and self.state['phase']=='cleaned');closed=self.phase(retired=True);need(not closed['active'])
                    actor=self.load_record(self.role_file('actor'),'actor')
                    need(actor is not None and actor['pending'] is None)
                    if actor['retired'] is None:pending=True
                    else:
                        need(not actor['retired']['status']['active'])
                        actor_frame=self.blob(reference=actor['retired']['frame']);measurement(self.run,actor_frame,cleaned=True)
                        if actor['published'] is not None and actor['published']['sample']['ticket']==self.state['ticket']:
                            need(actor_frame['state']==actor['published']['sample']['facts'])
                        frame=self.frame(cleaned=True)
                        plan=dict(owner=self.blob(self.previous[self.store.path]),roles={role:self.blob(self.role_file(role).read()) for role in ('primary','actor')},
                                  proof=self.blob(frame),closure=closed,phase='retiring',peerRetirement=None)
                        self.save(self.retirement_store,'retirement',plan)
                else:
                    if self.state is None:self.state=unpack(self.blob(reference=plan['owner'])['payload'])[0]
                if not pending:
                    self.final_sources(plan)
                    if plan['peerRetirement'] is None:
                        with self.peer(read_only=False) as peer:
                            source=peer.receive.perform(self.run,'inspect');need(source['source']['retired'] and not source['source']['scopePresent'])
                            actual=peer.files._owned();need(actual['result']['retired'])
                            plan['peerRetirement']=dict(binding=peer.binding,sourceStamp=peer.source_stamp,sourceSha256=peer.source_sha,
                                resultNode={key:actual['result']['stamp'][key] for key in ('device','inode')})
                            self.save(self.retirement_store,'retirement',plan)
                    self.final_peer(plan)
                    for role,record in plan['roles'].items():
                        if record is not None:self.verify_images(unpack(self.blob(reference=record)['payload'])[0],role)
                    record=dict(chatRetirementVersion=VERSION,runId=self.run,binding=self.state['binding'],retirement=self.blob(plan))
                    if archive is None:self.completed.write(record,None)
                    else:need(same(archive,record))
                    need(same(self.completed.read(),record))
                    for role,old in plan['roles'].items():
                        store=self.role_file(role);current=store.read();original=self.blob(reference=old);need(current is None or same(current,original))
                        if current is not None:store.discard(current)
                        need(store.read() is None)
                    current=self.store.read();need(current is None or same(current,self.blob(reference=plan['owner'])))
                    if current is not None:self.store.discard(current)
                    need(self.store.read() is None);old=self.retirement_store.read()
                    if old is not None:self.retirement_store.discard(old)
                    need(self.retirement_store.read() is None and self.file('peer-files').read() is None);return True
            need(attempt<160);self.sleep(.25)
        return False
