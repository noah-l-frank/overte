"""Closed immutable file originals with bounded, kernel-owned read windows.

An admitted file's bytes/full physical stamp remain immutable. Reopening is a
new read window of that qualified file, never continued ownership of an old OFD
or discovery/adoption of another journal. The original directory remains held.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import stat

from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import need


def signature(info):
    return [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns]


class ClosedOriginalFile:
    """Every opened pair closes only after its actual F_DUPFD_QUERY succeeds."""
    def __init__(self,path,mode,parent_guard):
        need(mode in (0o600,0o400) and callable(parent_guard))
        self.path,self.mode,self.parent_guard=path,mode,parent_guard
        self.raw=self.stamp=None;self.active=None;self.failed=False

    def read(self,validate=None):
        need(not self.failed and self.active is None)
        owner=None
        try:
            self.parent_guard()
            owner=self.active=OriginalDescriptor(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            info=os.fstat(owner.fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==self.mode
                and info.st_nlink==1 and 0<info.st_size<=65536)
            raw=os.pread(owner.fd,65537,0);original=signature(info)
            need(len(raw)==info.st_size and signature(self.path.lstat())==signature(os.fstat(owner.fd))==original)
            if self.stamp is not None:need(original==self.stamp and raw==self.raw)
            if validate is not None:validate(raw)
            self.parent_guard();owner.require(owner.fd)
            need(signature(self.path.lstat())==signature(os.fstat(owner.fd))==original)
            # Preserve an uncertain pair without closing either recycled half.
            need(owner.close());self.active=None
            if self.stamp is None:self.stamp,self.raw=original,raw
            return raw,original
        except BaseException:
            self.failed=True
            if owner is not None and owner.close():self.active=None
            raise

    def close(self):
        # No retry or adoption of an uncertain descriptor. The host process
        # owns its finalization; a foreign replacement must remain untouched.
        return self.active is None
