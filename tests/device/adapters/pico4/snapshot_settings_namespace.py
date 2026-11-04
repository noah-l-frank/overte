"""Source2-only prospective bill of actual known Snapshot originals.

This grants no Native/input/restore authority. A live typed Snapshot context
supplies its existing original owners; names alone never admit a new file.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import stat
import threading

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import digest
from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need,integer
from adapters.pico4.lifecycle_namespace_bill import canonical_size,strict
from adapters.script_journey.history import canonical,unpack,MAX_FRAMES,MAX_RAW

UNRESOLVED=[]


class SnapshotSettingsNamespaceBill:
    def __init__(self,raw):
        self.raw=self.original_raw=raw;self.lock=self.original_lock=raw.lock
        self.path=self.original_path=raw.path.parent;self.host=host_identity();self.thread=threading.get_ident()
        self.directory=self.original_directory=object.__new__(OriginalDescriptor)
        self.windows=[];self.failed=False
        try:
            OriginalDescriptor.__init__(self.directory,self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.resource()
        except BaseException:self.poison();raise

    def poison(self):
        self.failed=True
        if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)

    def resource(self):
        need(not self.failed and self.raw is self.original_raw and self.lock is self.original_lock
            and self.path is self.original_path and self.directory is self.original_directory
            and self.raw.path.parent==self.path and self.host==host_identity() and self.thread==threading.get_ident())
        self.lock.assert_held();require_directory(self.directory,self.path)

    def read(self,path,expected,physical,mutex=None):
        """Fresh complete bytes from a KNOWN original, never inode discovery."""
        self.resource();need(path.parent==self.path and type(expected) is bytes and len(expected)<=65536)
        owner=object.__new__(OriginalDescriptor);self.windows.append(owner)
        try:
            OriginalDescriptor.__init__(owner,path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            owner.require(owner.fd);before=os.fstat(owner.fd)
            if mutex is not None:mutex._check(owner.fd,path)
            need(stat.S_ISREG(before.st_mode) and before.st_uid==os.geteuid() and before.st_nlink==1
                and stat.S_IMODE(before.st_mode)==0o600 and signature(before)==list(physical))
            raw=os.pread(owner.fd,65537,0);owner.require(owner.fd);self.resource()
            need(raw==expected and len(raw)==before.st_size and signature(path.lstat())==signature(os.fstat(owner.fd))==list(physical))
            if mutex is not None:mutex._check(owner.fd,path)
            need(owner.close());self.windows.remove(owner);return raw
        except BaseException:self.poison();raise

    def known(self,context):
        """Only the actual existing owners can supply expected root/manifests."""
        from adapters.pico4.snapshot_settings_scope2_baseline import PicoSnapshotSettingsScope2Baseline
        from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
        from adapters.pico4.snapshot_close_owner import PicoSnapshotCloseOwner
        need(type(context) is PicoSnapshotSettingsScope2Baseline and context.raw is self.raw
            and context.lock is self.lock and context.run==self.raw.run and context.binding==self.raw.binding)
        context.bound();base=context.parent;need(type(base) is PicoSnapshotCancelOwner)
        roots=[];containers=[];graphs=[];seen_graphs=set()
        def graph(value):
            if value is not None and id(value) not in seen_graphs:
                seen_graphs.add(id(value));graphs.append(value)
        def root(store,value):
            need(store.path.parent==self.path)
            if value is not None:roots.append((store,value));graph(value)
        def originals(owner):
            owner.verify();root(owner.root,owner.disk);graph(owner.values);graph(owner.scope)
            if owner.disk is not None:containers.append(owner)
        root(base.store,base.disk);graph(base.state);originals(base.originals)
        root(context.store,context.disk);graph(context.state);originals(context.originals)
        if base.files.state is not None:root(base.files.store,base.files.state)
        if base.save_owner is not None:
            saved=base.save_owner;need(saved.parent is base and saved.lock is self.lock)
            root(saved.store,saved.disk);graph(saved.state);originals(saved.originals)
        closed=base.close_owner
        if closed is not None:
            need(type(closed) is PicoSnapshotCloseOwner and closed.base is base and closed.lock is self.lock)
            closed.bound();root(closed.store,closed.disk);graph(closed.state);originals(closed.originals);originals(closed.statuses)
            returned=closed.parent;bg=closed.bg
            root(returned.store,returned.disk);graph(returned.state);originals(returned.originals)
            root(bg.store,bg.disk);graph(bg.state);graph(bg.parent);originals(bg.originals)
            root(bg.parent_store,bg.parent_disk);originals(bg.parent_originals)
            for store,header,owner in bg.ancestors:root(store,header);originals(owner)
        checkpoint=context.closed_checkpoint
        need(checkpoint is context.original_closed_checkpoint)
        if checkpoint is not None:
            from adapters.pico4.snapshot_settings_close import PicoSnapshotSettingsClose
            need(type(checkpoint) is PicoSnapshotSettingsClose and checkpoint.baseline is context
                and checkpoint.parent is closed and checkpoint.lock is self.lock)
            checkpoint.bound();root(checkpoint.store,checkpoint.disk);graph(checkpoint.state)
        # The raw root is guarded by its already held original Lifecycle file;
        # its immutable children have their own admitted original descriptors.
        self.raw.resource();root(self.raw.store,self.raw.state)
        rows={};parts=0
        for store,value in roots:
            data=canonical(value)+b'\n';store._parent();physical=signature(store.path.lstat())
            # Expected data comes from actual typed warm owners. Their own
            # guards bracket these full physical windows; no live fact is read
            # from a merely named header.
            if store.path.name in rows:need(rows[store.path.name][1]==data)
            else:rows[store.path.name]=(store.path,data,physical,'root',None)
        for owner in containers:
            manifest=owner.disk['chunks'];history=owner.history
            need(len(manifest)==len(history.identities))
            for i,expected in enumerate(manifest):
                path=history._path(i);need(history.signature(i)==history.identities[i])
                value=history.store(i).read();need(digest(value)==expected and history.signature(i)==history.identities[i])
                data=canonical(value)+b'\n';physical=signature(path.lstat())
                if path.name in rows:need(rows[path.name][1]==data)
                else:rows[path.name]=(path,data,physical,'chunk',None);parts+=1
        for path,data,physical in self.raw.known_children():
            need(path.name not in rows);rows[path.name]=(path,data,list(physical),'chunk',None);parts+=1
        mutex=self.mutex(context)
        try:info=mutex.path.lstat()
        except FileNotFoundError:
            need(base.files.state is None)
        else:
            need(base.files.state is not None and base.files.disk is not None
                and base.files.store.read()==base.files.disk==base.files.state)
            base.files.validate(base.files.state)
            need(mutex.path.name not in rows)
            rows[mutex.path.name]=(mutex.path,b'',signature(info),'mutex',mutex)
        return rows,parts,graphs

    def mutex(self,context):
        from adapters.pico4.snapshot_settings_scope2_baseline import PicoSnapshotSettingsScope2Baseline
        from adapters.pico4.snapshot_capture_files import PicoSnapshotCaptureFiles
        from adapters.script_journey.lock import ScriptSourceLock
        need(type(context) is PicoSnapshotSettingsScope2Baseline and context.raw is self.raw)
        files=context.parent.files
        need(type(files) is PicoSnapshotCaptureFiles and files.source.lock is self.lock
            and type(files.lock) is ScriptSourceLock and files.lock.path.parent==self.path
            and files.lock.path==files.store.path.with_name(files.store.path.name+'.lock'))
        return files.lock

    def measure(self,context):
        """One global family bill; original source and quotas are not reset.

        Existing roots keep their original typed warm owners' authority. This
        opens new full-byte/OFD windows; it does not assert continued OFD
        ownership that those legacy writers never provided.
        """
        try:
            self.resource()
            named={}
            with os.scandir(self.path) as entries:
                for index,entry in enumerate(entries):
                    need(index<4096)
                    if entry.name.startswith('snapshot-'):named[entry.name]=entry
            # Bound actual named files before constructing canonical copies or
            # expanding any history. Names do not admit a root or child.
            sizes={};mutex=self.mutex(context)
            for name,entry in named.items():
                info=entry.stat(follow_symlinks=False)
                need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid()
                    and stat.S_IMODE(info.st_mode)==0o600 and info.st_nlink==1 and 0<=info.st_size<=65536
                    and (info.st_size>0 or name==mutex.path.name))
                sizes[name]=info.st_size
            stored=sum(sizes.values());need(stored<=MAX_RAW)
            # Two bounded copies cover the named JSON and its derived exact
            # expected bytes; all decoded graphs and prospective wire copies
            # are billed separately below.
            need(2*stored+3*65536+2097152<=MAX_RAW)
            rows,parts,graphs=self.known(context);need(set(rows)==set(named) and parts<=MAX_FRAMES)
            expected=sum(len(row[1]) for row in rows.values());need(expected==stored)
            retained=sum(canonical_size(graph) for graph in graphs)
            codec=self.raw.codec.metadata_bytes();held=self.raw.resource_bytes()
            need(2*stored+retained+codec+held+3*65536+2097152<=MAX_RAW)
            expanded=0;largest=0
            def expand(value):
                nonlocal expanded,largest
                if type(value) is dict:
                    if set(value)=={'encoding','bytes','sha256','data'}:
                        size=value['bytes'];need(integer(size,2,MAX_RAW))
                        prospective=expanded+size
                        need(2*stored+max(retained,2*prospective)+max(largest,size)
                            +codec+held+3*65536+2097152<=MAX_RAW)
                        self.raw.codec.guard();output=unpack(value);self.raw.codec.guard()
                        need(canonical_size(output)==size)
                        expanded=prospective;largest=max(largest,size);expand(output)
                    else:
                        for item in value.values():expand(item)
                elif type(value) is list:
                    for item in value:expand(item)
            for name,(path,expected,physical,kind,actual_mutex) in sorted(rows.items()):
                raw=self.read(path,expected,physical,actual_mutex)
                if kind=='mutex':need(raw==b'' and actual_mutex is mutex);continue
                value=strict(raw)
                if kind=='chunk':need(type(value.get('chatSampleChunkVersion')) is int and value['chatSampleChunkVersion']==1)
                expand(value)
            self.resource()
            current=set()
            with os.scandir(self.path) as entries:
                for index,entry in enumerate(entries):
                    need(index<4096)
                    if entry.name.startswith('snapshot-'):current.add(entry.name)
            need(current==set(rows))
            return dict(parts=parts,storedBytes=stored,
                decodedBytes=stored+max(retained,2*expanded)+codec+held,
                transientBytes=stored+largest+3*65536,largestExpandedBytes=largest,
                currentGraphBytes=retained,expandedProtocolBytes=expanded)
        except BaseException:self.poison();raise

    def close_host(self):
        if self.failed or self.windows:return False
        self.resource()
        if not self.directory.close():self.poison();return False
        return True
