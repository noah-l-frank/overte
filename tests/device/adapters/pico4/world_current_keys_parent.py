"""One opt-in normal keyboard component in the unchanged World acting Parent.

Focus2 explicitly retains a historical gesture intent and reads fresh focus.
Key1 types only the representable prefix of the actual active Common action.
Unsupported Unicode leaves that SAME action acting; no whole-step success.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import hashlib
from adapters.native_feature_observation import exact,integer,need,number,decode
from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.pico4.world_current_focus_parent import FIELD as FOCUS,focus_matches
from adapters.pico4.world_current_gesture import receipt,calibration
from adapters.pico4.world_current_keyboard import units
from adapters.pico4.world_current_keyboard import PicoWorldCurrentKeyboard
from adapters.pico4.world_current_keys_originals import WorldCurrentKeysOriginals,FILE as ORIGINALS_FILE
from adapters.script_journey.history import canonical
from adapters.pico4.world_current_document import semantic
from feature_journeys.contract import arguments
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.fixtures import context

KEY='picoWorldCurrentKeyParentVersion'
UNRESOLVED_RAW_ACQUISITIONS=[]


def reference(value):
    exact(value,{'parts','bytes','sha256'})
    need(type(value['parts']) is list and 0<len(value['parts'])<=128 and all(integer(i,0,511) for i in value['parts'])
         and value['parts']==list(range(value['parts'][0],value['parts'][-1]+1))
         and integer(value['bytes'],1,524288) and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']))


def validate_carrier(value,row,owner,run,url):
    field=FOCUS if FOCUS in value else KEY
    exact(value,{field,'ticket','kind','phase','hostIdentity','operationStarted','operationEpochMs',
        'character','keyEntity','records','calibration','intent','publication','effect','neutral','blockedCodepoint','callStartedMonotonic'})
    need(type(value[field]) is int and value[field]==(2 if field==FOCUS else 1) and value['ticket']==row['ticket']
         and value['kind'] in ('focus','character','caps','layer') and ((field==FOCUS)==(value['kind']=='focus'))
         and value['phase'] in ('planned','calibrated','published','effected','blocked')
         and type(value['hostIdentity']) is str and value['hostIdentity'] and number(value['operationStarted'],0,1e15)
         and number(value['callStartedMonotonic'],0,value['operationStarted'])
         and integer(value['operationEpochMs'],1) and type(value['records']) is list and len(value['records'])<=128)
    for ref in value['records']:reference(ref)
    for name in ('calibration','intent','publication','effect','neutral'):
        if value[name] is not None:reference(value[name]);need(value[name] in value['records'])
    if value['kind']=='focus':need(value['character'] is None and value['keyEntity'] is None)
    else:need(value['keyEntity'] is None and value['phase']=='planned' or type(value['keyEntity']) is str
              and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['keyEntity']))
    if value['kind']=='character':need(type(value['character']) is str and len(value['character'])==1 and 32<=ord(value['character'])<=126)
    else:need(value['character'] is None)
    phase=value['phase']
    if phase=='planned':need(all(value[k] is None for k in ('calibration','intent','publication','effect')) and row['envelope'] is None and not row['complete'])
    else:need(value['calibration'] is not None)
    if row['envelope'] is not None:need(value['intent'] is not None)
    if phase in ('published','effected','blocked'):need(value['publication'] is not None and row['envelope'] is not None)
    if phase in ('effected','blocked'):need(value['effect'] is not None and value['neutral'] is not None and row['complete'])
    else:need(not row['complete'])
    need(value['blockedCodepoint'] is None or phase=='blocked' and type(value['blockedCodepoint']) is str
         and re.fullmatch('[0-9a-f]{4,6}',value['blockedCodepoint']))
    activation=row['anchor']['packet']['activations'][-1]
    need(activation['ticket']==value['ticket'] and activation['stimulus']['verb']=='focus-type'
         and value['operationStarted']<=row['anchor']['hostMonotonic'])


def validate_sequence(rows,owner):
    focus=None;typed='';previous=None
    for row in rows:
        value=row['original']
        if value.get(FOCUS)==2:
            need(focus is None);focus=row;previous=row;continue
        if KEY not in value:continue
        need(focus is not None and focus['complete'] and previous['complete']
             and all(value[k]==focus['original'][k] for k in ('ticket','hostIdentity','callStartedMonotonic'))
             and value['operationStarted']>=previous['original']['operationStarted'])
        activation=row['anchor']['packet']['activations'][-1];desired=activation['stimulus']['inputs']['text']
        if value['kind']=='character':
            need(len(typed)<len(desired) and value['character']==desired[len(typed)])
            if row['complete']:typed+=value['character']
        if value['phase']=='blocked':
            need(len(typed)<len(desired) and not 32<=ord(desired[len(typed)])<=126
                 and value['blockedCodepoint']==format(ord(desired[len(typed)]),'04x'))
        previous=row


def consumed(trace,key,before,after):
    """Join actual vr-key/Qt/Native/JNI/Java originals, independently of DOM."""
    need(trace.arm_packet is not None and decode(trace.last['raw'])['source']['terminal'])
    expected=key['effectiveUtf16Hex'];matches=[];releases=[]
    for event in trace.events.values():
        if {'keyboard-event','application-target'}<=set(event):
            released=event['keyboard-event'][1];application=event['application-target'][1]
            if released['eventType']=='release':
                need(event['keyboard-event'][0]==event['application-target'][0]=='vr-key'
                     and released['keyEntity']==key['id'] and released['keyType']==key['type'] and released['modifiers']==0
                     and released['textUtf16Hex']==expected and released['keyboardObject']==after['traceKeyboardObject']
                     and application['eventType']=='release' and application['requestedEntity']==released['requestedEntity']
                     and application['handlerMatchesWindow'] and application['focusItemMatches'])
                releases.append(released)
        if not {'keyboard-event','application-target','native-input','jni-command','java-entry','java-consume'}<=set(event):continue
        need(all(v[0]=='vr-key' for v in event.values()))
        key_event=event['keyboard-event'][1];app=event['application-target'][1];native=event['native-input'][1]
        entry=event['java-entry'][1];jni=event['jni-command'][1]
        if key_event['eventType']!='press':continue
        need(key_event['keyEntity']==key['id'] and key_event['keyType']==key['type'] and key_event['modifiers']==0
             and key_event['textUtf16Hex']==expected and app['eventType']=='press' and app['requestedEntity']==key_event['requestedEntity']
             and app['handled'] and app['handlerMatchesWindow'] and app['focusItemMatches']
             and native['accepted'] and native['eventType']=='key-press' and native['key']==key_event['key']
             and native['modifiers']==0 and native['textUtf16Hex']==expected
             and entry['isMainThread'] and key_event['keyboardObject']==after['traceKeyboardObject']
             and (before['traceKeyboardObject'] is None or before['traceKeyboardObject']==key_event['keyboardObject']))
        text=bytes.fromhex(jni['commandUtf16Hex']).decode('utf-16-be',errors='strict')
        import json
        need(json.loads(text)=={'text':units(expected)})
        matches.append(key_event)
    need(len(matches)==1 and len(releases)==1 and matches[0]['keyboardObject']==releases[0]['keyboardObject']
         and matches[0]['key']==releases[0]['key'] and matches[0]['requestedEntity']==releases[0]['requestedEntity'])


class PicoWorldCurrentKeysParent:
    def __init__(self,parent):
        self.parent=parent;self.call_started=parent.source.monotonic();self.producer=host_identity();self.failed=False;self.ledger=None;self.expected=None
        self._pass_active=False;self._host_pass=None
        self.native=parent.adapter._native_feature_observer(parent.target,read_only=True)
        self.operation=None;self.operation_epoch=None;self.call=None;self.started=None;self.created=None

    def clock(self):
        self.external()
        need(not self.failed and self.producer==host_identity())
        now=self.parent.source.monotonic();epoch=self.native.clock_ms();ended=self.parent.source.monotonic()
        need(number(now,self.call_started,self.call_started+60) and number(ended,now,self.call_started+60))
        if self.started is not None:
            need(number(now,self.started,self.started+120) and number(ended,now,self.started+120)
                 and self.created<=self.parent.source.epoch_ms()<=self.created+120000)
        if self.operation is not None:
            need(number(ended,self.operation,self.operation+5) and integer(epoch,self.operation_epoch,self.operation_epoch+5000))

    def host(self):
        p=self.parent;p.lock.assert_held();p.control()
        need(not self.failed and self.producer==host_identity() and self.expected is not None
             and json_digest(p.store.read())==json_digest(self.expected[0])
             and p.state['phase']=='acting' and json_digest(p.state['active'])==json_digest(self.call))
        if self._pass_active:
            need(self._host_pass is not None);self._host_pass.guard()
        else:need(json_digest(p.pins())==json_digest(self.expected[1]))

    def remember(self):
        if self._pass_active:
            need(self._host_pass is not None);self._host_pass.remember()
        else:
            p=self.parent;observed=p.pins()
            if self.expected is not None:
                old={r['path']:r for r in self.expected[1]};current={r['path']:r for r in observed}
                main=str(p.store.path);root=str(p.root/ORIGINALS_FILE)
                need(set(old)<=set(current) and set(current)-set(old)<=({root} if root not in old else set()))
                for path,row in old.items():
                    if path==main and json_digest(p.disk)!=json_digest(self.expected[0]):
                        need(current[path]['sha256']==hashlib.sha256(canonical(p.disk)+b'\n').hexdigest())
                    elif path==root and current[path]!=row:
                        need(self.ledger is not None);self.ledger.file.guard()
                        need(current[path]['signature']==list(self.ledger.file.stamp)
                             and current[path]['sha256']==hashlib.sha256(self.ledger.file.raw).hexdigest())
                    else:need(current[path]==row)
            self.expected=[deepcopy(p.disk),observed]

    def external(self):need(not self._pass_active)

    def protect_source(self,source):
        """Block direct source/clock/IO reentry before any actual SDK guard."""
        sources=[source]
        if hasattr(source,'focus'):sources.append(source.focus)
        for item in tuple(sources):
            if hasattr(item,'documents'):sources.append(item.documents)
        for item in sources:
            item.guard=self.guard
            for name in ('clock_ms','send','read_raw'):
                original=getattr(item,name)
                def protected(*args,_original=original,**kwargs):self.external();return _original(*args,**kwargs)
                setattr(item,name,protected)
        return source

    def guard(self):
        self.external();p=self.parent;self.clock()
        if p.lock._owner is not None:self.host();p.runtime();p.exact_phase();self.host()
        else:
            with p.lock.held():
                self.host();p.runtime();p.exact_phase();seal=p.seal(p.source.monotonic(),self.native.clock_ms(),[],self.native)
            p.finalize(seal)
        self.clock();return True

    def save(self,update):
        p=self.parent;self.clock()
        with p.lock.held():
            self.host();p.runtime();p.exact_phase();started=p.source.monotonic();requested=self.native.clock_ms()
            state=deepcopy(p.state);update(state['inputs'][-1]);p.save(state);self.remember()
            seal=p.seal(started,requested,[],self.native)
        p.finalize(seal);self.remember();self.clock()

    def retain(self,value):
        self.external();p=self.parent
        # The existing source transport calls this before parsing raw replies.
        with p.lock.held():
            self.host()
            self._pass_active=True;window=None
            try:
                with self.ledger.host_transaction(self.expected[1]) as window:
                    self._host_pass=window;overrun=False
                    if type(value) is dict and type(value.get('raw')) is str and len(value['raw'].encode())>131072:
                        encoded=value['raw'].encode()
                        # The OS adapter has no bounded-read API. Preserve the
                        # actual object, record extent/SHA, then refuse. This
                        # is not a claim of complete durable oversized raw.
                        UNRESOLVED_RAW_ACQUISITIONS.append(value)
                        ref=self.ledger.retain(dict(kind='raw-acquisition-overrun',request=deepcopy(value.get('request')),
                            bytes=len(encoded),sha256=hashlib.sha256(encoded).hexdigest(),durableLiteralLimit=131072))
                        overrun=True
                    else:ref=self.ledger.retain_source(value)
            except BaseException:
                self.failed=True;raise
            finally:self._host_pass=None;self._pass_active=False
            self.expected=[deepcopy(p.disk),deepcopy(window.final_pins)]
            self.host()
            state=deepcopy(p.state);state['inputs'][-1]['original']['records'].append(deepcopy(ref));p.save(state);self.remember()
            need(not overrun)
        self.clock();return ref

    def capacity(self):
        self.external()
        with self.parent.lock.held():self.host();self.ledger.capacity()
        self.clock()

    def source(self):
        self.external();p=self.parent;value=p.adapter.world_prefix_current_source(p.target,p)
        self.protect_source(value)
        value.retain=value.documents.retain=self.retain;value.capacity=value.documents.capacity=self.capacity
        return value

    def neutral(self,envelope):
        self.external();p=self.parent
        # Passive, before the NEXT fresh calibration. Never release/replay.
        self.guard();value=p.adapter.world_prefix_current_neutral(p.target,p,envelope);self.clock()
        return self.retain(dict(kind='original-owned-neutral',envelope=deepcopy(envelope),status=deepcopy(value)))

    def row(self,kind,character=None,key_id=None):
        p=self.parent;self.operation=p.source.monotonic();self.operation_epoch=self.native.clock_ms();self.clock()
        value={FOCUS if kind=='focus' else KEY:2 if kind=='focus' else 1,'ticket':self.call['ticket'],'kind':kind,'phase':'planned',
            'hostIdentity':self.producer,'operationStarted':self.operation,'operationEpochMs':self.operation_epoch,
            'callStartedMonotonic':self.call_started,
            'character':character,'keyEntity':key_id,'records':[],'calibration':None,'intent':None,'publication':None,
            'effect':None,'neutral':None,'blockedCodepoint':None}
        with p.lock.held():self.host();p.input_begin(value);self.remember()

    def gesture(self,source,key_id=None):
        self.external();p=self.parent;original=source.original();ref=self.original_reference(source)
        self.save(lambda row:row['original'].update(phase='calibrated',calibration=ref))
        def intent(value):
            self.external();self.host();stored={k:deepcopy(v) for k,v in value.items() if k!='calibrationOriginal'}
            stored['calibrationReference']=deepcopy(ref)
            intent_ref=self.retain(dict(kind='gesture-intent',original=stored))
            state=deepcopy(p.state);need(state['inputs'][-1]['original']['intent'] is None)
            state['inputs'][-1]['original']['intent']=intent_ref;p.save(state);self.remember();p.input_fence().check()
        def stream(value):self.external();self.host();p.input_fence().stage_intent(value);self.remember()
        def publish(value):self.external();self.host();p.input_fence().before_publish(value);self.host()
        def admission():self.external();self.host();p.runtime();p.exact_phase();p.input_fence().check();self.clock()
        gesture=p.adapter.world_prefix_current_gesture(p.target,p,source,intent,stream_intent=stream,
            before_publish=publish,admission=admission,started=self.operation,requested=self.operation_epoch,key_id=key_id)
        result=gesture.publish();receipt(result)
        stored={k:deepcopy(v) for k,v in result.items() if k!='calibrationOriginal'};stored['calibrationReference']=deepcopy(ref)
        published_ref=self.retain(dict(kind='historical-gesture-receipt',original=stored))
        self.save(lambda row:row['original'].update(phase='published',publication=published_ref));return result

    def original_reference(self,source):
        original=source.original()
        if type(source) is PicoWorldCurrentKeyboard:
            refs=source.original_references()
            for ref in refs.values():reference(ref);need(ref in self.parent.state['inputs'][-1]['original']['records'])
            return self.retain(dict(kind='keyboard-original-bundle',references=refs,sha256=json_digest(original)))
        return self.retain(dict(kind='calibration',original=original))

    def finish_row(self,effect,neutral,*,source=None):
        effect_ref=self.original_reference(source) if source is not None else self.retain(dict(kind='fresh-independent-effect',original=effect))
        def complete(row):row['original'].update(phase='effected',effect=effect_ref,neutral=neutral);row['complete']=True
        self.save(complete)

    def run(self,value):
        self.external();p=self.parent;need(p.role=='primary' and p.lock._owner is None and self.call is None)
        self.call=deepcopy(arguments('feature.world-web.act',value))
        try:
            with p.lock.held(),p.adapter.existing_input_session(p.target):
                p.read();p.control();need(p.state is not None and p.state['phase']=='ready' and p.state['inputs'])
                index=len(p.state['completed']);step=SCENARIOS[p.area]['steps'][index]
                need(self.call['verb']=='focus-type' and self.call['runId']==p.run and self.call['fixtureUrl']==p.url
                     and json_digest(dict(verb=self.call['verb'],inputs=self.call['inputs']))==json_digest(dict(verb=step['verb'],inputs=expand(step['inputs'],context(p.run)))))
                p.observation_admission();phase=p.source.read(p.state['fixture'])
                need(phase['ticket']==self.call['ticket'] and phase['verb']==self.call['verb'] and phase['inputs']==self.call['inputs']
                     and len(phase['status']['activations'])==index+2)
                self.started=min(v['anchor']['hostMonotonic'] for v in p.state['inputs']);self.created=p.state['fixture']['createdEpochMs'];self.clock()
                state=deepcopy(p.state);state.update(phase='acting',active=deepcopy(self.call),fixture=deepcopy(phase['status']));p.save(state);self.remember()
                self.ledger=WorldCurrentKeysOriginals(p,self.host,self.remember);self.remember()
            previous=next((r['envelope'] for r in reversed(p.state['inputs']) if r['envelope'] is not None),None)
            # Previous source/Script input is already an ORIGINAL owned stream.
            # Its passive wait precedes all new per-input1.5 anchors.
            if previous is not None:
                self.guard();p.adapter.world_prefix_current_neutral(p.target,p,previous);self.clock()
            self.row('focus');focus=self.source();focus.read(p.run,p.url,p.state['ownerToken'],'measure-current-ray','text')
            publication=self.gesture(focus);neutral=self.neutral(publication['streamEnvelope'])
            focus.read(p.run,p.url,p.state['ownerToken'],'observe-current-focus','text');current=focus.original()
            self.retain(dict(kind='focus-original',original=current));need(focus_matches(publication['calibrationOriginal'],current))
            focus.require_warm(current);self.finish_row(current,neutral)
            self.operation=self.operation_epoch=None
            keyboard=p.adapter.world_prefix_current_keyboard(p.target,p,retain=self.retain,capacity=self.capacity)
            self.protect_source(keyboard)
            desired=self.call['inputs']['text'];typed='';last=publication['streamEnvelope'];last_row=None
            controls_used=0
            while len(typed)<len(desired):
                character=desired[len(typed)]
                if not 32<=ord(character)<=126:break
                need(len(typed)<64);self.guard();p.adapter.world_prefix_current_neutral(p.target,p,last);self.clock()
                self.row('character',character)
                keyboard.read(p.run,p.url,p.state['ownerToken']);before=decode(keyboard.original()['raw'])['source']['keyboard']
                found=[k for k in before['keys'] if k['layer']==before['activeLayer'] and k['type']==0 and units(k['effectiveUtf16Hex'])==character]
                if not found:
                    # Actual active opposite-case key plus actual CAPS target;
                    # inactive layer labels are deliberately not advertised.
                    opposite=[v for v in before['keys'] if v['type']==0 and units(v['effectiveUtf16Hex']).swapcase()==character]
                    controls=[k for k in before['keys'] if k['type']==1 and k['switchLayer']!=before['activeLayer']]
                    need(len(opposite)==1)
                    need(len(controls)==1 and controls_used<2);key=controls[0];controls_used+=1
                    self.save(lambda row:row['original'].update(kind='caps',character=None,keyEntity=key['id']))
                else:need(len(found)==1);key=found[0];self.save(lambda row:row['original'].update(keyEntity=key['id']))
                kind=p.state['inputs'][-1]['original']['kind'];trace=None
                if kind=='character':
                    trace=p.adapter.world_prefix_current_consumption(p.target,p,keyboard.focus,retain=self.retain,capacity=self.capacity);trace.arm()
                published=self.gesture(keyboard,key['id']);last=published['streamEnvelope'];neutral=self.neutral(last)
                if trace is not None:
                    for _ in range(128):
                        packet=trace.observe(trace.cursor);self.clock()
                        if packet['source']['terminal'] and trace.cursor==packet['source']['availableFrames']:break
                        keyboard.sleep(.02)
                    else:need(False)
                # A new actual focus/DOM + keyboard capture after the original
                # pulse/neutralization. Never reuse/retime the old calibration.
                keyboard.read(p.run,p.url,p.state['ownerToken']);after_packet=decode(keyboard.original()['raw']);after=after_packet['source']['keyboard']
                fresh_focus=keyboard.original()['focusOriginal'];old_focus=published['calibrationOriginal']['focusOriginal']
                need(focus_matches(old_focus,fresh_focus) and before['instance']==after['instance']
                     and after['sequence']>before['sequence'] and after['acceptedSequence']==before['acceptedSequence']+1)
                accepted=after['lastAccepted'];need(accepted['keyEntity']==key['id'] and accepted['keyType']==key['type']
                    and accepted['keyEntityInstance']==key['entityInstance']
                    and accepted['layerBefore']==before['activeLayer'] and accepted['capsBefore']==before['caps']
                    and before['capturedEpochMs']-250<=accepted['epochMs']<=after['capturedEpochMs']+250)
                after_keys=[v for v in after['keys'] if v['id']==key['id']]
                old_editor=decode(old_focus['raw'])['source']['nativeEditor'];new_editor=decode(fresh_focus['raw'])['source']['nativeEditor']
                if kind=='caps':
                    need(after['activeLayer']==key['switchLayer'] and after['caps'] is not before['caps'] and old_editor==new_editor)
                    need(key['id'] in after['layerMembership'][key['layer']]['entityIds'])
                else:
                    need(len(after_keys)==1 and all(after_keys[0][k]==key[k] for k in ('entityInstance','createdEpochUs','parentId','type','layer')))
                    consumed(trace,key,before,after);need(before['activeLayer']==after['activeLayer'] and before['caps']==after['caps'])
                    need(old_editor['text']==typed and old_editor['cursor']==old_editor['anchor']==len(typed)
                         and new_editor['text']==typed+character and new_editor['cursor']==new_editor['anchor']==len(typed)+1)
                    typed+=character
                keyboard.require_warm(keyboard.original());self.finish_row(keyboard.original(),neutral,source=keyboard)
                self.operation=self.operation_epoch=None;last_row=deepcopy(p.state['inputs'][-1]['original'])
            return self.block(typed,desired,last_row)
        except BaseException:
            self.failed=True
            if self.ledger is not None and not self.ledger.closed:
                from adapters.pico4.world_current_keys_originals import UNRESOLVED_HOST_FILES
                if self.ledger.file not in UNRESOLVED_HOST_FILES:UNRESOLVED_HOST_FILES.append(self.ledger.file)
            # Parent/ledger/intents remain in place, including raw-before-fail.
            # No restart, pointer retry, forced input release or generic cleanup.
            raise

    def block(self,typed,desired,last_row):
        need(typed and len(typed)<len(desired) and not 32<=ord(desired[len(typed)])<=126)
        self.save(lambda row:row['original'].update(phase='blocked',blockedCodepoint=format(ord(desired[len(typed)]),'04x')))
        with self.parent.lock.held():self.ledger.finish_host();self.remember()
        self.guard()
        return dict(picoWorldCurrentKeysComponentVersion=1,typedPrefix=typed,blockedCodepoint=format(ord(desired[len(typed)]),'04x'),
                    parentPhase='acting',commonActionComplete=False,ledger=str(self.ledger.store.path))
