"""Original model replies for the same remote Emote capture, before parsing.

Uses the existing raw writer unchanged. No native/product action or business
clock is permitted in return archival; new reservations retain Parent guards.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import stat

from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import integer,need
from adapters.chat_journey.archive_file import signature
from adapters.pico4.audio_raw_archive import AudioRawArchive,MAX_LITERAL
from adapters.script_journey.history import canonical,MAX_RAW,MAX_FRAMES
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
# Existing Source3 reserves48 raw fragments and two phase originals.
VIEWER_TAIL_PARTS=50
UNRESOLVED=[]


def expanded(value):
    """Charge every simultaneously retained packed transcript, including copies."""
    if type(value) is list:return sum(expanded(item) for item in value)
    if type(value) is not dict:return 0
    own=0
    if set(value)=={'encoding','bytes','sha256','data'} and value['encoding']=='zlib-base64-json':
        need(integer(value['bytes'],2,MAX_RAW));own=value['bytes']
    return own+sum(expanded(item) for item in value.values())


class EmoteModelOriginals:
    def __init__(self,capture):
        self.capture=capture;self.host=host_identity();self.token=None
        self.path=capture.store.path.with_name(capture.store.path.name+'.model-raw.json')
        scope=dict(picoEmoteModelOriginalsVersion=VERSION,captureIdentity=capture.identity,
            captureJournal=str(capture.store.path),parentPrefixSha256=hashlib.sha256(canonical(capture.parent_prefix)).hexdigest())
        self.scope=canonical(scope)
        roots={Path(path).resolve(strict=True) for path in (capture.store.path.parent,capture.primary.store.path.parent,
            capture.source.store.path.parent,capture.root)}
        self.roots=self.original_roots=tuple(sorted((path for path in roots if not any(path!=other and path.is_relative_to(other) for other in roots)),key=str))
        self.lock=ScriptSourceLock(capture.store.path.with_name(capture.store.path.name+'.model-raw-lock'))
        self.archive=object.__new__(AudioRawArchive)
        try:AudioRawArchive.__init__(self.archive,self.path,scope,self.lock,self.identity,self.other_bill,capture.monotonic)
        except BaseException:
            UNRESOLVED.append(self)
            try:self.archive.close_host()
            except Exception:pass
            raise
    def identity(self):
        # Already issued raw returns can outlive a business header or clock.
        # The writer still proves its OWN original journal/directory/OFD and
        # fixed host/scope. This never authorizes another getter or dispatch.
        need(host_identity()==self.host and canonical(self.archive.scope)==self.scope
            and self.archive.path==self.path)
    def other_bill(self):
        need(self.roots is self.original_roots)
        files=stored=decoded=0;nodes=0
        def walk(path,depth):
            nonlocal files,stored,decoded,nodes
            need(depth<=8);directory=OriginalDescriptor(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:
                require_directory(directory,path)
                with os.scandir(directory.fd) as entries:names=[entry.name for entry in entries]
                for name in names:
                    nodes+=1;need(nodes<=4096)
                    current=path/name
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
        # Count our own metadata too, plus the existing final viewer query's
        # worst-case original50 files. None is a second namespace budget.
        return dict(parts=files+len(self.archive.pages)+2+VIEWER_TAIL_PARTS,
            storedBytes=stored,decodedBytes=decoded)
    def reserve(self,command):
        need(self.token is None);self.capture.bound()
        self.token=self.archive.reserve('emote-model',command,MAX_LITERAL,side_bytes=VIEWER_TAIL_PARTS*65536)
        self.capture.bound() # Actual reservation/billing cannot renew admission.
    def retain(self,value):
        need(self.token is not None)
        result=self.archive.retain(self.token,value);self.token=None;return result
    def close_host(self):
        result=self.archive.close_host()
        if not result and self not in UNRESOLVED:UNRESOLVED.append(self)
        return result
