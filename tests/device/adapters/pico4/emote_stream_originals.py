"""One lossless Source4 range archive and aggregate for BOTH native roles."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import stat

from adapters.chat_journey.archive_file import signature
from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need
from adapters.pico4.audio_raw_archive import AudioRawArchive,AudioRawSourceLock
from adapters.pico4.emote_model_originals import expanded
from adapters.pico4.emote_stream_frame import FRAME_LIMIT,CONTROL_LIMIT
from adapters.pico4.emote_stream_policy import PicoEmoteStreamPolicy
from adapters.script_journey.history import canonical,MAX_FRAMES,MAX_RAW

VERSION=1
UNRESOLVED=[]


class PicoEmoteStreamOriginals:
    """All Parent/source/capture copies and role literals share512/16MiB.

    The reused audioRawJournalVersion1 is only a literal container. The exact
    new scope identifies Navigation-independent Emote execution policy. Native
    mutable current/control/intent files retain their worst-case allowance;
    each observed wire and each distinct read receipt remains an original.
    """
    def __init__(self,policy,roots,*,capacity=None):
        need(type(policy) is PicoEmoteStreamPolicy);policy.bound()
        need(capacity is getattr(policy,'capacity',None))
        self.capacity=self._capacity=capacity
        self.policy=self._policy=policy;self.host=host_identity()
        self.path=self._path=policy.parent.store.path.with_name(policy.parent.store.path.name+'.child-stream-raw.json')
        parent=policy.parent
        required=(parent.store.path.parent,parent.source.store.path.parent,parent.inputs.store.path.parent,parent.source.artifact_root)
        admitted={Path(path).resolve(strict=True) for path in (*required,*roots)}
        self.roots=self._roots=tuple(sorted((path for path in admitted
            if not any(path!=other and path.is_relative_to(other) for other in admitted)),key=str))
        scope=dict(picoEmoteStreamOriginalsVersion=1 if capacity is None else 2 if capacity.source_profile is None else 3,containerFormat='audioRawJournalVersion1-raw-only',
            budgetSha256=hashlib.sha256(policy.raw).hexdigest(),baselineSha256=policy.baseline_sha,
            parentIdentitySha256=hashlib.sha256(policy.parent_identity).hexdigest(),roots=[str(path) for path in self.roots],
            roles=['primary','actor'],maximumNativeFramesPerRole=256,maximumCompoundNativeFrames=512)
        if capacity is not None:
            scope['captureCapacitySha256']=capacity.descriptor_sha
            if capacity.source_profile is not None:
                scope.update(picoEmoteSourceTransactionVersion=1,picoEmoteSourcePhysicalVersion=2,
                    sourceProfileSha256=capacity.source_profile.sha256)
        self.scope=self._scope=canonical(scope);self.lock=self._lock=AudioRawSourceLock(policy.lock)
        self.monotonic=self._monotonic=parent.source.monotonic
        self.archive=self._archive=object.__new__(AudioRawArchive)
        try:
            if capacity is not None:capacity.bind_archive(self.archive,self.other_bill)
            AudioRawArchive.__init__(self.archive,self.path,scope,self.lock,self.identity,self.other_bill,self.monotonic)
            if capacity is not None:capacity.ready()
            policy.bound()
        except BaseException:UNRESOLVED.append(self);raise

    def identity(self):
        # No admission callback/clock is invoked on an already issued return.
        # The actual writer still verifies all original root/OFD/bytes itself.
        self.policy.host_identity()
        need(self.capacity is self._capacity)
        if self.capacity is not None:self.capacity.host_identity()
        need(host_identity()==self.host and self.policy is self._policy and self.path==self._path
            and self.archive is self._archive and self.archive.path==self.path and self.scope is self._scope and canonical(self.archive.scope)==self.scope
            and self.lock is self._lock and self.monotonic is self._monotonic and self.roots is self._roots
            and self.lock.primary is self.policy.original_lock)

    def other_bill(self):
        self.identity();files=stored=decoded=nodes=0
        def walk(path,depth):
            nonlocal files,stored,decoded,nodes
            need(depth<=8);directory=OriginalDescriptor(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                require_directory(directory,path)
                with os.scandir(directory.fd) as entries:names=[entry.name for entry in entries]
                for name in names:
                    nodes+=1;need(nodes<=4096);current=path/name
                    if current.parent==self.path.parent and (name==self.path.name or name.startswith(self.path.name+'.')):continue
                    info=current.lstat();need(info.st_uid==os.geteuid() and not stat.S_ISLNK(info.st_mode))
                    if stat.S_ISDIR(info.st_mode):walk(current,depth+1);continue
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=MAX_RAW)
                    before=signature(info);owner=OriginalDescriptor(current,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                    try:
                        owner.require(owner.fd);raw=os.pread(owner.fd,MAX_RAW+1,0);owner.require(owner.fd)
                        need(len(raw)==info.st_size and signature(os.fstat(owner.fd))==before==signature(current.lstat()))
                    finally:need(owner.close())
                    files+=1;stored+=len(raw);decoded+=len(raw)
                    if name.endswith('.json'):decoded+=expanded(json.loads(raw))
                    need(files<=MAX_FRAMES and stored<=MAX_RAW and decoded<=MAX_RAW)
                require_directory(directory,path)
            finally:need(directory.close())
        for root in self.roots:walk(root,0)
        # A native role has one mutable current, control ACK and pending file.
        # They are not historical samples, but their full possible retained
        # bytes/files are conservatively charged to the SAME compound bill.
        native=2*(FRAME_LIMIT+CONTROL_LIMIT+65)
        value=dict(parts=files+len(self.archive.pages)+1+6,storedBytes=stored+native,decodedBytes=decoded+native)
        if self.capacity is not None:
            extra=self.capacity.extra_bill();value={key:value[key]+extra[key] for key in value}
        return value

    def bound(self):
        self.identity();self.policy.bound();self.archive.verify();self.identity()
        if self.capacity is not None:self.capacity.admission()

    def close_host(self):
        result=self.archive.close_host()
        if not result and self not in UNRESOLVED:UNRESOLVED.append(self)
        return result
