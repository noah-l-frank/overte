"""Closed positive HOST component on actual cold Parent and existing archive.

No preparing owner,Native/Android/Qt fact,input,public capability or new pool.
The first stage accepts only its explicit bounded source-model adapter.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0

VERSION=1  # Internal HOST contract; no public/native capability.
from dataclasses import dataclass,field
import hashlib,os,stat,time
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.native_fd_owner import require_directory
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.pico4.world_root_resource import WorldRootParticipant1,WorldRootSelection1,PRECOUNT,WINDOW,LIMIT,PART,ENTRIES
from adapters.pico4.world_document_model import WorldDocumentModelContext1,WorldDocumentFileModel1
from adapters.pico4.world_json_work import project,LEXICAL_SLOT
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import canonical
from adapters.pico4.assets_raw_archive import quoted_bytes

RAW_WORK=80*PART
COMMAND_WORK=8*4096
MODEL_STORED=3*PART
COMPOUND_START=24*PART+52*PART+2*COMMAND_WORK


@dataclass(frozen=True,eq=False)
class WorldCurrentHostSelection1:
    context:WorldDocumentModelContext1
    base:WorldRootSelection1=field(default_factory=WorldRootSelection1)
    operation:str='document'
    focus_get_delay:float=0.0
    event_return_handback:bool=False
    live_string_aliases:bool=False
    product_dom:bool=False
    cancel_dom_beforeinput:bool=False


class WorldDocumentModelAdapter1:
    """Declared HOST-only factory,not the real PicoBound/Native factory."""
    def __init__(self,path,context):
        need(type(context) is WorldDocumentModelContext1);context.validate()
        self.context=context;self.pico_configuration=('world-current-host-model',path)
        self.source_lock=ScriptSourceLock(path/'script-sources.lock')
        self.resources=None;self.factory_calls=0;self.sdk_calls=0;self.inputs=0
    def _script_journey(self):return self
    def _lock(self,target,source_lock=None):
        if source_lock is not None:need(source_lock is self.source_lock)
        return self.source_lock
    def _world_current_input_originals(self,target,*,source_lock,root_resources=None):
        need(type(root_resources) is WorldRootCurrentParticipant2 and self.resources is root_resources)
        root_resources.admit_current_factory(self,target,source_lock)
        self.factory_calls+=1
        return root_resources.create_current_readers()


class WorldRootCurrentParticipant2(WorldRootParticipant1):
    def __init__(self,selection):
        need(type(selection) is WorldCurrentHostSelection1 and type(selection.context) is WorldDocumentModelContext1)
        need(type(selection.operation) is str and selection.operation in ('document','focus','ime')
            and type(selection.focus_get_delay) is float and 0.0<=selection.focus_get_delay<=2.0
            and (selection.operation in ('focus','ime') or selection.focus_get_delay==0.0)
            and type(selection.event_return_handback) is bool
            and (not selection.event_return_handback or selection.operation=='ime')
            and type(selection.live_string_aliases) is bool
            and (not selection.live_string_aliases or selection.operation=='ime')
            and type(selection.product_dom) is bool
            and (not selection.product_dom or (selection.operation=='ime' and selection.event_return_handback and selection.live_string_aliases))
            and type(selection.cancel_dom_beforeinput) is bool and (not selection.cancel_dom_beforeinput or selection.product_dom))
        selection.context.validate()
        super().__init__(selection.base)
        self.host_selection=self._host_selection=selection;self._operation=selection.operation;self._focus_get_delay=selection.focus_get_delay;self._event_return_handback=selection.event_return_handback;self._live_string_aliases=selection.live_string_aliases;self._product_dom=selection.product_dom;self._cancel_dom_beforeinput=selection.cancel_dom_beforeinput
        self.original=None;self.raw=self.model=self.reader=self.focus=None
        self.ready=False;self.closed=False;self.constructing=True
        self.model_credit=selection.context.model_work();self._model_credit=self.model_credit
        self.inventory_credit=4112;self.current=None;self.completed=[]
        self.birth=None;self.compound=None;self.focus_call=None;self.warm_work=0;self.warm_originals=[];self.event_credit=0;self.event_owner=None;self.trace_reader=None;self.event_model=None;self.event_rows=[];self.event_active=None;self.event_parse=False;self.intent=None;self.closed_event_calls=0;self.node=self._node=None;self.node_credit=2*PART if selection.product_dom else 0;self.post_work=0;self.post_documents=[]
        # Fund ALL constructors/startup before directory/archive/model work.
        need(PRECOUNT+WINDOW+4096+self.inventory_credit+self.model_credit+self.node_credit+RAW_WORK+max(LEXICAL_SLOT+COMMAND_WORK,COMPOUND_START if selection.operation in ('focus','ime') else 0)+MODEL_STORED<=LIMIT)

    def check_data(self):
        super().check_data()
        need(self.host_selection is self._host_selection and self.host_selection.base is self.config
            and type(self.host_selection) is WorldCurrentHostSelection1 and not self.closed
            and type(self.host_selection.operation) is str and self.host_selection.operation is self._operation
            and type(self.host_selection.focus_get_delay) is float and self.host_selection.focus_get_delay is self._focus_get_delay
            and type(self.host_selection.event_return_handback) is bool
            and self.host_selection.event_return_handback is self._event_return_handback
            and type(self.host_selection.live_string_aliases) is bool
            and self.host_selection.live_string_aliases is self._live_string_aliases
            and type(self.host_selection.product_dom) is bool
            and self.host_selection.product_dom is self._product_dom
            and type(self.host_selection.cancel_dom_beforeinput) is bool
            and self.host_selection.cancel_dom_beforeinput is self._cancel_dom_beforeinput)
        need(type(self.closed_event_calls) is int and 0<=self.closed_event_calls<=4096)
        need(type(self.model_credit) is int and self.model_credit is self._model_credit
            and type(self.node_credit) is int and self.node_credit==(2*PART if self._product_dom else 0))
        if self.node is not None:
            from adapters.pico4.world_product_dom import WorldProductDom1
            need(self.node is self._node and type(self.node) is WorldProductDom1)
            for name in ('guard','query','snapshot','ime','capture','prepare_literal','close_host'):
                callback=getattr(self.node,name)
                need(callback.__self__ is self.node and callback.__func__ is getattr(WorldProductDom1,name))
        c=self.host_selection.context;c.validate()
        need(c.run==self.parent.run and c.fixture_url==self.parent.url and self.parent.role=='primary'
            and self.parent.source.monotonic is time.monotonic)
        if self.original is not None:
            need(type(self.original) is WorldDocumentModelAdapter1 and self.original is self.parent.adapter.original
                and self.original.context is c and self.original.resources is self)

    def bind(self,parent,parent_type):
        super().bind(parent,parent_type)
        try:
            self.original=parent.adapter.original
            need(type(self.original) is WorldDocumentModelAdapter1 and self.original.resources is None
                and self.original.context is self.host_selection.context)
            self.original.resources=self
            self.directory_guard();need(self.names()==[])
            self._bill(0,self.live_size(),0,0)
            # The superclass bind has already installed the actual Root pair.
            self.birth=time.monotonic()
            self.raw=object.__new__(AudioRawArchive)
            scope=dict(worldCurrentHostRawVersion=1,parentScope=parent.scope,kind='HOST_SOURCE_COMPONENT_ONLY',
                processId=os.getpid(),runId=parent.run,ownerToken=self.host_selection.context.owner)
            AudioRawArchive.__init__(self.raw,parent.root/'pico-world-current-host-raw.json',scope,parent.lock,
                self.identity,self.other_bill,parent.source.monotonic)
            self.model=object.__new__(WorldDocumentFileModel1)
            WorldDocumentFileModel1.__init__(self.model,self,self.host_selection.context)
            self.constructing=False;self.ready=True
            self.census()
        except BaseException as error:self.fail(error);raise

    def identity(self):
        self.directory_guard()
        need(self.original is self.parent.adapter.original and self.original.resources is self)

    def model_identity(self,model):
        self.identity();need(model is self.model and type(model) is WorldDocumentFileModel1
            and model.context is self.host_selection.context and model.file.store is model.store
            and model.store.path==self.root/'pico-world-current-host-model-source.json')

    def native_epoch_ms(self):return time.time_ns()//1000000
    def native_monotonic_ms(self):return time.monotonic_ns()//1000000

    def work(self):
        # Full startup/read allocation remains funded even before first call.
        calls=[*self.completed,*([self.current] if self.current is not None else [])]
        need(all(type(call['work']) is int and type(call['entry']) is int
            and call['work']>=0 and call['entry']>=0 for call in calls))
        if self._operation in ('focus','ime'):
            group=self.compound
            entry=(group['entry'] if group is not None else 0)+sum(call['entry'] for call in calls)
            if self.focus_call is not None:entry+=self.focus_call['entry']
            if self._operation=='ime' and group is not None and group['done']:
                # Only original focus's TRUE successful return closes ALL
                # nested reader/Raw/census frames. Keep every actual escaped
                # object and historical integer; retire their extra COPY-work
                # reservation, not any S/A/P/model/Raw/result ownership.
                need(group.get('entries_closed') is True and (self.current is None or
                        (self._product_dom and self.current.get('post_current_document') is True
                            and type(self.post_work) is int and self.post_work>0 and self.current['entry']==0))
                    and len(self.completed)==1 and self.focus_call is not None
                    and not self.records and not self.entry_claims and not self.metadata_claims
                    and not self.snapshots and self.counter_candidate is None)
                entry=0
            return self.model_credit+self.node_credit+RAW_WORK+(group['work'] if group is not None else COMPOUND_START)+entry+max(self.warm_work,self.event_credit,self.post_work)
        return self.model_credit+RAW_WORK+max(LEXICAL_SLOT+COMMAND_WORK,
            sum(call['work']+call['entry'] for call in calls))

    def live_size(self):
        value=4*super().held_size()+32768  # closed Parent key/object/control metadata
        def nodes(item):
            kind=type(item)
            if kind is dict:return 1+sum(1+nodes(v) for v in item.values())
            if kind is list:return 1+sum(nodes(v) for v in item)
            return 1
        from adapters.pico4.world_live_strings import WorldLiveStrings1
        string_extents=WorldLiveStrings1() if self._live_string_aliases else None
        def dto(item):
            if string_extents is not None:return string_extents.size(item)
            if type(item) is bytes:return len(item)+256
            if type(item) is tuple:return sum(dto(v) for v in item)+64+8*len(item)
            # Canonical keys AND values plus their exact typed live-node meta.
            return 4*canonical_size(item,LIMIT)+256*nodes(item)
        value+=dto(self.host_selection.operation)+dto(self.host_selection.focus_get_delay)+dto(self.host_selection.event_return_handback)+dto(self.host_selection.live_string_aliases)+dto(self.host_selection.product_dom)+dto(self.host_selection.cancel_dom_beforeinput)
        for name in ('run','fixture_url','owner','instance','item','dom','response','entity','ticket'):
            value+=dto(getattr(self.host_selection.context,name))
        if self.raw is not None and hasattr(self.raw,'state'):
            for name in ('scope','disk','state'):value+=dto(getattr(self.raw,name))
            for name in ('pages','issued_reservations','unconfirmed_returns'):
                item=getattr(self.raw,name);need(type(item) is dict and all(type(k) is int for k in item))
                value+=256+sum(dto(k)+dto(v)+256 for k,v in item.items())
            value+=dto(self.raw.open_data)+dto(self.raw.pin)+dto(self.raw.host)
            value+=256+sum(dto(k)+dto(v) for k,v in self.raw.page_bodies.items())
            value+=256+sum(dto(k)+dto(owner.raw or b'')+1024 for k,owner in self.raw.closed.items())
            need(not self.raw.uncertain)
            # page_pins aliases pages by exact identity; physical stamps extra.
            for index,(page,pin) in self.raw.page_pins.items():
                need(page is self.raw.pages[index]);value+=dto(pin)+256
        if self.model is not None and hasattr(self.model,'packet'):
            value+=dto(self.model.packet)+dto(self.model.request)+len(self.model.file.raw or b'')
            value+=dto(self.model.process)+dto(self.model.sequence)+dto(self.model.finished_epoch)
            value+=dto(self.model.dom_sequence)+dto(self.model.focused)+dto(self.model.focus_delay_done)
            if self.model.document_packet is not self.model.packet:value+=dto(self.model.document_packet)
        if self.reader is not None:
            for name in ('last','raw','last_request'):value+=dto(getattr(self.reader,name))
        if self.focus is not None:
            for name in ('last','raw','last_request','document_original','_warm_anchor'):
                value+=dto(getattr(self.focus,name))
        if self.compound is not None:
            value+=4096+dto(self.compound['result'])
        calls=[*self.completed,*([self.current] if self.current is not None else [])]
        if self.focus_call is not None:calls.append(self.focus_call)
        for call in calls:
            value+=1024  # call dict keys/control/container/reader references
            for name in ('request','raw','raw_ref','retainer','result','tokens'):value+=dto(call[name])
            value+=dto(call.get('controlReturn'))+dto(call.get('documentOriginal'))
            if 'plan' in call:
                plan=call['plan']
                from adapters.pico4.world_json_work import WorldJsonWork1
                need(type(plan) is WorldJsonWork1)
                value+=dto(dict(utf8=plan.utf8_bytes,canonical=plan.max_canonical,nodes=plan.total_nodes,
                    depth=plan.combined_depth,data=plan.decoded_data,metadata=plan.decoded_metadata,
                    lexical=plan.lexical_slot,streams=dict(plan.streams)))+256
        value+=dto(self.warm_originals)+dto(self.event_rows)
        for row in self.post_documents:
            value+=1024
            for name in ('request','raw','raw_ref','retainer','result','tokens','controlReturn'):value+=dto(row.get(name))
            if 'plan' in row:
                plan=row['plan']
                value+=dto(dict(utf8=plan.utf8_bytes,canonical=plan.max_canonical,nodes=plan.total_nodes,depth=plan.combined_depth,
                    data=plan.decoded_data,metadata=plan.decoded_metadata,lexical=plan.lexical_slot,streams=dict(plan.streams)))+256
        if self.node is not None:
            node=self.node
            for name in ('ready','last','pending','buffer','stderr','start'):
                if hasattr(node,name):value+=dto(getattr(node,name))
            for row in getattr(node,'rows',[]):
                value+=4096
                for name in ('call','raw','stderr','payload'):value+=dto(row.get(name))
                owner=row.get('owner')
                if owner is not None:
                    value+=len(getattr(owner,'raw',None) or b'')
                    if hasattr(owner,'path'):value+=dto(str(owner.path))+512
            for name in ('script','editor','executable'):
                if hasattr(node,name):value+=dto(str(getattr(node,name)))
            value+=16384  # Popen/three paired pipe owners/current controls

        if self.intent is not None:value+=len(getattr(self.intent,'raw',None) or b'')+4096
        if self.event_owner is not None:
            for name in ('original_focus','call','raw','last','entry_text'):value+=dto(getattr(self.event_owner,name))
        if self.trace_reader is not None:
            for name in ('arm_packet','focus_original','last','_query_anchor'):value+=dto(getattr(self.trace_reader,name))
            # Original correlate stores tuple(origin, decoded-frame). Count
            # that actual typed container rather than pretending it is JSON.
            value+=256
            for event,kinds in self.trace_reader.events.items():
                value+=dto(event)+256
                for kind,pair in kinds.items():value+=dto(kind)+dto(pair)+256
        if self.event_model is not None:
            value+=dto(self.event_model.frames)+dto(self.event_model.arm_call)+dto(self.event_model.node_effect)
            if self.event_model.event is not None:value+=dto(vars(self.event_model.event))
            for name in ('instance','sequence','issued'):value+=dto(getattr(self.event_model,name))
        value+=4096  # closed warm/event-owner control; payload credit is separate
        # Known stage/model/archive/reader/focus/context objects and exact
        # bound callback references. No payload or arbitrary closure is hidden.
        value+=6*256+4096
        return value

    def known_files(self):
        need(self.ready and not self.constructing)
        rows={}
        if self.model.file.file is not None:
            self.model.file.guard();rows[str(self.model.store.path)]=(0o600,list(self.model.file.stamp),hashlib.sha256(self.model.file.raw).hexdigest())
        if self.intent is not None and self.intent.file is not None:
            self.intent.guard();rows[str(self.intent.path)]=(0o600,list(self.intent.stamp),hashlib.sha256(self.intent.raw).hexdigest())
        if self.node is not None:
            if getattr(self.node,'start',None) is not None:self.node.guard()
            for row in getattr(self.node,'rows',[]):
                owner=row.get('owner')
                if owner is not None and getattr(owner,'file',None) is not None:
                    owner.guard();rows[str(owner.path)]=(0o600,list(owner.stamp),hashlib.sha256(owner.raw).hexdigest())
        archive=self.raw;archive.verify()
        rows[str(archive.path)]=(0o600,list(archive.pin),hashlib.sha256(canonical(archive.disk)+b'\n').hexdigest())
        for index,row in enumerate(archive.state['parts']):
            if row['closed']:
                owner=archive.closed[index];need(owner.stamp==row['physical'])
            rows[str(archive.part_path(index))]=(0o400 if row['closed'] else 0o600,row['physical'],row['sha256'])
        for index,(value,pin) in archive.page_pins.items():
            need(value is archive.pages[index])
            rows[str(archive.page_store(index).path)]=(0o600,pin,hashlib.sha256(archive.page_bodies[index]+b'\n').hexdigest())
        return rows

    def callback_identity(self):
        need(type(self.raw) is AudioRawArchive and self.raw.other_bill is self.raw._other_bill
            and self.raw.identity is self.raw._identity and self.raw.clock is self.raw._clock
            and self.raw.clock is self.parent.source.monotonic
            and self.raw.other_bill.__self__ is self and self.raw.other_bill.__func__ is type(self).other_bill
            and self.raw.identity.__self__ is self and self.raw.identity.__func__ is type(self).identity)
        if self.reader is not None:
            for name,method in (('send',type(self).send),('read_raw',type(self).get),('guard',type(self).guard_current),
                    ('clock_ms',type(self).native_epoch_ms),('retain',type(self).retain),('capacity',type(self).capacity)):
                callback=getattr(self.reader,name)
                need(callback.__self__ is self and callback.__func__ is method)
            need(self.reader.resource_provider is self and self.reader.monotonic is self.parent.source.monotonic
                and self.reader.sleep is time.sleep)
        if self.focus is not None and self._operation in ('focus','ime'):
            for name,method in (('send',type(self).send_focus),('read_raw',type(self).get_focus),
                    ('retain',type(self).retain_focus),('capacity',type(self).capacity)):
                callback=getattr(self.focus,name)
                need(callback.__self__ is self and callback.__func__ is method)
            need(self.focus.resource_provider is self and self.focus.documents is self.reader
                and self.focus.guard is self.reader.guard and self.focus.clock_ms is self.reader.clock_ms
                and self.focus.monotonic is self.reader.monotonic and self.focus.sleep is self.reader.sleep)

    def event_callbacks(self):
        if self.event_owner is None or self.trace_reader is None:return
        from adapters.pico4.world_current_ime import PicoWorldCurrentIme
        from adapters.pico4.world_current_consumption import PicoWorldCurrentConsumption
        from adapters.pico4.world_host_ime_model import WorldHostImeModel1
        need(type(self.event_owner) is PicoWorldCurrentIme and self.event_owner.resources is self
            and self.event_owner.focus is self.focus and type(self.trace_reader) is PicoWorldCurrentConsumption
            and self.trace_reader.resource_provider is self and self.trace_reader.focus is self.focus
            and type(self.event_model) is WorldHostImeModel1 and self.event_model.stage is self
            and self.event_model.original is self.model)
        for reader in (self.event_owner,self.trace_reader):
            for name,method in (('send',type(self).event_send),('read_raw',type(self).event_get),
                    ('retain',type(self).event_retain),('capacity',type(self).capacity)):
                callback=getattr(reader,name);need(callback.__self__ is self and callback.__func__ is method)
            need(reader.guard is self.focus.guard and reader.clock_ms is self.focus.clock_ms
                and reader.monotonic is self.focus.monotonic and reader.sleep is self.focus.sleep)

    def file_mode(self,path):
        # No physical/source verdict cache. Exact registered archive family only.
        if self.intent is not None and path==self.intent.path:return 0o600
        if self.node is not None:
            for row in getattr(self.node,'rows',[]):
                owner=row.get('owner')
                if owner is not None and hasattr(owner,'path') and path==owner.path:return 0o600
        if self.model is not None and path==self.model.store.path:return 0o600
        if self.raw is not None:
            if path==self.raw.path:return 0o600
            for index,(value,pin) in self.raw.page_pins.items():
                if path==self.raw.page_store(index).path:return 0o600
            for index,row in enumerate(self.raw.state['parts']):
                if path==self.raw.part_path(index):
                    if row['closed']:need(index in self.raw.closed and self.raw.closed[index].stamp==row['physical']);return 0o400
                    return 0o600
        need(False)

    def census(self):
        self.check_data();need(self.ready and not self.constructing)
        with self.lock.held():
            self.identity();self.callback_identity();self.event_callbacks();known=self.known_files();names=self.names()
            need(names==sorted(Path(path).name for path in known))
            n=len(names);r=len(str(self.root).encode())
            future=n+7
            j=2+max(0,future-1)+future*(512+6*(r+1+255))
            self.inventory_credit=max(self.inventory_credit,8*j+768*n+4096)
            # Metadata and read windows are held BEFORE full pins allocations.
            self._bill(0,self.live_size(),0,n)
            pins=self.parent.pins();need(len(pins)==n)
            stored=0
            for row in pins:
                mode,stamp,sha=known[row['path']]
                need(row['signature']==list(stamp) and row['sha256']==sha
                    and stat.S_IMODE(row['signature'][2])==mode)
                stored+=row['signature'][5]
            need(names==self.names());self.identity()
            logical=self.raw.bill()['literalBytes']+self.raw.bill()['metadataBytes']
            return self._bill(stored,self.live_size(),logical,n)

    def _bill(self,stored,live,logical,n):
        pending=MODEL_STORED+3*PART+65536+(3*PART if self._operation=='ime' else 0)+(3*PART if self._product_dom else 0)
        fixed=PRECOUNT+WINDOW+4096+self.inventory_credit
        decoded=fixed+stored+logical+live+self.work()
        disk=fixed+stored+pending
        need(all(type(v) is int and v>=0 for v in (stored,live,logical,n,decoded,disk))
            and decoded<=LIMIT and disk<=LIMIT and n+7<=ENTRIES)
        return dict(decodedBytes=decoded,storedBytes=disk,parts=0,files=n,S=stored,A=logical,P=live,
            work=self.work(),inventory=self.inventory_credit,pendingStored=pending,limit=LIMIT)

    def other_bill(self):return self.census()

    def admit_current_factory(self,original,target,source_lock):
        try:
            self.check_data();need(self.ready and self.current is None and not self.completed
                and type(original) is WorldDocumentModelAdapter1 and original is self.original
                and type(target) is str and target==self.parent.target and source_lock is self.lock
                and self.lock._owner is None)
            self.census()
        except BaseException as error:self.fail(error);raise

    def create_current_readers(self):
        from adapters.pico4.world_current_document import PicoWorldCurrentDocument
        from adapters.pico4.world_current_input import PicoWorldCurrentInput
        need(self.reader is self.focus is None)
        if self._product_dom:
            from adapters.pico4.world_product_dom import WorldProductDom1,NODE_WORK
            need(self.node is None and self.model_credit>=NODE_WORK+65536)
            self.census()
            self.node=self._node=object.__new__(WorldProductDom1)
            with self.lock.held():
                WorldProductDom1.__init__(self.node,self,Path(__file__).with_name('world_product_dom_worker.js'),
                    Path(__file__).resolve().parents[4]/'android/common/web/resources/editor.js')
        self.reader=object.__new__(PicoWorldCurrentDocument)
        PicoWorldCurrentDocument.__init__(self.reader,self.send,self.get,self.native_epoch_ms,self.guard_current,
            self.model.pid,self.lock,monotonic=self.parent.source.monotonic,sleep=time.sleep,
            retain=self.retain,capacity=self.capacity,resource_provider=self)
        self.focus=object.__new__(PicoWorldCurrentInput)
        if self._operation in ('focus','ime'):
            PicoWorldCurrentInput.__init__(self.focus,self.reader,self.send_focus,self.get_focus,
                retain=self.retain_focus,capacity=self.capacity,resource_provider=self)
        else:PicoWorldCurrentInput.__init__(self.focus,self.reader,self.reject_input_source,self.reject_input_source)
        return self.focus

    def document_read(self,reader,run,url,owner):
        if self._product_dom and self.compound is not None and self.compound['done']:
            return self.post_document_read(reader,run,url,owner)
        # Pure ownership BEFORE any source/native clock/guard callback. A nested
        # refusal neither clears nor replaces the outer active call.
        need(self.current is None and not self.completed and reader is self.reader
            and type(run) is str and type(url) is str and type(owner) is str)
        self.current=dict(work=LEXICAL_SLOT+COMMAND_WORK,entry=0,request=None,raw=None,raw_ref=None,
            retainer=None,result=None,tokens=[])
        try:
            c=self.host_selection.context;need((run,url,owner)==(c.run,c.fixture_url,c.owner))
            before=self.census();self.current['entry']=before['P'];self.census()
            result=reader._read_original(run,url,owner)
        except BaseException as error:self.fail(error);raise
        # No callback/IO/clock/opaque release after original final checks. Full
        # work/entry and actual returned DTO stay retained; no early debit.
        self.current['result']=result;self.completed.append(self.current);self.current=None
        return result

    def guard_current(self):
        self.check_data();need((self.current is not None or self.compound is not None)
            and self.ready and time.monotonic()-self.birth<=120)
        self.identity();self.model.guard();self.census();return True
    def capacity(self):self.guard_current()
    def model_before_produce(self,model,request):
        record=self.current if self.current is not None else self.focus_call
        need(model is self.model and record is not None and record['request']==request)
        self.guard_current()
    def model_before_get(self,model):need(model is self.model);self.guard_current()
    def model_published(self,model):need(model is self.model);self.census()

    def prospective_metadata(self,role,command,limit):
        """Count actual old state + next closed token before Raw copies."""
        need(type(role) is str and type(command) is dict and type(limit) is int
            and 1<=limit<=65536 and not self.raw.state['pending'])
        command_size=canonical_size(command,4096);parts=(limit+PART-1)//PART+1
        def nodes(value):
            if type(value) is dict:return 1+sum(1+nodes(v) for v in value.values())
            if type(value) is list:return 1+sum(nodes(v) for v in value)
            return 1
        token=512+quoted_bytes(role)+command_size+quoted_bytes(str(self.raw.path))
        # Exact current families have already passed original full-file/OFD
        # guards. Allow the worst uint64 signature width for EVERY old page
        # in metadata_capacity, plus the possible new page/parts/token.
        header=canonical_size(self.raw.disk,PART)+token+parts*512+384+192*len(self.raw.pages)
        page=self.raw.state['reads']//32
        existing=canonical_size(self.raw.pages[page],PART) if page in self.raw.pages else 512
        receipt=1024+quoted_bytes(role)+command_size+parts*64
        page_nodes=max([48,*[nodes(v) for v in self.raw.pages.values()]])
        next_header_nodes=nodes(self.raw.disk)+nodes(command)+128
        next_page_nodes=page_nodes+nodes(command)+64
        # Pairs/memos/chunks/reference/header metadata is preheld separately
        # from4P byte +4*(5H+6I) decoded DATA +8P encoder overlap.
        required_meta=2*256*(5*next_header_nodes+6*next_page_nodes)+PART
        header_bound=header
        index_bound=max([existing+receipt+256,*[canonical_size(v,PART)+1 for v in self.raw.pages.values()]])
        # Same original80P, FULL simultaneous SUM. 4P raw append/readback and
        # 8P encoder windows stay unchanged. Five decoded header domains4H
        # each and six index domains4I each use their actual PROSPECTIVE
        # scalar bounds; remaining space funds the exact metadata formula.
        # Never discount an alias or raise the same-root/Raw quota.
        required_work=12*PART+20*header_bound+24*index_bound+required_meta
        need(header_bound<=PART and index_bound<=PART and required_work<=RAW_WORK)
        self.census()

    def send(self,request):
        self.guard_current();self.prospective_metadata('world-model-control',request,1)
        token=self.raw.reserve('world-model-control',request,1)
        self.current['tokens'].append(token)
        try:
            returned=self.model.send(request)
            self.current['controlReturn']=returned
            self.raw.retain(token,returned)
        except BaseException as error:self.fail(error);raise
    def get(self):
        self.guard_current();self.prospective_metadata('world-model-data',self.current['request'],65536)
        token=self.raw.reserve('world-model-data',self.current['request'],65536)
        self.current['tokens'].append(token)
        try:
            returned=self.model.original();self.current['raw']=returned
            reference=self.raw.retain(token,returned);self.current['raw_ref']=reference
            return returned
        except BaseException as error:self.fail(error);raise

    def retain(self,value):
        need(self.current is not None);self.current['retainer']=value
        try:
            kind=value['kind']
            if kind=='world-current-document-request':
                need(self.current['request'] is None);self.current['request']=value['request'];self.census();return
            need(kind=='world-current-document-raw' and value['request']==self.current['request']
                and value['raw'] is self.current['raw'] and self.current['raw_ref'] is not None)
            observed=self.raw.literal(self.current['raw_ref']);need(observed==value['raw'])
            plan=project(value['raw'])
            self.current['work']=max(self.current['work'],plan.call_work)
            self.current['plan']=plan
            if self._product_dom and self.compound is not None and self.compound['done']:
                self.post_work=max(self.post_work,plan.call_work)
            elif self._operation in ('focus','ime'):self.update_compound()
            self.census()  # Actual literal+all copy/meta admitted BEFORE decode.
        except BaseException as error:self.fail(error);raise

    def update_compound(self):
        need(self._operation in ('focus','ime') and self.compound is not None and not self.compound['done'])
        doc=self.current if self.current is not None else self.completed[0] if self.completed else None
        dp=doc.get('plan') if doc is not None else None
        doc_term=dp.decoded_data+dp.decoded_metadata if dp is not None else 0
        focus_term=0
        if self.focus_call is not None and 'plan' in self.focus_call:
            need(dp is not None);fp=self.focus_call['plan']
            focus_metadata=14*256*(fp.total_nodes+1)+dp.decoded_metadata+1024*(fp.combined_depth+1)+4096
            focus_term=52*fp.max_canonical+52*dp.max_canonical+focus_metadata
        self.compound['work']=24*PART+max(52*PART,doc_term,focus_term)+2*COMMAND_WORK

    def focus_read(self,focus,run,url,owner,operation,control):
        # ONE cold selected compound call; no warm Stage2 owner adoption.
        need(self._operation in ('focus','ime') and self.compound is None and self.current is None
            and not self.completed and self.focus_call is None and focus is self.focus
            and all(type(v) is str for v in (run,url,owner,operation,control))
            and operation=='observe-current-focus' and control=='text')
        self.compound=dict(work=COMPOUND_START,entry=0,result=None,done=False,entries_closed=False)
        try:
            before=self.census();self.compound['entry']=before['P'];self.census()
            result=focus._read_original(run,url,owner,operation,control)
            if self._operation=='ime':
                # This PURE data check follows the true original return; no
                # new callback/clock/IO/owner release can intervene.
                need(self.lock._owner is None and self.failure is None
                    and self.current is None and len(self.completed)==1 and self.focus_call is not None
                    and not self.raw.state['pending'] and not self.raw.issued_reservations
                    and not self.raw.unconfirmed_returns and not self.raw.uncertain
                    and not self.records and not self.entry_claims and not self.metadata_claims
                    and not self.snapshots and self.counter_candidate is None)
        except BaseException as error:self.fail(error);raise
        # Original final focus freshness finished. Builtin transfer only.
        self.compound['result']=result;self.compound['done']=True
        if self._operation=='ime':
            self.compound['work']=2*COMMAND_WORK
            self.compound['entries_closed']=True
        return result

    def warm_bound(self):
        dp=self.completed[0]['plan'];fp=self.focus_call['plan']
        metadata=11*256*(fp.total_nodes+1)+dp.decoded_metadata+1024*(fp.combined_depth+1)+4096
        return 40*fp.max_canonical+52*dp.max_canonical+metadata

    def warm_original(self,focus,original):
        # Re-admit THIS exact original pure parser before any of its decoding,
        # hashing,callbacks or clocks. Never spend a later input's credit.
        need(self._operation=='ime' and self.compound is not None and self.compound['done']
            and self.warm_work==0 and not self.event_parse and focus is self.focus and self.failure is None)
        need(type(original) is dict)
        self.warm_originals.append(original)  # Exact caller graph stays held/accounted.
        self.warm_work=self.warm_bound()
        try:
            self.census()
            result=focus._require_warm_original(original)
        except BaseException as error:self.fail(error);raise
        # Original method has actually returned only None. Saved DTOs and all
        # caller/entry/raw/model/file roots remain in P/S/A,not released here.
        self.warm_work=0
        return result

    def send_focus(self,request):
        need(self.focus_call is not None and self.current is None and self.compound is not None
            and not self.compound['done'])
        self.guard_current();self.prospective_metadata('world-model-focus-control',request,1)
        token=self.raw.reserve('world-model-focus-control',request,1)
        self.focus_call['tokens'].append(token)
        try:
            returned=self.model.send_focus(request);self.focus_call['controlReturn']=returned
            self.raw.retain(token,returned)
        except BaseException as error:self.fail(error);raise

    def get_focus(self):
        need(self.focus_call is not None and self.current is None and self.compound is not None
            and not self.compound['done'])
        self.guard_current();self.prospective_metadata('world-model-focus-data',self.focus_call['request'],65536)
        token=self.raw.reserve('world-model-focus-data',self.focus_call['request'],65536)
        self.focus_call['tokens'].append(token)
        try:
            returned=self.model.original();self.focus_call['raw']=returned
            reference=self.raw.retain(token,returned);self.focus_call['raw_ref']=reference
            return returned
        except BaseException as error:self.fail(error);raise

    def retain_focus(self,value):
        need(self.compound is not None and not self.compound['done'] and self.current is None
            and len(self.completed)==1)
        try:
            kind=value['kind']
            if kind=='world-current-input-request':
                need(self.focus_call is None)
                self.focus_call=dict(work=0,entry=0,request=value['request'],raw=None,raw_ref=None,
                    retainer=value,result=None,tokens=[],documentOriginal=value['documentOriginal'])
                before=self.census();self.focus_call['entry']=before['P'];self.census();return
            need(kind=='world-current-input-raw' and self.focus_call is not None
                and value['request']==self.focus_call['request'] and value['raw'] is self.focus_call['raw']
                and self.focus_call['raw_ref'] is not None)
            self.focus_call['retainer']=value
            observed=self.raw.literal(self.focus_call['raw_ref']);need(observed==value['raw'])
            self.focus_call['plan']=project(value['raw']);self.update_compound();self.census()
        except BaseException as error:self.fail(error);raise

    def create_ime_sources(self):
        from adapters.pico4.world_current_ime import PicoWorldCurrentIme
        from adapters.pico4.world_current_consumption import PicoWorldCurrentConsumption
        from adapters.pico4.world_host_ime_model import WorldHostImeModel1
        need(self._operation=='ime' and self.compound is not None and self.compound['done']
            and self.event_owner is self.event_model is self.trace_reader is None)
        # Control-only constructors; no event/writer/query/parse occurs here.
        self.event_credit=max(LEXICAL_SLOT+COMMAND_WORK,self.warm_bound())
        self.census()
        self.event_model=object.__new__(WorldHostImeModel1)
        WorldHostImeModel1.__init__(self.event_model,self)
        self.event_owner=object.__new__(PicoWorldCurrentIme)
        PicoWorldCurrentIme.__init__(self.event_owner,self.focus,self.event_send,self.event_get,
            self.event_retain,self.capacity,self)
        from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
        self.intent=object.__new__(LifecycleProcessFile)
        LifecycleProcessFile.__init__(self.intent,PrivateFeatureState(self.root/'pico-world-current-ime-intent.json'))
        self.trace_reader=object.__new__(PicoWorldCurrentConsumption)
        PicoWorldCurrentConsumption.__init__(self.trace_reader,self.focus,self.event_send,self.event_get,
            self.event_retain,capacity=self.capacity,resource_provider=self)
        self.census();return self.event_owner,self.trace_reader

    def ime_entry(self,owner,text):
        need(owner is self.event_owner and self._operation=='ime' and type(text) is str
            and self.compound is not None and self.compound['done']
            and sum(2 if ord(c)>65535 else 1 for c in text)<=512
            and not any(ord(c)<32 or ord(c)==127 or 0xE000<=ord(c)<=0xE05E or 0xD800<=ord(c)<=0xDFFF for c in text))
        owner.entry_text=text  # Actual caller scalar, before callback/first copy.
        # Same controlled response/Raw/decoder work as Doc/Focus. All model,
        # actual saved originals/entries/Root/80P remain separately charged.
        self.event_credit=max(self.event_credit,LEXICAL_SLOT+COMMAND_WORK)
        self.census()

    def event_before_produce(self,model,request):
        need(model is self.event_model and self.event_active is not None
            and self.event_active['request']==request)
        self.guard_current()
    def event_published(self,model):need(model is self.event_model);self.census()

    def event_send(self,request):
        need(self._operation=='ime' and self.event_active is not None and not self.event_parse)
        self.guard_current();self.prospective_metadata('world-ime-model-control',request,1)
        token=self.raw.reserve('world-ime-model-control',request,1)
        self.event_active['tokens'].append(token)
        try:
            returned=self.event_model.send(request);self.event_active['controlReturn']=returned
            self.raw.retain(token,returned)
        except BaseException as error:self.fail(error);raise

    def event_get(self):
        need(self.event_active is not None and not self.event_parse)
        self.guard_current();request=self.event_active['request']
        self.prospective_metadata('world-ime-model-data',request,65536)
        token=self.raw.reserve('world-ime-model-data',request,65536)
        self.event_active['tokens'].append(token)
        try:
            returned=self.model.original();self.event_active['raw']=returned
            ref=self.raw.retain(token,returned);self.event_active['raw_ref']=ref
            return returned
        except BaseException as error:self.fail(error);raise

    def event_retain(self,value):
        try:
            kind=value['kind']
            if kind in ('request','ime-request'):
                need(self.event_active is None and not self.event_parse)
                # A genuine next query starts after the preceding original
                # call exit; the enclosing controlled vertical owns release.
                self.event_credit=max(self.event_credit,LEXICAL_SLOT+COMMAND_WORK)
                row=dict(request=value['request'],raw=None,raw_ref=None,retainer=value,tokens=[],controlReturn=None)
                self.event_rows.append(row);self.event_active=row;self.census()
                if kind=='ime-request':
                    need(self.intent is not None and self.intent.file is None)
                    payload=dict(worldCurrentImeIntentVersion=1,scope=self.raw.scope,original=value)
                    need(canonical_size(payload,PART)+1<=PART)
                    self.intent.write(payload,None);self.census()
                return
            need(kind in ('raw','ime-raw') and self.event_active is not None
                and value['raw'] is self.event_active['raw'])
            self.event_active['retainer']=value
            actual=self.raw.literal(self.event_active['raw_ref']);need(actual==value['raw'])
            plan=project(value['raw']);dp=self.completed[0]['plan'];fp=self.focus_call['plan']
            warm_meta=11*256*(fp.total_nodes+1)+dp.decoded_metadata+1024*(fp.combined_depth+1)+4096
            demand=12*PART+max(52*PART,80*plan.max_canonical+40*fp.max_canonical+52*dp.max_canonical
                +16*256*(plan.total_nodes+1)+warm_meta+1024*(plan.combined_depth+1)+4096)+COMMAND_WORK
            self.event_credit=max(self.event_credit,demand);self.census();self.event_parse=True
        except BaseException as error:self.fail(error);raise

    def trace_arm(self,reader):
        need(reader is self.trace_reader and self.event_active is None and not self.event_parse)
        try:
            self.event_credit=max(self.event_credit,LEXICAL_SLOT+COMMAND_WORK,self.warm_bound())
            self.census()  # BEFORE the original arm's focus deepcopy/parser.
            result=reader._arm_original()
            self.event_owner_returned(reader)
            return result
        except BaseException as error:self.fail(error);raise

    def trace_observe(self,reader,sequence):
        need(reader is self.trace_reader and type(sequence) is int)
        try:
            self.event_credit=max(self.event_credit,LEXICAL_SLOT+COMMAND_WORK,self.warm_bound())
            self.census()  # BEFORE outer command/copy/query/correlate/finish.
            result=reader._observe_original(sequence)
            self.event_owner_returned(reader)
            return result
        except BaseException as error:self.fail(error);raise

    def ime_commit(self,reader,text):
        need(reader is self.event_owner)
        try:
            result=reader._commit_original(text)
            self.event_owner_returned(reader)
            return result
        except BaseException as error:self.fail(error);raise

    def event_owner_returned(self,reader):
        # Called only after TRUE original outer arm/commit/observe returned,
        # including all original correlate/finish/lock/freshness statements.
        # All escaped DTOs/originals/events remain strong, counted in P/S/A.
        if not self._event_return_handback:return
        need((reader is self.event_owner or reader is self.trace_reader)
            and self.failure is None and self.lock._owner is None
            and self.event_active is None and not self.event_parse
            and not self.raw.state['pending'] and not self.raw.issued_reservations
            and not self.raw.unconfirmed_returns and not self.raw.uncertain)
        self.closed_event_calls+=1
        self.event_credit=COMMAND_WORK  # Pure numeric call-work exit only.

    def trace_query(self,reader,call):
        need(reader is self.trace_reader and self.event_active is None and not self.event_parse)
        try:result=reader._query_original(call)
        except BaseException as error:self.fail(error);raise
        self.event_query_returned(reader,result)
        return result

    def event_query_returned(self,reader,result):
        # Called only at the genuine original owner/query return. Every actual
        # returned DTO is retained before clearing its active parse domain.
        need(reader is self.event_owner or reader is self.trace_reader)
        need(self.event_active is not None and self.event_parse)
        self.event_active['result']=result
        self.event_active=None;self.event_parse=False

    def node_before_query(self,node):
        need(node is self.node and self._product_dom and self.model_credit>=24*PART+65536)
        self.guard_current() if self.compound is not None or self.current is not None else self.census()
    def node_before_literal(self,node):
        need(node is self.node and self._product_dom)
        self.census()  # node pending3P already fixed BEFORE each new owner/IO
    def node_literal_ready(self,node):
        need(node is self.node);self.census()
    def node_before_parse(self,node,row):
        need(node is self.node and row in node.rows and row['confirmed'])
        plan=project(row['raw'].decode('utf-8'))
        demand=16*plan.max_canonical+8*256*(plan.total_nodes+1)+2048*(plan.combined_depth+1)+32768
        need(demand<=8*PART);self.census()
    def post_document_read(self,reader,run,url,owner):
        need(reader is self.reader and self.current is None and len(self.completed)==1 and not self.post_documents
            and self.trace_reader is not None and self.trace_reader.cursor==4 and self.event_model.issued
            and self.node is not None and self.failure is None
            and all(type(v) is str for v in (run,url,owner))
            and (run,url,owner)==(self.host_selection.context.run,self.host_selection.context.fixture_url,self.host_selection.context.owner))
        self.post_work=LEXICAL_SLOT+COMMAND_WORK
        self.current=dict(work=self.post_work,entry=0,request=None,raw=None,raw_ref=None,retainer=None,result=None,tokens=[],controlReturn=None,post_current_document=True)
        try:
            self.census()
            with self.lock.held():self.node.guard()
            result=reader._read_original(run,url,owner)
            need(self.lock._owner is None and self.failure is None and not self.raw.state['pending'])
        except BaseException as error:self.fail(error);raise
        self.current['result']=result;self.post_documents.append(self.current);self.current=None
        self.post_work=COMMAND_WORK
        return result

    def reject_input_source(self,*_args,**_kwargs):raise NativeUIError('CurrentInput HOST stage is absent')

    def close_host(self):
        self.closed=True
        results=[]
        if self.node is not None and hasattr(self.node,'process'):results.extend(self.node.close_host())
        if self.intent is not None and hasattr(self.intent,'parent'):results.append(self.intent.close_host())
        if self.raw is not None and hasattr(self.raw,'directory'):results.append(self.raw.close_host())
        if self.model is not None and hasattr(self.model,'file'):results.append(self.model.close_host())
        # Base close is physical-only; it does not consult poisoned business data.
        results.append(super().close_host())
        return results
