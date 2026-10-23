"""Passive original Linux ownership for the independent Chat host observer.

No process discovery, launch, nonzero signal or device operation is provided.
Expected program hashes and the ownership predicate must come from the original
fixture controller, not from the Pico candidate or a completed-looking result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import errno
import hashlib
import os
from pathlib import Path
import re
import stat
import time

from adapters.chat_journey.evidence_archive import stamp,private
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.chat_actor_files import stamp as actor_stamp
from adapters.chat_journey.source_chunks import digest
from fixture.chat_actor_process import LinuxChatActorProcess

VERSION=1


class LinuxChatObserverProcess(LinuxChatActorProcess):
    """Acquire the exact originally LIVE observer before accepting its result.

    This proves kernel process/program/file ownership only. It does not prove
    an Actor's native graph, return delivery, exit status or complete cleanup.
    A late acquisition after exit is refused; old descriptor ownership cannot
    be reconstructed from private files.
    """
    def __init__(self,identity,entry,configuration,executable_sha256,entry_sha256,owned):
        need(type(identity) is str and re.fullmatch('[1-9][0-9]*:[1-9][0-9]*:[0-9a-f-]{36}',identity)
            and type(entry_sha256) is str and re.fullmatch('[0-9a-f]{64}',entry_sha256)
            and type(executable_sha256) is str and re.fullmatch('[0-9a-f]{64}',executable_sha256))
        self.expected_executable_sha256=executable_sha256
        self.original_identity=identity;self.entry=Path(entry);self.configuration=Path(configuration)
        self.entry_owner=None;self.fd_owner=None;self.fd=-1
        need(self.entry.is_absolute() and self.entry.resolve(strict=True)==self.entry
            and self.configuration.is_absolute() and self.configuration.resolve(strict=True)==self.configuration)
        PrivateFeatureState(self.configuration)._parent();info=self.configuration.lstat();private(info)
        self.configuration_stamp=stamp(info);self.entry_sha256=entry_sha256
        try:
            self.entry_owner=OriginalDescriptor(self.entry,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            info=os.fstat(self.entry_owner.fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and not info.st_mode&0o022
                and info.st_nlink==1 and 0<info.st_size<=1024*1024)
            self.entry_stamp=stamp(info);self.entry_original=os.pread(self.entry_owner.fd,1024*1024+1,0)
            need(len(self.entry_original)==info.st_size and hashlib.sha256(self.entry_original).hexdigest()==entry_sha256)
            self.input_sha=digest(self.inputs())
            self.source_files()
            super().__init__(int(identity.split(':')[0]),self.configuration.parent,executable_sha256,owned)
            self.executable_stamp_sha=digest(self.executable)
            need(self.process_identity==identity);self.guard()
        except BaseException:self.close();raise

    def inputs(self):
        return dict(identity=self.original_identity,entry=str(self.entry),configuration=str(self.configuration),
            executableSha256=self.expected_executable_sha256,entrySha256=self.entry_sha256,
            entryStamp=self.entry_stamp,configurationStamp=self.configuration_stamp)

    def source_files(self):
        need(digest(self.inputs())==self.input_sha and type(self.entry_original) is bytes and type(self.entry_stamp) is list
            and type(self.configuration_stamp) is list
            and all(type(value) is int for value in (*self.entry_stamp,*self.configuration_stamp)))
        self.entry_owner.require(self.entry_owner.fd)
        need(stamp(os.fstat(self.entry_owner.fd))==self.entry_stamp==stamp(self.entry.lstat())
            and os.pread(self.entry_owner.fd,1024*1024+1,0)==self.entry_original
            and hashlib.sha256(self.entry_original).hexdigest()==self.entry_sha256)
        PrivateFeatureState(self.configuration)._parent();info=self.configuration.lstat();private(info)
        need(stamp(info)==self.configuration_stamp)

    def original_program(self):
        need(self.sha256==self.expected_executable_sha256 and digest(self.executable)==self.executable_stamp_sha
            and actor_stamp(os.fstat(self.fd))==self.executable)

    def guard(self):
        if hasattr(self,'executable_stamp_sha'):self.original_program()
        return super().guard()

    def _arguments(self):
        self.source_files()
        with (Path('/proc')/str(self.pid)/'cmdline').open('rb') as stream:raw=stream.read(8193)
        need(len(raw)<=8192);arguments=raw.split(b'\0')
        # No -c/-m or extra argument can impersonate the reviewed entrypoint.
        need(len(arguments)==5 and arguments[-1]==b'' and arguments[1]==os.fsencode(self.entry)
            and arguments[2]==b'--config' and arguments[3]==os.fsencode(self.configuration))
        executable=os.stat(os.fsdecode(arguments[0]));actual=os.stat(f'/proc/{self.pid}/exe')
        need((executable.st_dev,executable.st_ino)==(actual.st_dev,actual.st_ino))
        self.source_files()

    def _absent(self):
        try:os.kill(self.pid,0)
        except ProcessLookupError as error:need(error.errno==errno.ESRCH)
        except OSError:need(False)
        else:raise NativeUIError('Original independent Chat observer is still present')
        try:(Path('/proc')/str(self.pid)).lstat()
        except FileNotFoundError:pass
        else:need(False) # Includes PID reuse; no forgiveness from start mismatch.

    def require_absent(self):
        """Two actual ESRCH probes while retaining the originally acquired OFDs."""
        self.fd_owner.require(self.fd);self.source_files();self.original_program()
        need(self.process_identity==self.original_identity
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.boot)
        started=time.monotonic();before=int(time.time()*1000);self._absent()
        value=dict(chatObserverProcessPresenceVersion=VERSION,sourceRole='independent-chat-host-observer',
            hostProcessIdentity=self.original_identity,queryProcessId=self.pid,presence='absent',errorSymbol='ESRCH',
            executableSha256=self.sha256,entrySha256=self.entry_sha256,configurationStamp=deepcopy(self.configuration_stamp),
            requestedEpochMs=before,capturedEpochMs=int(time.time()*1000))
        result=deepcopy(value);self.source_files();self.fd_owner.require(self.fd);self.original_program();self._absent()
        ended_epoch=int(time.time()*1000)
        need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.boot
            and before<=result['capturedEpochMs']<=ended_epoch<=before+1500
            and 0<=time.monotonic()-started<=1.5)
        return result

    def close(self):
        okay=super().close()
        if self.entry_owner is not None:okay=OriginalDescriptor.close(self.entry_owner) is True and okay
        return okay
