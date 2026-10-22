"""Once-only original host cursor replacement; no SDK or target input.

Actual process death, candidate/birth qualification and input ownership belong
outside this host primitive. They must precede its durable intent callback.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
import stat
import uuid

from adapters.native_fd_owner import OriginalDescriptor,fcntl
from .adapter_session import AdapterSessionError,STATE_SCHEMA_VERSION

VERSION=1


def need(value):
    if not value:raise AdapterSessionError('Original Pico binding transfer is unavailable or unresolved')


def state(value):
    need(type(value) is dict and set(value)=={'schemaVersion','processIdentity','sessionNonce','nextSequence'}
        and type(value['schemaVersion']) is int and value['schemaVersion']==STATE_SCHEMA_VERSION
        and type(value['processIdentity']) is str and 0<len(value['processIdentity'])<=160
        and all(33<=ord(char)<=126 for char in value['processIdentity'])
        and type(value['sessionNonce']) is str and len(value['sessionNonce'])==64
        and all(char in '0123456789abcdef' for char in value['sessionNonce'])
        and type(value['nextSequence']) is int and 1<=value['nextSequence']<=0xffffffff)
    return value


def stamp(info):
    return dict(device=str(info.st_dev),inode=str(info.st_ino),size=info.st_size,
        mtimeNs=info.st_mtime_ns,ctimeNs=info.st_ctime_ns)


def private(info,*,directory=False):
    need((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
        and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==(0o700 if directory else 0o600)
        and (directory or info.st_nlink==1))


def pairs(items):
    result={}
    for key,value in items:need(key not in result);result[key]=value
    return result


class OriginalBindingTransfer:
    """One warm source owner; a lost publication is reconciled read-only.

    Exact original open-file descriptions stay held across the caller's process
    transition. A copied/replaced state or recycled descriptor is never adopted.
    Unknown input/callback ownership and cold transfer recovery are not inferred.
    """
    def __init__(self,session):
        from .adapter_session import PicoOpenXrAdapterSession
        need(type(session) is PicoOpenXrAdapterSession and fcntl is not None)
        self.session=session;self.root=self.old=self.lock_owner=self.new=None;self.pending=None;self.failed=False
        self.temporary=None;self.original=None
        try:
            parent=session.state_path.parent;need(parent.is_absolute() and parent.resolve(strict=True)==parent)
            private(parent.lstat(),directory=True)
            self.root=OriginalDescriptor(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.lock_owner=OriginalDescriptor(session.lock_path,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            with self.locked():
                self.old=OriginalDescriptor(session.state_path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
                self.original=self.snapshot(self.old,session.state_path)
                need(session._load()==self.original['state'])
        except BaseException:
            self.close_host();raise AdapterSessionError('Original Pico binding ownership is unavailable') from None

    def guard_root(self):
        self.root.require(self.root.fd);parent=self.session.state_path.parent
        private(parent.lstat(),directory=True);private(os.fstat(self.root.fd),directory=True)
        need(parent.resolve(strict=True)==parent and (parent.stat().st_dev,parent.stat().st_ino)==self.root.node)
        self.lock_owner.require(self.lock_owner.fd);current=self.session.lock_path.lstat();private(current)
        held=os.fstat(self.lock_owner.fd);private(held)
        need(current.st_size==held.st_size==0 and (current.st_dev,current.st_ino)==self.lock_owner.node)

    @contextmanager
    def locked(self):
        self.guard_root();fcntl.flock(self.lock_owner.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:self.guard_root();yield;self.guard_root()
        finally:
            self.lock_owner.require(self.lock_owner.fd);fcntl.flock(self.lock_owner.fd,fcntl.LOCK_UN)

    def snapshot(self,owner,path):
        self.guard_root();owner.require(owner.fd);before=os.fstat(owner.fd);private(before)
        need(0<before.st_size<=4096)
        raw=os.pread(owner.fd,4097,0);current=path.lstat();private(current)
        need(stamp(before)==stamp(os.fstat(owner.fd))==stamp(current) and len(raw)==before.st_size)
        value=state(json.loads(raw.decode('utf-8'),object_pairs_hook=pairs))
        result=dict(bindingTransferVersion=VERSION,state=deepcopy(value),stamp=stamp(before),sha256=hashlib.sha256(raw).hexdigest())
        owner.require(owner.fd);self.guard_root();need(stamp(path.lstat())==stamp(os.fstat(owner.fd))==stamp(before))
        return result

    def capture(self):
        with self.locked():
            need(not self.failed and self.pending is None and self.original is not None)
            result=deepcopy(self.original);need(self.snapshot(self.old,self.session.state_path)==self.original)
            return result

    def prepare(self,successor,intent,before_publish):
        state(successor);need(callable(intent) and callable(before_publish) and self.pending is None
            and successor['nextSequence']==1 and all(successor[key]!=self.original['state'][key] for key in ('processIdentity','sessionNonce')))
        need(self.snapshot(self.old,self.session.state_path)==self.original)
        raw=(json.dumps(successor,sort_keys=True,separators=(',',':'))+'\n').encode();need(len(raw)<=4096)
        self.temporary=self.session.state_path.with_name('.binding-transfer-'+uuid.uuid4().hex+'.json')
        descriptor=os.open(self.temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        self.new=OriginalDescriptor(self.temporary,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        prepared=self.snapshot(self.new,self.temporary)
        self.pending=dict(successor=deepcopy(successor),prepared=prepared,intent=intent,before_publish=before_publish,phase='prepared')
        # Independent copies precede callback execution; callback edits cannot
        # alter either original cursor or the exact prepared successor source.
        intent(dict(bindingTransferVersion=VERSION,original=deepcopy(self.original),prepared=deepcopy(prepared)))
        before_publish();need(self.snapshot(self.old,self.session.state_path)==self.original
            and self.snapshot(self.new,self.temporary)==prepared)
        self.pending['phase']='publication-issued';before_publish()
        os.replace(self.temporary,self.session.state_path);os.fsync(self.root.fd)

    def observed(self):
        need(self.pending is not None and self.pending['phase']=='publication-issued')
        self.pending['before_publish']()
        actual=self.snapshot(self.new,self.session.state_path);prepared=self.pending['prepared']
        need(actual['state']==self.pending['successor'] and actual['sha256']==prepared['sha256']
            and all(actual['stamp'][key]==prepared['stamp'][key] for key in ('device','inode','size','mtimeNs'))
            and actual['stamp']['ctimeNs']>=prepared['stamp']['ctimeNs'] and self.session._load()==actual['state'])
        result=dict(bindingTransferVersion=VERSION,original=deepcopy(self.original),current=deepcopy(actual))
        self.pending['before_publish']();need(self.snapshot(self.new,self.session.state_path)==actual)
        self.pending['before_publish']();return result

    def replace(self,successor,*,intent,before_publish):
        try:
            with self.locked():
                need(not self.failed)
                if self.pending is None:self.prepare(deepcopy(successor),intent,before_publish)
                else:need(self.pending['successor']==successor and self.pending['intent'] is intent
                    and self.pending['before_publish'] is before_publish)
                return self.observed()
        except Exception:
            # Only an issued publication with its exact original new OFD can
            # be reconciled; a failed intent/guard never permits late replay.
            if self.pending is None or self.pending['phase']!='publication-issued':self.failed=True
            raise AdapterSessionError('Original Pico binding transfer remains unresolved; no cursor or journal is discarded') from None

    def reconcile(self):
        with self.locked():
            need(not self.failed);return self.observed()

    def close_host(self):
        """Only original host handles; unknown temporary/state files remain."""
        okay=True
        for owner in (self.new,self.old,self.lock_owner,self.root):
            if owner is not None:okay=owner.close() and okay
        return okay
