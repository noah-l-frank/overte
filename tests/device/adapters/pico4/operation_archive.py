"""Private bounded original stdio bytes, durable before their parser/next read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.operation_protocol import (need,PART_LIMIT,RESPONSE_LIMIT,STDERR_LIMIT,REQUEST_LIMIT,FILE_LIMIT,BYTE_LIMIT,dto_bytes)


class OperationArchive:
    def __init__(self,path,scope):
        self.path=Path(path);need(self.path.is_absolute())
        self.directory=OriginalDescriptor(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        require_directory(self.directory,self.path);need(not self.names())
        self.rows={};self.writers={};self.uncertain=[];self.closed=False
        self.store=PrivateFeatureState(self.path/'operation-host.json');self.journal=LifecycleProcessFile(self.store)
        self.state=None;self.root(dict(picoOperationArchiveVersion=1,scope=scope,program=None,phase='new',completed=[],pending=None))
    def names(self):
        result=set()
        with os.scandir(self.path) as scan:
            for entry in scan:
                need(len(result)<FILE_LIMIT);result.add(entry.name)
        return result
    def bind(self,program):
        self.guard();need(self.state['program'] is None);self.root(dict(self.state,program=program))
    def guard(self):
        need(not self.closed);require_directory(self.directory,self.path)
        expected=set(self.rows)|set(self.writers)|{'operation-host.json'}
        need(self.names()==expected)
        self.journal.guard()
        for owner in self.rows.values():owner.read()
        for name,(owner,raw,physical) in self.writers.items():
            owner.require(owner.fd);need(os.pread(owner.fd,PART_LIMIT+1,0)==raw
                and signature(os.fstat(owner.fd))==signature((self.path/name).lstat())==physical)
    def root(self,value):
        dto_bytes(value,65536);self.journal.write(value,self.state);self.state=value
    def reserve(self,request):
        self.guard();need(self.state['pending'] is None)
        files=self.names();used=sum((self.path/name).stat().st_size for name in files)
        # One entire response, stderr and request plus immutable receipt and
        # actual overlapping root-CAS temporary, before any pipe write/read.
        need(len(files)+64+1+1+1+1<=FILE_LIMIT and used+RESPONSE_LIMIT+STDERR_LIMIT+REQUEST_LIMIT+2*65536<=BYTE_LIMIT)
        state=dict(self.state,pending=request,phase='issued');dto_bytes(dict(state,completed=self.state['completed']+['f'*64]),65536);self.root(state)
    def append(self,name,raw):
        need(type(raw) is bytes and raw and len(raw)<=PART_LIMIT)
        require_directory(self.directory,self.path)
        if name not in self.writers:
            need(name not in self.rows and '/' not in name and '\\' not in name)
            path=self.path/name
            owner=OriginalDescriptor(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC)
            os.fchmod(owner.fd,0o600);self.writers[name]=(owner,b'',signature(os.fstat(owner.fd)))
        owner,previous,physical=self.writers[name];owner.require(owner.fd);need(len(previous)+len(raw)<=PART_LIMIT)
        need(os.pread(owner.fd,PART_LIMIT+1,0)==previous
            and signature(os.fstat(owner.fd))==signature((self.path/name).lstat())==physical)
        position=0
        while position<len(raw):
            owner.require(owner.fd)
            written=os.pwrite(owner.fd,raw[position:],len(previous)+position)
            need(written>0);position+=written
        os.fsync(owner.fd);owner.require(owner.fd);current=previous+raw
        physical=signature(os.fstat(owner.fd))
        need(os.pread(owner.fd,PART_LIMIT+1,0)==current and physical==signature((self.path/name).lstat()))
        self.writers[name]=(owner,current,physical)
    def seal(self,name):
        owner,raw,previous=self.writers[name];owner.require(owner.fd)
        need(raw and os.pread(owner.fd,PART_LIMIT+1,0)==raw
            and signature(os.fstat(owner.fd))==signature((self.path/name).lstat())==previous)
        os.fchmod(owner.fd,0o400);os.fsync(owner.fd);owner.require(owner.fd)
        physical=signature(os.fstat(owner.fd));need(physical==signature((self.path/name).lstat()))
        original=ClosedOriginalFile(self.path/name,0o400,lambda:require_directory(self.directory,self.path))
        observed,stamp=original.read();need(observed==raw and stamp==physical)
        need(owner.close());del self.writers[name];self.rows[name]=original
        return dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),physical=physical)
    def put(self,name,raw):
        self.append(name,raw);return self.seal(name)
    def finish(self,receipt):
        self.guard();need(self.state['pending'] is not None)
        raw=dto_bytes(receipt,65536);number=len(self.state['completed']);self.put(f'receipt-{number:03d}.json',raw)
        self.root(dict(self.state,pending=None,phase='ready',completed=self.state['completed']+[hashlib.sha256(raw).hexdigest()]))
        self.guard()
    def close(self):
        self.guard();need(not self.writers and self.state['pending'] is None)
        self.root(dict(self.state,phase='closed'));self.guard();need(self.journal.close_host())
        need(all(row.close() for row in self.rows.values()) and self.directory.close());self.closed=True
