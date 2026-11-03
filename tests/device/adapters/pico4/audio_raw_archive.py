"""Versioned original literal ranges; open-prefix ownership is not a closed file.

Every send/read first has durable worst-case admission. Every returned literal
is fsynced and referenced by a durable receipt before any source parser runs.
Unknown appends/CAS retain ownership and prohibit continuation or cold adoption.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import threading

from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import state as file_state
from adapters.script_journey.history import canonical,MAX_FRAMES,MAX_RAW
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
PART=65536
PAGE=32
MAX_LITERAL=1024*1024


def sha(raw):return hashlib.sha256(raw).hexdigest()


class AudioRawSourceLock:
    """Same original lock inode; a foreign thread must acquire its own OFD.

    The exact Primary SourceLock still binds all normal sources. Only archival
    read-only CAS uses this alias when a CLI worker returns on another thread.
    """
    def __init__(self,primary):
        need(type(primary) is ScriptSourceLock)
        self.primary=self.original=primary;self.path=primary.path;self.aliases={};self.node=None
    def own(self):
        need(self.primary is self.original and self.primary.path==self.path)
        owner=self.primary._owner
        if owner is not None and owner[2:]==(os.getpid(),threading.get_ident()):return self.primary
        key=(os.getpid(),threading.get_ident())
        if key not in self.aliases:
            need(len(self.aliases)<16);self.aliases[key]=ScriptSourceLock(self.path)
        alias=self.aliases[key];need(alias.path==self.path);return alias
    @contextmanager
    def held(self):
        selected=self.own()
        with selected.held():
            self.check_node();yield;self.check_node()
    def check_node(self):
        info=self.path.lstat();node=(info.st_dev,info.st_ino,info.st_uid,info.st_mode,info.st_nlink,info.st_size)
        if self.node is None:self.node=node
        need(node==self.node)
    def assert_held(self):self.own().assert_held();self.check_node()


class AudioRawArchive:
    """A warm original writer; no retry, truncation, namespace adoption or unlink."""
    def __init__(self,path,scope,lock,identity,bill,clock,*,literal_limit=MAX_LITERAL):
        # Assets already admits4MiB acquired literals. Its explicit new scope
        # may reuse these ranges; existing Audio/Navigation scopes stay1MiB.
        maximum=scope.get('maximumLiteralBytes',MAX_LITERAL) if type(scope) is dict else MAX_LITERAL
        need(type(literal_limit) is int and literal_limit in (MAX_LITERAL,4*MAX_LITERAL)
            and type(maximum) is int and maximum==literal_limit)
        self.store=PrivateFeatureState(path);self.scope=deepcopy(scope);self.scope_sha=json_digest(scope)
        self.literal_limit=self._literal_limit=literal_limit
        self.literal_profile=self.original_literal_profile=(literal_limit,self.scope_sha)
        self.lock,self.identity,self.other_bill,self.clock=lock,identity,bill,clock
        self._lock,self._identity,self._other_bill,self._clock=lock,identity,bill,clock
        self.host=host_identity();self.path=self.store.path;self.directory=OriginalDescriptor(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.original_directory=self.directory;self.failed=False;self.stopped=False;self.writer=None;self.open_data=b'';self.uncertain=[]
        self.unconfirmed_returns={};self.issued_reservations={}
        self.closed={};self.pages={};self.page_pins={};self.disk=self.pin=None
        self.state=dict(reads=0,pending=[],parts=[],pages=[])
        with self.lock.held():
            need(self.store.read() is None and not list(self.path.parent.glob(self.path.name+'.*')))
            self.save()

    def guard(self):
        self.lock.assert_held();need(not self.failed and host_identity()==self.host and self.path==self.store.path
            and self.scope_sha==json_digest(self.scope) and self.directory is self.original_directory
            and self.lock is self._lock and self.identity is self._identity and self.other_bill is self._other_bill and self.clock is self._clock)
        profile=self.literal_profile
        maximum=self.scope.get('maximumLiteralBytes',MAX_LITERAL) if type(self.scope) is dict else MAX_LITERAL
        need(profile is self.original_literal_profile and type(profile) is tuple and len(profile)==2
            and type(self.literal_limit) is type(self._literal_limit) is type(maximum) is int
            and self.literal_limit==self._literal_limit==maximum==profile[0]
            and profile[1]==self.scope_sha)
        self.identity();require_directory(self.directory,self.path.parent)

    def root_identity(self):
        self.guard()
        if self.disk is None:need(self.store.read() is None)
        else:
            value,raw,physical=file_state(self.store)
            need(value==self.disk and json_digest(value)==json_digest(self.disk) and physical==self.pin)

    def save(self):
        self.root_identity()
        value=dict(audioRawJournalVersion=VERSION,scope=deepcopy(self.scope),state=deepcopy(self.state))
        need(len(canonical(value))+1<=PART)
        self.store.write(value,self.disk)
        actual,raw,pin=file_state(self.store);need(actual==value)
        self.disk,self.pin=deepcopy(value),pin

    def part_path(self,index):return self.path.with_name(self.path.name+f'.part-{index:03d}.bin')
    def page_store(self,index):return PrivateFeatureState(self.path.with_name(self.path.name+f'.index-{index:02d}.json'))

    def verify(self):
        with self.lock.held():return self._verify()

    def _verify(self):
        self.root_identity()
        need(self.state==self.disk['state'] and json_digest(self.state)==json_digest(self.disk['state']))
        names=set()
        for index,row in enumerate(self.state['parts']):
            path=self.part_path(index);names.add(path.name)
            need(signature(path.lstat())==row['physical'])
            if row['closed']:
                need(index in self.closed and self.closed[index].stamp==row['physical'])
            else:
                need(index==len(self.state['parts'])-1 and self.writer is not None)
                self.writer.require(self.writer.fd)
                raw=os.pread(self.writer.fd,PART+1,0);self.writer.require(self.writer.fd)
                need(raw==self.open_data and len(raw)==row['bytes'] and sha(raw)==row['sha256']
                    and signature(os.fstat(self.writer.fd))==row['physical'])
        expected_pages=[dict(page=index,sha256=json_digest(value),physical=pin) for index,(value,pin) in sorted(self.page_pins.items())]
        need(self.state['pages']==expected_pages)
        for index,(value,pin) in self.page_pins.items():
            path=self.page_store(index).path;names.add(path.name)
            need(signature(path.lstat())==pin and json_digest(value)==json_digest(self.pages[index]))
        actual=set()
        with os.scandir(self.path.parent) as entries:
            for index,entry in enumerate(entries):
                need(index<4096)
                if entry.name.startswith(self.path.name+'.'):actual.add(entry.name)
        need(actual==names)

    def bill(self):
        rows=[row for value in self.pages.values() for row in value['receipts'] if row is not None]
        meta=len(canonical(self.disk))+1 if self.disk is not None else 0
        meta+=sum(len(canonical(value))+1 for value in self.pages.values())
        literal=sum(row['bytes'] for row in self.state['parts'])
        return dict(parts=len(self.state['parts']),literalBytes=literal,metadataBytes=meta,
            decodedBytes=literal+meta,storedBytes=literal+meta,receipts=len(rows),files=1+len(self.pages)+len(self.state['parts']))

    def maximum_receipt(self,token):
        return dict(read=token['read'],role=token['role'],command=deepcopy(token['command']),
            hostMonotonic=token['hostMonotonic'],returnedHostMonotonic=1000000000000000.0,
            kind='bytes',bytes=token['limit'],sha256='f'*64,ranges=[[511,65536,65536] for _ in range(token['parts'])])

    def metadata_capacity(self,pending):
        # Every already issued response retains its reservation. Admission of
        # a later request cannot spend an earlier receipt's guaranteed space.
        affected={token['read']//PAGE for token in pending}
        pages={index:deepcopy(self.pages[index]) for index in affected if index in self.pages}
        for token in pending:
            page=token['read']//PAGE;position=token['read']%PAGE
            if page not in pages:pages[page]=dict(audioRawRangeIndexVersion=VERSION,scopeSha256=self.scope_sha,page=page,receipts=[None]*PAGE)
            need(pages[page]['receipts'][position] is None)
            pages[page]['receipts'][position]=self.maximum_receipt(token)
        need(all(len(canonical(value))+1<=PART for value in pages.values()))
        maximum=deepcopy(self.state);maximum['pending']=deepcopy(pending)
        # Actual Linux signatures fit these complete unsigned64-bit fields.
        total=sum(token['parts'] for token in pending)
        maximum['parts'] += [dict(bytes=PART,sha256='f'*64,physical=[2**64-1]*8,closed=False) for _ in range(total)]
        maximum['pages']=[dict(page=index,sha256='f'*64,physical=[2**64-1]*8) for index in sorted(set(self.pages)|set(pages))]
        need(len(canonical(dict(audioRawJournalVersion=VERSION,scope=self.scope,state=maximum)))+1<=PART)

    def reserve(self,role,command,limit,*,side_bytes=0):
        verified=mutating=False
        try:
            with self.lock.held():
                self.verify();verified=True
                need(not self.stopped and type(role) is str and integer(limit,1,self.literal_limit) and self.state['reads']<MAX_FRAMES)
                need(integer(side_bytes,0,2*(11*48000*2*2+44)));json_digest(command);need(type(command) is dict and len(canonical(command))<=4096)
                current=self.other_bill();ours=self.bill();pending=self.state['pending']
                reserved_parts=sum(row['parts'] for row in pending);reserved_bytes=sum(row['limit']+row['sideBytes'] for row in pending)
                maximum_parts=(limit+PART-1)//PART+1
                need(current['parts']+ours['parts']+reserved_parts+maximum_parts<=MAX_FRAMES
                    and current['decodedBytes']+ours['decodedBytes']+reserved_bytes+limit+side_bytes+3*PART<=MAX_RAW
                    and current['storedBytes']+ours['storedBytes']+reserved_bytes+limit+side_bytes+3*PART<=MAX_RAW)
                read=self.state['reads'];clock=self.clock();need(number(clock,0,1e15))
                row=dict(read=read,role=role,command=deepcopy(command),limit=limit,parts=maximum_parts,scopeSha256=self.scope_sha,rootPath=str(self.path),
                    hostMonotonic=clock,thread=threading.get_ident(),sideBytes=side_bytes)
                self.metadata_capacity([*pending,row])
                mutating=True;self.state['pending'].append(row);self.state['reads']+=1;self.save()
                self.issued_reservations[read]=(json_digest(row),limit,threading.get_ident())
                return deepcopy(row)
        except BaseException:
            self.stopped=True
            # Pure predispatch refusal fences NEW work. Previously issued
            # responses can still use their original guaranteed reservations.
            if not verified or mutating:self.failed=True
            raise

    def _new_part(self):
        self.guard();index=len(self.state['parts']);path=self.part_path(index)
        writer=OriginalDescriptor('/proc/self/fd/'+str(self.directory.fd)+'/'+path.name,
            os.O_RDWR|os.O_APPEND|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.writer=writer;writer.require(writer.fd);os.fchmod(writer.fd,0o600);writer.require(writer.fd)
        self.open_data=b'';physical=signature(os.fstat(writer.fd))
        self.state['parts'].append(dict(bytes=0,sha256=sha(b''),physical=physical,closed=False));self.save()

    def _append(self,raw):
        self.verify();need(self.writer is not None and len(self.open_data)+len(raw)<=PART)
        writer=self.writer;row=self.state['parts'][-1];prefix=self.open_data
        writer.require(writer.fd);need(os.pread(writer.fd,PART+1,0)==prefix and signature(os.fstat(writer.fd))==row['physical'])
        offset=0
        while offset<len(raw):
            writer.require(writer.fd);written=os.write(writer.fd,raw[offset:]);writer.require(writer.fd)
            need(type(written) is int and written>0);offset+=written
        writer.require(writer.fd);os.fsync(writer.fd);writer.require(writer.fd)
        actual=os.pread(writer.fd,PART+1,0);writer.require(writer.fd)
        # The entire previous prefix remains exact across the authorized append.
        need(actual==prefix+raw and actual[:len(prefix)]==prefix and sha(actual[:len(prefix)])==row['sha256'])
        physical=signature(os.fstat(writer.fd));need(signature(self.part_path(len(self.state['parts'])-1).lstat())==physical)
        self.open_data=actual;row.update(bytes=len(actual),sha256=sha(actual),physical=physical);self.save()

    def seal_part(self):
        self.verify()
        if self.writer is None:return
        writer=self.writer;index=len(self.state['parts'])-1;row=self.state['parts'][index]
        writer.require(writer.fd);need(os.pread(writer.fd,PART+1,0)==self.open_data)
        os.fchmod(writer.fd,0o400);writer.require(writer.fd);os.fsync(writer.fd)
        need(os.pread(writer.fd,PART+1,0)==self.open_data);physical=signature(os.fstat(writer.fd))
        need(writer.close());self.writer=None
        original=ClosedOriginalFile(self.part_path(index),0o400,self.guard)
        raw,stamp=original.read();need(raw==self.open_data and stamp==physical)
        self.closed[index]=original;row.update(physical=stamp,closed=True);self.open_data=b'';self.save()

    def retain(self,token,value):
        try:
            # Capture the bounded return for a genuinely issued reservation
            # before an archival-root/OFD failure can unwind its caller. This
            # memory is explicitly unconfirmed, never a durable-source claim.
            need(type(token) is dict and type(token.get('read')) is int and host_identity()==self.host)
            read=token['read'];issued=self.issued_reservations.get(read)
            need(issued is not None and issued[0]==json_digest(token) and issued[2]==threading.get_ident())
            kind='none' if value is None else 'utf8' if type(value) is str else 'bytes'
            need(value is None or type(value) in (str,bytes));raw=b'' if value is None else value.encode('utf-8') if type(value) is str else value
            need(len(raw)<=issued[1])
            if read in self.unconfirmed_returns:need(self.unconfirmed_returns[read]==raw)
            else:self.unconfirmed_returns[read]=raw
            with self.lock.held():
                self.verify();need(token in self.state['pending'])
                ranges=[];offset=0
                while offset<len(raw):
                    if self.writer is None:self._new_part()
                    room=PART-len(self.open_data)
                    if room==0:self.seal_part();continue
                    piece=raw[offset:offset+room];index=len(self.state['parts'])-1;start=len(self.open_data)
                    self._append(piece);ranges.append([index,start,len(piece)]);offset+=len(piece)
                # Zero-byte/None originals still have their own distinct receipt.
                record=dict(read=token['read'],role=token['role'],command=deepcopy(token['command']),
                    hostMonotonic=token['hostMonotonic'],returnedHostMonotonic=self.clock(),kind=kind,
                    bytes=len(raw),sha256=sha(raw),ranges=ranges)
                page=token['read']//PAGE;position=token['read']%PAGE;store=self.page_store(page)
                old=deepcopy(self.pages.get(page));new=deepcopy(old) if old is not None else dict(audioRawRangeIndexVersion=VERSION,scopeSha256=self.scope_sha,page=page,receipts=[None]*PAGE)
                need(new['receipts'][position] is None);new['receipts'][position]=record
                need(len(canonical(new))+1<=PART);store.write(new,old)
                actual,unused,pin=file_state(store);need(actual==new);self.pages[page]=deepcopy(new);self.page_pins[page]=(deepcopy(new),pin)
                self.state['pages']=[dict(page=index,sha256=json_digest(value),physical=stamp) for index,(value,stamp) in sorted(self.page_pins.items())];self.state['pending'].remove(token);self.save();self.verify();self.unconfirmed_returns.pop(token['read']);self.issued_reservations.pop(token['read'])
                return dict(audioRawRangeVersion=VERSION,scopeSha256=self.scope_sha,read=token['read'],sha256=record['sha256'])
        except BaseException:self.failed=True;raise

    def literal(self,reference):
        with self.lock.held():
            self.verify();exact(reference,{'audioRawRangeVersion','scopeSha256','read','sha256'})
            need(type(reference['audioRawRangeVersion']) is int and reference['audioRawRangeVersion']==VERSION and reference['scopeSha256']==self.scope_sha
                and integer(reference['read'],0,self.state['reads']-1))
            index=reference['read'];record=self.pages[index//PAGE]['receipts'][index%PAGE]
            need(record is not None and record['sha256']==reference['sha256']);pieces=[]
            for part,start,size in record['ranges']:
                row=self.state['parts'][part]
                if row['closed']:raw,physical=self.closed[part].read();need(physical==row['physical'])
                else:
                    self.writer.require(self.writer.fd);raw=os.pread(self.writer.fd,PART+1,0);self.writer.require(self.writer.fd)
                    need(raw==self.open_data and signature(os.fstat(self.writer.fd))==row['physical'])
                need(integer(start,0,len(raw)) and integer(size,1,len(raw)-start));pieces.append(raw[start:start+size])
            raw=b''.join(pieces);need(len(raw)==record['bytes'] and sha(raw)==record['sha256'])
            return None if record['kind']=='none' else raw.decode('utf-8') if record['kind']=='utf8' else raw

    def close_host(self):
        # Failure cannot be promoted to a sealed journal. Reliable original
        # writer aliases may close; an uncertain/foreign recycled pair stays.
        results=[]
        if self.writer is not None:results.append(self.writer.close())
        results.extend(value.close() for value in self.closed.values());results.append(self.directory.close())
        return all(results)
