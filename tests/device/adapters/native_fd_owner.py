"""Linux original open-file-description ownership; no inode-only cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
try:import fcntl
except ImportError:fcntl=None

from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError

QUERY=getattr(fcntl,'F_DUPFD_QUERY',None) if fcntl is not None else None


class OriginalDescriptor:
    """An original descriptor plus an independently retained kernel alias.

    A lost/recycled half poisons this owner. Both uncertain handles are retained
    for host process finalization; a foreign replacement is never closed here.
    """
    def __init__(self,path,flags):
        need(QUERY is not None)
        self.fd=self.anchor=-1;self.closed=self.lost=False
        descriptor=os.open(path,flags);anchor=None
        try:
            anchor=fcntl.fcntl(descriptor,fcntl.F_DUPFD_CLOEXEC,0)
            info=os.fstat(descriptor);self.node=(info.st_dev,info.st_ino)
            self.fd,self.anchor=descriptor,anchor;self.require(descriptor)
        except BaseException:
            # These newly opened handles have not escaped to a caller.
            os.close(descriptor)
            if anchor is not None:os.close(anchor)
            self.fd=self.anchor=-1;raise

    def require(self,descriptor):
        try:
            need(not self.closed and not self.lost and type(descriptor) is int and descriptor==self.fd
                and self.fd>=0 and self.anchor>=0 and self.fd!=self.anchor)
            info=os.fstat(descriptor);anchor=os.fstat(self.anchor)
            need((info.st_dev,info.st_ino)==(anchor.st_dev,anchor.st_ino)==self.node
                and fcntl.fcntl(descriptor,QUERY,self.anchor)==1)
        except BaseException:
            self.lost=True;raise

    def close(self):
        if self.closed:return True
        try:self.require(self.fd)
        except (OSError,ValueError,NativeUIError):return False
        os.close(self.fd);os.close(self.anchor)
        self.fd=self.anchor=-1;self.closed=True
        return True
