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


@dataclass(frozen=True,eq=False)
class WorldCurrentHostSelection1:
    context:WorldDocumentModelContext1
    base:WorldRootSelection1=field(default_factory=WorldRootSelection1)


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
        selection.context.validate()
        super().__init__(selection.base)
        self.host_selection=self._host_selection=selection
        self.original=None;self.raw=self.model=self.reader=self.focus=None
        self.ready=False;self.closed=False;self.constructing=True
        self.model_credit=selection.context.model_work()
        self.inventory_credit=4112;self.current=None;self.completed=[]
        self.birth=None
        # Fund ALL constructors/startup before directory/archive/model work.
        need(PRECOUNT+WINDOW+4096+self.inventory_credit+self.model_credit+RAW_WORK+LEXICAL_SLOT+COMMAND_WORK+MODEL_STORED<=LIMIT)

    def check_data(self):
        super().check_data()
        need(self.host_selection is self._host_selection and self.host_selection.base is self.config
            and type(self.host_selection) is WorldCurrentHostSelection1 and not self.closed)
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
        return self.model_credit+RAW_WORK+max(LEXICAL_SLOT+COMMAND_WORK,
            sum(call['work']+call['entry'] for call in calls))

    def live_size(self):
        value=4*super().held_size()+32768  # closed Parent key/object/control metadata
        def nodes(item):
            kind=type(item)
            if kind is dict:return 1+sum(1+nodes(v) for v in item.values())
            if kind is list:return 1+sum(nodes(v) for v in item)
            return 1
        def dto(item):
            if type(item) is bytes:return len(item)+256
            if type(item) is tuple:return sum(dto(v) for v in item)+64+8*len(item)
            # Canonical keys AND values plus their exact typed live-node meta.
            return 4*canonical_size(item,LIMIT)+256*nodes(item)
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
        if self.reader is not None:
            for name in ('last','raw','last_request'):value+=dto(getattr(self.reader,name))
        for call in [*self.completed,*([self.current] if self.current is not None else [])]:
            value+=1024  # call dict keys/control/container/reader references
            for name in ('request','raw','raw_ref','retainer','result','tokens'):value+=dto(call[name])
            value+=dto(call.get('controlReturn'))
            if 'plan' in call:
                plan=call['plan']
                from adapters.pico4.world_json_work import WorldJsonWork1
                need(type(plan) is WorldJsonWork1)
                value+=dto(dict(utf8=plan.utf8_bytes,canonical=plan.max_canonical,nodes=plan.total_nodes,
                    depth=plan.combined_depth,data=plan.decoded_data,metadata=plan.decoded_metadata,
                    lexical=plan.lexical_slot,streams=dict(plan.streams)))+256
        # Known stage/model/archive/reader/focus/context objects and exact
        # bound callback references. No payload or arbitrary closure is hidden.
        value+=6*256+4096
        return value

    def known_files(self):
        need(self.ready and not self.constructing)
        rows={}
        if self.model.file.file is not None:
            self.model.file.guard();rows[str(self.model.store.path)]=(0o600,list(self.model.file.stamp),hashlib.sha256(self.model.file.raw).hexdigest())
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

    def file_mode(self,path):
        # No physical/source verdict cache. Exact registered archive family only.
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
            self.identity();self.callback_identity();known=self.known_files();names=self.names()
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
        pending=MODEL_STORED+3*PART+65536
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
        self.reader=object.__new__(PicoWorldCurrentDocument)
        PicoWorldCurrentDocument.__init__(self.reader,self.send,self.get,self.native_epoch_ms,self.guard_current,
            self.model.pid,self.lock,monotonic=self.parent.source.monotonic,sleep=time.sleep,
            retain=self.retain,capacity=self.capacity,resource_provider=self)
        self.focus=object.__new__(PicoWorldCurrentInput)
        PicoWorldCurrentInput.__init__(self.focus,self.reader,self.reject_input_source,self.reject_input_source)
        return self.focus

    def document_read(self,reader,run,url,owner):
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
        self.check_data();need(self.current is not None and self.ready and time.monotonic()-self.birth<=120)
        self.identity();self.model.guard();self.census();return True
    def capacity(self):self.guard_current()
    def model_before_produce(self,model,request):
        need(model is self.model and self.current is not None and self.current['request']==request)
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
        header=canonical_size(self.raw.disk,PART)+token+parts*512+384
        page=self.raw.state['reads']//32
        existing=canonical_size(self.raw.pages[page],PART) if page in self.raw.pages else 512
        receipt=1024+quoted_bytes(role)+command_size+parts*64
        page_nodes=nodes(self.raw.pages[page]) if page in self.raw.pages else 48
        next_header_nodes=nodes(self.raw.disk)+nodes(command)+128
        next_page_nodes=page_nodes+nodes(command)+64
        # Pairs/memos/chunks/reference/header metadata is preheld separately
        # from4P byte +4*(5H+6I) decoded DATA +8P encoder overlap.
        required_meta=2*256*(5*next_header_nodes+6*next_page_nodes)+PART
        need(header<=PART and existing+receipt+256<=PART and required_meta<=24*PART)
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
            self.census()  # Actual literal+all copy/meta admitted BEFORE decode.
        except BaseException as error:self.fail(error);raise

    def reject_input_source(self,*_args,**_kwargs):raise NativeUIError('CurrentInput HOST stage is absent')

    def close_host(self):
        self.closed=True
        results=[]
        if self.raw is not None and hasattr(self.raw,'directory'):results.append(self.raw.close_host())
        if self.model is not None and hasattr(self.model,'file'):results.append(self.model.close_host())
        # Base close is physical-only; it does not consult poisoned business data.
        results.append(super().close_host())
        return results
