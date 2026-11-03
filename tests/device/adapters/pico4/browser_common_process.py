"""Original live Linux runner ownership for common-consumption transfer.

Kernel/program ownership only: the caller supplies the reviewed entrypoint and
original process identity. No discovery, launch, signals or native facts exist
here. The typed consumer must additionally validate the actual export record.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import re
import stat

from adapters.chat_journey.archive_file import signature
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import need
from fixture.chat_actor_process import LinuxChatActorProcess

VERSION=1
UNRESOLVED=[]


class OriginalBrowserRunnerProcess(LinuxChatActorProcess):
    """Same executable/PID/start/boot, reviewed script, exact closed argv."""
    def __init__(self,identity,entry,artifacts,executable_sha256,entry_sha256,owned):
        need(type(identity) is str and re.fullmatch('[1-9][0-9]*:[1-9][0-9]*:[0-9a-f-]{36}',identity)
            and type(entry_sha256) is str and re.fullmatch('[0-9a-f]{64}',entry_sha256))
        self.original_identity=identity;self.entry=Path(entry)
        self.entry_owner=None;self.fd_owner=None;self.fd=-1
        self.original_executable_owner=None;self.initializing=True;self.lost=False
        need(self.entry.is_absolute() and self.entry.resolve(strict=True)==self.entry)
        self.entry_sha=entry_sha256;self.expected_executable_sha=executable_sha256
        self.scope=self.original_scope=(identity,str(self.entry),str(Path(artifacts)),executable_sha256,entry_sha256,owned)
        try:
            self.entry_owner=self.original_entry_owner=OriginalDescriptor(self.entry,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            info=os.fstat(self.entry_owner.fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_nlink==1
                and not info.st_mode&0o022 and 0<info.st_size<=1024*1024)
            self.entry_stamp=tuple(signature(info));self.entry_raw=os.pread(self.entry_owner.fd,1024*1024+1,0)
            need(len(self.entry_raw)==info.st_size and hashlib.sha256(self.entry_raw).hexdigest()==entry_sha256)
            self.entry_seal=(self.entry_owner,self.entry_stamp,self.entry_raw)
            self.source_files()
            super().__init__(int(identity.split(':')[0]),artifacts,executable_sha256,owned)
            self.initializing=False;need(self.process_identity==identity);self.guard()
        except BaseException:
            # No foreign/recycled half is closed by this cleanup attempt.
            if not self.close() and not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)
            raise

    def source_files(self):
        need(self.scope is self.original_scope and (self.original_identity,str(self.entry),self.scope[2],
            self.expected_executable_sha,self.entry_sha,self.scope[5])==self.scope)
        owner,stamp,raw=self.entry_seal
        need(self.entry_owner is self.original_entry_owner is owner and self.entry_stamp is stamp
            and self.entry_raw is raw and type(stamp) is tuple and type(raw) is bytes)
        owner.require(owner.fd)
        need(tuple(signature(os.fstat(owner.fd)))==tuple(signature(self.entry.lstat()))==stamp
            and os.pread(owner.fd,len(raw)+1,0)==raw and hashlib.sha256(raw).hexdigest()==self.entry_sha)
        owner.require(owner.fd)

    def _arguments(self):
        self.source_files();root=Path('/proc')/str(self.pid)
        with (root/'cmdline').open('rb') as stream:raw=stream.read(8193)
        need(len(raw)<=8192);args=raw.split(b'\0')
        need(len(args)==5 and args[-1]==b'' and args[2:4]==[b'--area',b'tablet-web'])
        entry=Path(os.fsdecode(args[1]));cwd=(root/'cwd').resolve(strict=True)
        need((cwd/entry if not entry.is_absolute() else entry).resolve(strict=True)==self.entry)
        executable=Path(os.fsdecode(args[0]));actual=os.stat(root/'exe')
        named=os.stat(cwd/executable if not executable.is_absolute() else executable)
        need((named.st_dev,named.st_ino)==(actual.st_dev,actual.st_ino))
        self.source_files()

    def guard(self):
        self.source_files()
        if self.initializing and self.original_executable_owner is None:
            # Base constructor has just opened this original and completed its
            # full executable read. No caller callback intervenes here.
            need(type(self.fd_owner) is OriginalDescriptor)
            self.original_executable_owner=self.fd_owner
        need(not self.lost and self.fd_owner is self.original_executable_owner
            and self.original_identity==self.process_identity and self.sha256==self.expected_executable_sha
            and self.path==Path(self.scope[2]) and self.owned is self.scope[5])
        return super().guard()

    def close(self):
        if self.lost:return False
        if (self.entry_owner is not None and self.entry_owner is not getattr(self,'original_entry_owner',None)
                or self.fd_owner is not None and self.fd_owner is not self.original_executable_owner):
            self.lost=True
            if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)
            return False
        okay=super().close()
        if self.entry_owner is not None:okay=self.entry_owner.close() and okay
        if not okay:
            self.lost=True
            if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)
        return okay
