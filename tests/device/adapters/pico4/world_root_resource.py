"""Private resource-census-only participant on one cold World Parent.

No source/input authority, new writer or quota. All charges use the SAME
512-entry/16MiB Root. Other owners/stages are deliberately unsupported.
Serialized logical accounting is not a universal Python/native RSS bound.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0

VERSION=1  # Internal HOST contract; no public/native capability.
from dataclasses import dataclass
import hashlib
import os
import stat
from pathlib import Path

from adapters.chat_journey.archive_file import signature
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile

LIMIT=16777216
ENTRIES=512
PART=65536
PRECOUNT=32*PART
WINDOW=3*PART
FILE_STORED=3*PART
FILE_WORK=3*PART


@dataclass(frozen=True,eq=False)
class WorldRootSelection1:
    version:int=1
    limit:int=LIMIT
    entries:int=ENTRIES
    precount:int=PRECOUNT
    window:int=WINDOW


def selection(value):
    need(type(value) is WorldRootSelection1)
    for name,wanted in (('version',1),('limit',LIMIT),('entries',ENTRIES),('precount',PRECOUNT),('window',WINDOW)):
        actual=getattr(value,name);need(type(actual) is int and actual==wanted)


class WorldRootParticipant1:
    def __init__(self,config):
        selection(config)
        self.config=self._config=config
        # This charge exists BEFORE the Parent invokes its namespace callbacks,
        # before OriginalDescriptor and before the first scandir/stat inventory.
        self.precount=config.precount;self.window=config.window
        self.fixed=4096
        self.parent=self.directory=None
        self.records=[];self.entry_claims=[];self.metadata_claims=[];self.snapshots=[]
        self.failure=None;self.active=False;self.host_closed=False
        self.counter_candidate=None
        self.root=self.lock=self.parent_type=None
        self.credit={'version':1,'precount':PRECOUNT,'window':WINDOW}
        self._credit=self.credit
        need(self.precount+self.window+self.fixed<=LIMIT)

    def fail(self,error):
        if self.failure is None:self.failure=(error,error.__traceback__)

    def bind(self,parent,parent_type):
        need(self.parent is None and self.directory is None and not self.active)
        from adapters.pico4.world_web_prefix import PicoWorldWebPrefix
        need(parent_type is PicoWorldWebPrefix and type(parent) is PicoWorldWebPrefix)
        self.parent=parent;self.parent_type=parent_type
        self.root=parent.root;self.lock=parent.lock
        self.store=parent.store;self.source=parent.source;self.scope=parent.scope
        self.scope_sha=parent.scope_sha;self.role_sha=parent.role_sha
        self.parent_fields=tuple(vars(parent))
        try:
            self.check_data()
            # Strong owner is installed before its actual descriptor constructor.
            self.directory=object.__new__(OriginalDescriptor)
            OriginalDescriptor.__init__(self.directory,self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.directory_guard()
        except BaseException as error:self.fail(error);raise

    def check_data(self):
        selection(self.config)
        need(self.config is self._config and self.failure is None and not self.host_closed
            and self.credit is self._credit and type(self.credit) is dict
            and set(self.credit)=={'version','precount','window'})
        for name,wanted in (('version',1),('precount',PRECOUNT),('window',WINDOW)):
            need(type(self.credit[name]) is int and self.credit[name]==wanted)
        p=self.parent
        need(p is not None and type(p) is self.parent_type and p.resource_participant is self
            and p.root is self.root and p.lock is self.lock and p.store is self.store
            and p.store.path==self.root/'pico-world-web-prefix.json' and p.source is self.source
            and p.scope is self.scope and p.scope_sha==self.scope_sha and p.role_sha==self.role_sha
            and tuple(vars(p))==self.parent_fields
            and isinstance(self.root,Path) and self.root.is_absolute()
            and p.disk is None and p.state is None and p.history is None and p.vm is None
            and p.fence is None and p.runtime_guard is None and p.source.previous is None
            and p._source_pass_export is None and not p.failed and not p._actor_started)
        # All actual nonempty owners are rejected in this initial stage.
        need(len(self.records)<=1 and len(self.entry_claims)<=2)
        p.identity_control()

    def directory_guard(self):
        self.check_data();require_directory(self.directory,self.root)

    def held_size(self):
        self.check_data();p=self.parent;s=p.source;c=s.client
        # Exact currently held DTO/string fields. Deliberate conservative
        # duplicates across Parent/source/lock fields; no alias subtraction.
        values=(p.scope,p.disk,p.state,p.target,p.run,p.url,p.foreign,p.role,p.scope_sha,p.role_sha,
            s.previous,s.run,s.area,s.fixture_url,c.url,c.token,str(p.root),str(p.lock.path),str(p.store.path),self.credit)
        result=sum(canonical_size(value,LIMIT) for value in values)
        for row in self.records:
            result+=canonical_size(row['payload'],LIMIT)+len(row['raw'] or b'')
            result+=canonical_size(str(row['store'].path),LIMIT)+canonical_size(list(row['stamp']) if row['stamp'] else None,LIMIT)
        return result

    def bill(self,*,stored=0,live=0,metadata=0,entry=0):
        self.check_data()
        fixed=self.precount+self.window+self.fixed
        planned=len(self.records)*FILE_STORED
        work=len(self.records)*FILE_WORK
        sm=fixed+stored+planned+sum(self.metadata_claims)+metadata
        # Cold Parent A=0. A missing decoded/source-stage provider never supplies
        # an invented zero: that stage cannot call this resource-only API.
        dm=fixed+stored+live+sum(self.entry_claims)+entry+work+sum(self.metadata_claims)+metadata
        need(type(sm) is int and type(dm) is int and sm<=LIMIT and dm<=LIMIT)
        return {'stored':sm,'decoded':dm,'limit':LIMIT,'entries':len(self.records),
            'S':stored,'A':0,'P':live,'entryClaims':sum(self.entry_claims)+entry,
            'metadata':sum(self.metadata_claims)+metadata,'precount':self.precount,
            'window':self.window,'pendingStored':planned,'pendingWork':work,'fixed':self.fixed}

    def hold_file_before_init(self,owner,store,payload):
        need(not self.active and type(owner) is LifecycleProcessFile and not vars(owner)
            and type(store) is PrivateFeatureState and type(payload) is dict
            and store.path.parent==self.root and store.path.name=='world-resource-counter.json')
        self.check_data();need(not self.records)
        # Register/retain before ANY actual writer constructor or write. The
        # helper never calls either. The fixture alone performs its owned IO.
        row={'owner':owner,'store':store,'payload':payload,'raw':None,'stamp':None,'ready':False}
        self.records.append(row)
        try:
            need(canonical_size(payload,LIMIT)+1<=PART)
            self.bill(live=self.held_size());self.directory_guard()
        except BaseException as error:self.fail(error);raise

    def file_ready(self,owner):
        self.check_data();need(not self.active and len(self.records)==1)
        row=self.records[0];need(row['owner'] is owner and not row['ready'])
        try:
            need(owner.store is row['store'] and owner.path==row['store'].path
                and owner.file is owner._file and not owner.failed and owner.temporary is None and not owner.uncertain
                and type(owner.raw) is bytes and type(owner.stamp) is tuple)
            owner.guard()
            row['raw'],row['stamp'],row['ready']=owner.raw,owner.stamp,True
            self.bill(live=self.held_size());self.directory_guard()
        except BaseException as error:self.fail(error);raise

    def admit_current_factory(self,original,target,source_lock):
        """This profile has no typed current-source provider: fail BEFORE SDK."""
        need(not self.active)
        try:
            self.check_data()
            need(original is self.parent.adapter.original and type(target) is str
                and target==self.parent.target and source_lock is self.lock
                and self.lock._owner is None)
            # A real same-Root resource census precedes the absent-stage gate.
            # It never supplies a Native/candidate/current authority verdict.
            self.census()
            raise NativeUIError('Typed current-source resource provider is absent')
        except BaseException as error:self.fail(error);raise

    def hold_counter_candidate(self,owner,store,payload):
        """Finite owned filesystem-fault custody; never writer adoption."""
        self.check_data()
        need(not self.active and self.counter_candidate is None and len(self.records)==1
            and self.records[0]['ready'] and type(owner) is LifecycleProcessFile and not vars(owner)
            and type(store) is PrivateFeatureState and store.path==self.records[0]['store'].path
            and payload is self.records[0]['payload'])
        # Existing frozen literal and actual path lengths, bounded BEFORE any
        # candidate constructor/readback. The extra512 covers protected-path
        # suffixes, not a restriction of the Parent payload/path grammar.
        literal=canonical_size(payload,LIMIT)+1
        required=6*literal+12*(6*(len(str(store.path).encode('utf-8'))+512)+2)+49152
        need(required<=131072)
        self.bill(live=self.held_size(),metadata=131072)
        self.metadata_claims.append(131072)
        self.counter_candidate=(owner,store,payload,required)
        self.directory_guard()

    def names(self):
        self.directory_guard();result=[]
        # The permanent 2MiB precount reservation predates this allocation.
        os.lseek(self.directory.fd,0,os.SEEK_SET)
        with os.scandir(self.directory.fd) as entries:
            for item in entries:
                need(len(result)<ENTRIES and type(item.name) is str and len(item.name.encode('utf-8'))<=255)
                result.append(item.name)
        self.directory_guard()
        need(len(result)==len(set(result)))
        return sorted(result)

    def census(self,stage='resource-census'):
        need(type(stage) is str and stage=='resource-census' and not self.active)
        self.active=True
        try:
            self.check_data();need(len(self.snapshots)<2 and all(row['ready'] for row in self.records))
            entry=self.held_size();self.bill(live=entry,entry=entry)
            self.entry_claims.append(entry)  # No early debit after save/clear/return.
            names=self.names();need(self.counter_candidate is None)
            need(names==sorted(row['store'].path.name for row in self.records))
            n=len(names);r=len(str(self.root).encode('utf-8'))
            j=2+max(0,n-1)+n*(512+6*(r+1+255));m=8*j+768*n+4096
            self.bill(live=self.held_size(),metadata=m)
            self.metadata_claims.append(m)  # Before Parent.pins allocates any row.
            # Fresh bounded metadata census admits ALL physical bytes before
            # the original full-file readers allocate their payload windows.
            prospective=0
            for name in names:
                self.directory_guard()
                info=os.stat(name,dir_fd=self.directory.fd,follow_symlinks=False)
                need(stat.S_ISREG(info.st_mode) and info.st_nlink==1
                    and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
                    and 0<info.st_size<=PART)
                prospective+=info.st_size
            self.bill(stored=prospective,live=self.held_size())
            for row in self.records:row['owner'].guard()
            pins=self.parent.pins()  # Original closed OFD/full-byte/eight-stat path.
            self.directory_guard();need(names==self.names() and len(pins)==n)
            stored=0
            for pin,row in zip(pins,sorted(self.records,key=lambda row:str(row['store'].path))):
                owner=row['owner'];owner.guard()
                need(pin['path']==str(owner.path) and pin['signature']==list(row['stamp'])
                    and owner.raw is row['raw'] and owner.stamp is row['stamp']
                    and pin['sha256']==hashlib.sha256(row['raw']).hexdigest())
                stored+=pin['signature'][5]
            need(stored==prospective==sum(len(row['raw']) for row in self.records))
            result={'stage':stage,'bill':self.bill(stored=stored,live=self.held_size()),'pins':pins,
                'inputAllowed':False,'sourceAllowed':False,'parentPrepared':False}
            need(canonical_size(pins,LIMIT)<=j)
            self.snapshots.append(result);return result
        except BaseException as error:self.fail(error);raise
        finally:self.active=False

    def close_host(self):
        # Only the original held directory. File owner closes are separate and
        # no business/Parent/native retirement follows from this operation.
        if self.directory is None:return False
        result=self.directory.close()
        if result:self.host_closed=True
        return result
