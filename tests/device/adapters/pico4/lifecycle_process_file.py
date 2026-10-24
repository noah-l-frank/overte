"""Actual original Process journal/parent OFDs across its own atomic saves."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import stat
import tempfile
from adapters.chat_journey.archive_file import signature
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import need
from adapters.script_journey.history import canonical


class LifecycleProcessFile:
    def __init__(self,store):
        self.store,self.path=store,store.path
        self.parent=self._parent=OriginalDescriptor(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.file=self._file=None;self.raw=self.stamp=None;self.uncertain=[]
        self.temporary=None;self.failed=False
        self.parent_guard()
        try:self.path.lstat()
        except FileNotFoundError:return
        self.file=self._file=OriginalDescriptor(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        self.raw,self.stamp=self.read(self.file,self.path)

    def parent_guard(self):
        need(not self.failed and self.store.path==self.path and self.parent is self._parent)
        self.parent.require(self.parent.fd);self.store._parent()
        info=self.path.parent.lstat();held=os.fstat(self.parent.fd)
        need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o700
            and (info.st_dev,info.st_ino)==(held.st_dev,held.st_ino)==self.parent.node)

    def read(self,owner,path):
        self.parent_guard();owner.require(owner.fd);info=os.fstat(owner.fd)
        need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
            and info.st_nlink==1 and 0<info.st_size<=65536)
        original=tuple(signature(info));raw=os.pread(owner.fd,65537,0)
        owner.require(owner.fd);self.parent_guard()
        need(len(raw)==info.st_size and tuple(signature(path.lstat()))==tuple(signature(os.fstat(owner.fd)))==original)
        return raw,original

    def guard(self):
        self.parent_guard();need(self.file is self._file)
        if self.file is None:
            try:self.path.lstat()
            except FileNotFoundError:return
            need(False)
        raw,physical=self.read(self.file,self.path)
        need(raw==self.raw and physical==self.stamp)

    def write(self,value,previous):
        self.guard();need(self.store.read()==previous)
        raw=canonical(value)+b'\n';need(len(raw)<=65536)
        descriptor,temporary=tempfile.mkstemp(dir=self.path.parent,prefix=self.path.name+'.pending-')
        self.temporary=temporary;candidate=None
        try:
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            candidate=OriginalDescriptor(temporary,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            observed,_stamp=self.read(candidate,self.path.parent/temporary);need(observed==raw)
            self.guard();need(self.store.read()==previous)
            # Retain the actual prepared OFD before publication. Opening the
            # pathname only afterwards could adopt an identical replacement.
            os.replace(os.path.basename(temporary),self.path.name,
                src_dir_fd=self.parent.fd,dst_dir_fd=self.parent.fd)
            os.fsync(self.parent.fd)
            observed,physical=self.read(candidate,self.path);need(observed==raw)
            old=self.file;self.file=self._file=candidate;candidate=None
            self.raw,self.stamp=observed,physical;self.temporary=None
            if old is not None:
                if not old.close():self.uncertain.append(old);need(False)
            self.guard()
        except BaseException:
            self.failed=True
            if candidate is not None:self.uncertain.append(candidate)
            # Unknown files/handles are not adopted, deleted or closed here.
            raise

    def close_host(self):
        return all([owner.close() for owner in (*self.uncertain,self.file,self.parent) if owner is not None])
