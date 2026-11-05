# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Cold declared IME/trace data producer on the SAME original source writer.

No Qt/JNI/Java call or DOM setter is executed. Trace reflects this actual Host
model's event/command values; delivery is not a modeled DOM effect verdict.
"""
from copy import deepcopy
from dataclasses import dataclass
import json,uuid
from adapters.native_feature_observation import need
from adapters.script_journey.history import canonical
from adapters.pico4.assets_raw_archive import quoted_bytes
from adapters.pico4.world_current_ime import command as ime_command
from adapters.pico4.world_current_consumption import command as trace_command

@dataclass(frozen=True)
class HostImeEvent1:
    commit:str
    replacement_start:int
    replacement_length:int
    event_id:str

class WorldHostImeModel1:
    def __init__(self,stage):
        self.stage=stage;self.original=stage.model
        self.arm_call=None;self.frames=[];self.event=None;self.node_effect=None
        self.issued=False;self.sequence=0;self.instance=uuid.uuid4().hex
    def preflight(self,call):
        # No DTO/encoding/hex builder is used to obtain this prospective plan.
        # Existing model44B+2048 metadata entries stays a separate SUM domain.
        # The closed source can refuse an allowed command that will not fit;
        # this does not narrow the original IME/parser payload grammar.
        c=self.original.context;c.validate()
        need(type(self.issued) is bool and type(self.sequence) is int and 0<=self.sequence<9007199254740991)
        base=16384+64*quoted_bytes(c.url)+128*max(quoted_bytes(getattr(c,k))
            for k in ('run','owner','instance','item','dom','response','entity','ticket'))
        if call['operation']=='commit-current-text':
            ime_command(call);need(call['control']=='text');text=call['text']
            escapes=sum(ch in '\\"' for ch in text)
            units=sum(2 if ord(ch)>65535 else 1 for ch in text)
            utf8=sum(1 if ord(ch)<128 else 2 if ord(ch)<2048 else 3 if ord(ch)<65536 else 4 for ch in text)
            # Product JSON has only these six fixed keys; 256 includes both
            # replacement integers, punctuation and the other scalar values.
            product16=256+units+escapes;product8=256+utf8+escapes
            frames=3*(4*product16+2*product8)+4*units+16*quoted_bytes(c.url)+8192
            # Four frame rows/builders and one packet use <=2048 fixed typed
            # node/encoder/descriptor entries (see closed table in review).
            need(frames<=base and len(self.frames)==0)
        else:
            trace_command(call);need(len(self.frames)<=4)
        need(self.stage.model_credit>=44*base+524288)
        return base
    def native(self):return self.original.snapshot()['native']
    def snapshot(self):return dict(native=self.native(),finish=dict(self.original.document_packet['source']['originalFinish']))
    def frame(self,kind,raw,event):
        literal=canonical(raw).decode('utf-8');need(len(literal.encode())<=8192 and len(self.frames)<16)
        self.frames.append(dict(sequence=len(self.frames)+1,eventId=event,kind=kind,origin='qt-ime',
            epochMs=self.stage.native_epoch_ms(),monotonicMs=self.stage.native_monotonic_ms(),raw=literal))
    def send(self,call):
        self.stage.event_before_produce(self,call)
        self.preflight(call)  # BEFORE snapshots, event, UTF encodings or file write.
        model=self.original;c=model.context;focus=self.stage.focus.last
        need(focus is not None and model.document_packet is not None)
        epoch=self.stage.native_epoch_ms();mono=self.stage.native_monotonic_ms();self.sequence+=1
        before=self.snapshot();operation=call['operation']
        if operation=='commit-current-text':
            ime_command(call)
            need(not self.issued and self.arm_call is not None
                and call['focusNonce']==self.stage.focus.last_request['commandId']
                and call['documentNonce']==model.document_packet['commandId'])
            editor=focus['source']['nativeEditor'];old=editor['text']
            units=sum(2 if ord(ch)>65535 else 1 for ch in old)
            self.event=HostImeEvent1(call['text'],-min(editor['cursor'],editor['anchor']),
                units-abs(editor['cursor']-editor['anchor']),uuid.uuid4().hex)
            self.issued=True  # Once BEFORE the declared normal event consumer.
            event=self.event;product=dict(action='ime',commit=event.commit,preedit='',replaceStart=event.replacement_start,
                replaceLength=event.replacement_length,cursor=0)
            if self.stage.node is not None:
                self.node_effect=self.stage.node.ime(call['commandId'],editor,product)
                need(self.node_effect['issued'] is True and self.node_effect['attemptNonce']==call['commandId'])
            literal=json.dumps(product,ensure_ascii=False,sort_keys=True,separators=(',',':'))
            native=self.native()
            native_raw=dict(authority=native,editor=deepcopy(editor),eventType='ime',key=None,modifiers=None,
                textUtf16Hex=None,commitUtf16Hex=event.commit.encode('utf-16-be').hex(),preeditUtf16Hex='',
                replacementStart=event.replacement_start,replacementLength=event.replacement_length,attributes=[],accepted=True)
            jni={**{k:native[k] for k in ('handle','creation','grant','page','url','sourceIdentity')},
                'commandUtf16Hex':literal.encode('utf-16-be').hex(),'commandUtf8Hex':literal.encode('utf-8').hex()}
            self.frame('jni-command',jni,event.event_id)
            self.frame('native-input',native_raw,event.event_id)
            java={k:jni[k] for k in ('handle','grant','page','url','commandUtf16Hex','commandUtf8Hex')}
            a=model.snapshot()['java']
            self.frame('java-entry',dict(java,isMainThread=True,capturedEpochMs=a['capturedEpochMs'],capturedElapsedMs=a['capturedElapsedMs']),event.event_id)
            self.frame('java-consume',dict(java,before=a,after=model.snapshot()['java']),event.event_id)
            source=dict(reason='',dispatch=dict(issued=True,acceptedQt=True,issuedEpochMs=epoch,issuedMonotonicMs=mono),
                nativeBefore=before,nativeAfter=self.snapshot(),focusReference={k:focus[k] for k in ('commandId','instance','sequence')},
                documentReference={k:model.document_packet[k] for k in ('commandId','instance','sequence')},
                originalFinish=dict(model.document_packet['source']['originalFinish']))
            packet=dict(picoWorldCurrentImeVersion=1,documentNonce=call['documentNonce'],focusNonce=call['focusNonce'])
        else:
            trace_command(call)
            if operation=='arm-current-consumption':
                need(self.arm_call is None and not self.issued);self.arm_call=deepcopy(call)
            else:need(self.arm_call is not None and call['attemptNonce']==self.arm_call['commandId'])
            frame=None
            if operation=='observe-current-consumption' and call['afterSequence']<len(self.frames):frame=deepcopy(self.frames[call['afterSequence']])
            source=dict(attemptReference=dict(nonce=self.arm_call['commandId'],itemInstance=c.item,sourceInstance=focus['instance']),
                focusReference={k:focus[k] for k in ('commandId','instance','sequence')},nativeBefore=before,nativeAfter=self.snapshot(),
                lifetime=dict(itemAlive=True,contextAlive=True,windowAlive=True,receiverAlive=True,activeAttempt=not self.issued),
                frame=frame,availableFrames=len(self.frames),terminal=self.issued)
            packet=dict(picoWorldCurrentConsumptionVersion=1)
        packet.update(commandId=call['commandId'],runId=c.run,ownerToken=c.owner,instance=self.instance,sequence=self.sequence,
            processId=model.pid,requestedEpochMs=epoch,requestedMonotonicMs=mono,capturedEpochMs=self.stage.native_epoch_ms(),
            capturedMonotonicMs=self.stage.native_monotonic_ms(),status='ready',source=source)
        raw=canonical(packet)+b'\n';need(len(raw)<=65536)
        if self.stage.host_selection.controller_focus:need(len(raw)<=self.wire_bound())
        model.file.write(packet,model.packet);model.packet=packet;model.request=dict(call)
        self.stage.event_published(self);return None

    def wire_bound(self):
        # Existing frame() constructs canonical ensure_ascii JSON and limits
        # each raw scalar to8192. Outer quoting costs at most2*8192+2. All
        # remaining closed header/refs/lifetime/native+finish fields are below
        #24576+8*quoted(url)+16*maxQuotedId, independently of the actual reply.
        from adapters.native_feature_observation import exact
        c=self.original.context;c.validate();need(type(self.frames) is list and len(self.frames)<=4)
        need(type(self.instance) is str and len(self.instance)==32
            and all(ch in '0123456789abcdef' for ch in self.instance))
        focus=self.stage.focus.last;doc=self.original.document_packet
        need(type(focus) is dict and type(doc) is dict and focus['instance']==c.item and doc['instance']==c.instance)
        for value in (focus,doc):
            for key in ('commandId','instance'):
                item=value[key];need(type(item) is str and len(item)==32 and all(ch in '0123456789abcdef' for ch in item))
            need(type(value['sequence']) is int and 0<value['sequence']<(1<<64))

        for frame in self.frames:
            exact(frame,{'sequence','eventId','kind','origin','epochMs','monotonicMs','raw'})
            need(type(frame['raw']) is str and frame['raw'].isascii() and len(frame['raw'])<=8192
                and all(32<=ord(ch)<=126 for ch in frame['raw'])
                and type(frame['eventId']) is str and len(frame['eventId'])==32
                and all(ch in '0123456789abcdef' for ch in frame['eventId'])
                and type(frame['kind']) is str and type(frame['origin']) is str
                and frame['kind'] in ('jni-command','native-input','java-entry','java-consume')
                and frame['origin']=='qt-ime')
            for key in ('sequence','epochMs','monotonicMs'):
                need(type(frame[key]) is int and 0<frame[key]<(1<<64))
        q=max(quoted_bytes(getattr(c,k)) for k in ('run','owner','instance','item','dom','response','entity','ticket'))
        return min(65536,24576+8*quoted_bytes(c.url)+16*q)
