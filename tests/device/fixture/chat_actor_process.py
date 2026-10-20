"""Linux kernel qualification of a dedicated, already-owned Chat fixture actor.

Read-only: this module never launches, signals or discovers an unowned process.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

from adapters.chat_actor_files import identity,node,stamp
from adapters.native_feature_observation import integer,need
from adapters.normal_ui import NativeUIError


class LinuxChatActorProcess:
    def __init__(self,pid,directory,executable_sha256,owned):
        need(sys.platform.startswith('linux') and integer(pid,1) and callable(owned)
             and type(executable_sha256) is str and re.fullmatch('[0-9a-f]{64}',executable_sha256))
        self.pid,self.path,self.owned=pid,Path(directory),owned;self.fd=-1
        need(self.path.is_absolute() and self.path.resolve(strict=True)==self.path)
        root=self.path.lstat();need(stat.S_ISDIR(root.st_mode) and stat.S_IMODE(root.st_mode)==0o700 and root.st_uid==os.geteuid())
        self.root=node(root);self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        need(re.fullmatch('[0-9a-f-]{36}',self.boot));self.start=self._start()
        self._arguments()
        self.fd=os.open(f'/proc/{pid}/exe',os.O_RDONLY|os.O_CLOEXEC)
        try:
            before=os.fstat(self.fd);need(stat.S_ISREG(before.st_mode));self.executable=stamp(before)
            digest=hashlib.sha256()
            while True:
                data=os.read(self.fd,1024*1024)
                if not data:break
                digest.update(data)
            need(stamp(os.fstat(self.fd))==self.executable and digest.hexdigest()==executable_sha256)
            self.sha256=executable_sha256;self.guard()
        except BaseException:
            self.close();raise

    @property
    def process_identity(self):return f'{self.pid}:{self.start}:{self.boot}'

    def _start(self):
        need(self.owned(self.pid) is True)
        root=Path('/proc')/str(self.pid);need(root.stat().st_uid==os.geteuid())
        # comm may contain spaces or ')'; fields after its final ')' begin at
        # state (field 3), so index 19 is kernel starttime (field 22).
        fields=(root/'stat').read_text().rsplit(')',1)[1].split()
        need(fields[0] not in ('Z','X') and len(fields)>19 and re.fullmatch('[1-9][0-9]*',fields[19]))
        return fields[19]

    def _arguments(self):
        raw=(Path('/proc')/str(self.pid)/'cmdline').read_bytes().split(b'\0')
        need(raw.count(b'--testScript')==1 and raw.count(b'--e2eChatActorDir')==1)
        index=raw.index(b'--e2eChatActorDir');need(index+1<len(raw) and raw[index+1]==os.fsencode(self.path))

    def guard(self):
        try:
            need(self.fd>=0 and self._start()==self.start
                 and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.boot
                 and self.path.resolve(strict=True)==self.path)
            root=self.path.lstat();need(node(root)==self.root and stat.S_ISDIR(root.st_mode)
                and stat.S_IMODE(root.st_mode)==0o700 and root.st_uid==os.geteuid())
            self._arguments();need(stamp(os.fstat(self.fd))==self.executable
                and stamp(os.stat(f'/proc/{self.pid}/exe'))==self.executable and self.owned(self.pid) is True)
            return True
        except (OSError,ValueError,IndexError):
            raise NativeUIError('Owned native Chat actor process is unavailable') from None

    def released(self,original):
        identity(original);self.guard();found=False
        # fd links are kernel descriptors, including '(deleted)' files. Never
        # mistake path absence or a successful unlink for descriptor release.
        for descriptor in (Path('/proc')/str(self.pid)/'fd').iterdir():
            try:current=descriptor.stat()
            except FileNotFoundError:continue # A concurrent close is allowed.
            if node(current)==original:found=True
        self.guard();return not found

    def close(self):
        if self.fd>=0:os.close(self.fd);self.fd=-1
