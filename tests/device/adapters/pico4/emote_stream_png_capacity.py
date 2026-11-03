"""Actual original PNG file backing a conservative future-copy allowance.

PNG is an original image, not a <=64KiB history part. No ClosedOriginalFile
limit changes. This owner holds its own actual paired OFDs through finalization.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
import stat

from adapters.chat_journey.archive_file import signature
from adapters.graphics_journey.originals import GraphicsOriginals,record
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need
from adapters.script_journey.history import canonical
from adapters.pico4.probe_originals import same_callable


class PicoEmotePNGCapacity:
    def __init__(self,images,value,guard):
        need(type(images) is GraphicsOriginals and callable(guard));record(value)
        need(value['kind']=='image' and value['phase']=='saved')
        self.images=images;self.value=value;self.metadata=canonical(value);self.guard=guard
        self.path=images._path(value);self.directory=self.file=None;self.stamp=None
        need(guard() is not False)
        self.directory=OriginalDescriptor(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.file=OriginalDescriptor(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        self._pins=(self.images,self.value,self.metadata,self.guard,self.path,self.directory,self.file)
        self.read();need(guard() is not False)

    def read(self):
        need(self.images is self._pins[0] and self.value is self._pins[1] and self.metadata is self._pins[2]
            and same_callable(self.guard,self._pins[3]) and self.path==self._pins[4]
            and self.directory is self._pins[5] and self.file is self._pins[6]
            and self.guard() is not False and canonical(self.value)==self.metadata)
        require_directory(self.directory,self.path.parent);self.file.require(self.file.fd)
        before=os.fstat(self.file.fd);stamp=signature(before)
        need(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o600 and before.st_uid==os.geteuid()
            and before.st_nlink==1 and before.st_size==self.value['bytes'] and before.st_size<=33554432
            and (before.st_dev,before.st_ino)==(self.value['file']['device'],self.value['file']['inode'])
            and (self.stamp is None or self.stamp==stamp))
        raw=os.pread(self.file.fd,before.st_size+1,0);self.file.require(self.file.fd)
        need(len(raw)==before.st_size and hashlib.sha256(raw).hexdigest()==self.value['sha256']
            and signature(os.fstat(self.file.fd))==signature(self.path.lstat())==stamp)
        require_directory(self.directory,self.path.parent);need(self.guard() is not False)
        if self.stamp is None:self.stamp=stamp
        return dict(path=str(self.path),sha256=self.value['sha256'],bytes=before.st_size,physical=list(stamp))

    def close_host(self):
        return all(owner.close() for owner in (self.file,self.directory) if owner is not None)
