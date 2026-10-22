"""Live read-only ownership of already verified host inputs; no new admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import fcntl
import errno
import os
from pathlib import Path
import stat
import weakref


MAX_DIRECTORIES=128
MAX_ENTRIES=4096
MAX_DEPTH=16
MAX_FILES=256
DUPFD_QUERY=getattr(fcntl,'F_DUPFD_QUERY',None)


class CandidateReadSealUnavailable(ValueError):
    pass


def need(value):
    if not value:raise ValueError('Pico original candidate read seal changed')


def stamp(value):
    return tuple(getattr(value,key) for key in ('st_dev','st_ino','st_mode','st_uid','st_gid',
        'st_size','st_mtime_ns','st_ctime_ns','st_nlink'))


def same_description(descriptor,anchor):
    return DUPFD_QUERY is not None and fcntl.fcntl(descriptor,DUPFD_QUERY,anchor)==1


def owned_open(path,flags):
    if DUPFD_QUERY is None:raise CandidateReadSealUnavailable('Original OFD query unavailable')
    descriptor=os.open(path,flags);anchor=None
    try:
        anchor=fcntl.fcntl(descriptor,fcntl.F_DUPFD_CLOEXEC,0)
        try:need(same_description(descriptor,anchor))
        except OSError as error:
            if error.errno in (errno.EINVAL,errno.ENOSYS):raise CandidateReadSealUnavailable('Original OFD query unavailable') from None
            raise
        return descriptor,anchor,os.fstat(descriptor)
    except BaseException:
        # Neither freshly created handle has escaped this function yet.
        os.close(descriptor)
        if anchor is not None:os.close(anchor)
        raise


def close_all(descriptors):
    for descriptor,anchor,original in descriptors:
        try:
            value=os.fstat(descriptor)
            # Kernel OFD identity is essential: even the same original inode
            # opened again under this number is a foreign descriptor lifetime.
            if (value.st_dev,value.st_ino)==original and same_description(descriptor,anchor):
                os.close(descriptor);os.close(anchor)
            # If either half was lost, deliberately retain the uncertain pair.
            # Process finalization owns its eventual release, never this GC.
        except OSError:pass


def bounded_decoder_tree(root):
    """One cold inventory, bounded before descent; never used by a query."""
    root=Path(root);pending=[(root,0)];directories={};jars=set();entries=0
    while pending:
        path,depth=pending.pop();need(depth<=MAX_DEPTH and len(directories)<MAX_DIRECTORIES)
        before=path.stat();need(stat.S_ISDIR(before.st_mode) and not path.is_symlink())
        directories[str(path)]=stamp(before)
        with os.scandir(path) as scan:
            for entry in scan:
                entries+=1;need(entries<=MAX_ENTRIES and not entry.is_symlink())
                if entry.is_dir(follow_symlinks=False):pending.append((Path(entry.path),depth+1))
                elif entry.name.endswith('.jar'):
                    need(entry.is_file(follow_symlinks=False));jars.add(str(Path(entry.path)))
        need(stamp(path.stat())==directories[str(path)])
    need(all(stamp(Path(path).stat())==original for path,original in directories.items()))
    return jars,directories


class CandidateReadSeal:
    """Retain original hashed inodes, refusing every later mutation/replacement.

    This never verifies a candidate. The caller supplies the original verifier's
    already accepted digests and a complete current inventory/argument snapshot.
    No changed input can refresh/rebuild this seal. The original live descriptor
    prevents inode reuse; kernel ctime also detects writes with restored mtime.
    """
    def __init__(self,inventory,metadata,result,*,directories=None):
        self.inventory,self.metadata=inventory,metadata
        self.original_metadata=deepcopy(metadata());self.original_inventory=deepcopy(inventory())
        need(self.original_inventory and all(type(key) is str and type(value) is str and len(value)==64
            for key,value in self.original_inventory.items()))
        directories={} if directories is None else deepcopy(directories)
        need(len(self.original_inventory)<=MAX_FILES and len(directories)<=MAX_DIRECTORIES)
        self.rows=[];descriptors=[]
        try:
            for name,digest in sorted(self.original_inventory.items()):
                path=Path(name);need(path.is_absolute());resolved=path.resolve(strict=True)
                descriptor,anchor,before=owned_open(resolved,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
                descriptors.append((descriptor,anchor,(before.st_dev,before.st_ino)));need(stat.S_ISREG(before.st_mode) and before.st_nlink>0)
                checksum=hashlib.sha256()
                for block in iter(lambda:os.read(descriptor,1024*1024),b''):checksum.update(block)
                original=stamp(before)
                need(checksum.hexdigest()==digest and stamp(os.fstat(descriptor))==original
                    and path.resolve(strict=True)==resolved and stamp(path.stat())==original)
                self.rows.append((path,resolved,descriptor,original,anchor))
            for name,original in sorted(directories.items()):
                path=Path(name);need(path.is_absolute() and not path.is_symlink());resolved=path.resolve(strict=True)
                descriptor,anchor,before=owned_open(resolved,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_DIRECTORY)
                descriptors.append((descriptor,anchor,(before.st_dev,before.st_ino)))
                need(stat.S_ISDIR(before.st_mode) and stamp(os.fstat(descriptor))==original
                    and stamp(path.stat())==original)
                self.rows.append((path,resolved,descriptor,original,anchor))
            self.result=deepcopy(result);self.closed=False
            self.check()
            self.finalizer=weakref.finalize(self,close_all,tuple(descriptors))
        except BaseException:
            close_all(descriptors)
            raise

    def check(self):
        try:return self._check()
        except BaseException:
            # Once invalid, this lifetime cannot resume even if a transient
            # dependency/environment later appears unchanged again.
            if hasattr(self,'finalizer'):self.close()
            else:self.closed=True
            raise

    def _check(self):
        result=deepcopy(self.result)
        need(not self.closed and self.metadata()==self.original_metadata
            and self.inventory()==self.original_inventory)
        for path,resolved,descriptor,original,anchor in self.rows:
            need(same_description(descriptor,anchor)
                and stamp(os.fstat(anchor))==original
                and fcntl.fcntl(anchor,fcntl.F_GETFD)&fcntl.FD_CLOEXEC
                and fcntl.fcntl(descriptor,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY
                and fcntl.fcntl(descriptor,fcntl.F_GETFD)&fcntl.FD_CLOEXEC
                and path.resolve(strict=True)==resolved and stamp(os.fstat(descriptor))==original
                and stamp(path.stat())==original)
        need(self.metadata()==self.original_metadata and self.inventory()==self.original_inventory)
        return result

    def close(self):
        self.closed=True;self.finalizer()
