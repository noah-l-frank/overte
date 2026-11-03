"""Declared native publisher model with REAL host files/original paired OFDs.

This exercises the proposed protocol, not compiled Qt/C++ or Android support.
Terminal fixture finalization closes only confirmed actual host descriptors;
it does not simulate native recovery of a failed pending publisher.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import fcntl
import hashlib
import os
import stat

from adapters.chat_journey.archive_file import signature
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need

PENDING='feature-pico-emote-capture-pending.json'
FIXED={'world-render-observation.json':262144,'feature-pico-world-model-draws.json':262144,'world-render-receipts-result.json':262144}


class NativePublisherModel:
    def __init__(self,root,guard):
        self.root,self.guard=root,guard;self.owners=[];self.files={};self.failed=False;self.events=[];self.fault=None;self.stopped=False;self.drained=False
        self.directory=object.__new__(OriginalDescriptor);self.owners.append(self.directory)
        OriginalDescriptor.__init__(self.directory,root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.directory_guard();names=list(root.iterdir());need(len(names)<=4096)
        need(not any(p.name.startswith('world-render-storage-') or p.name==PENDING for p in names))
        for name,limit in FIXED.items():
            owner=self.create(name);self.files[name]=dict(owner=owner,bytes=b'',physical=signature(os.fstat(owner.fd)),limit=limit)
        self.require()

    def directory_guard(self):
        require_directory(self.directory,self.root);need(self.guard() is not False)

    def create(self,name):
        self.directory_guard();owner=object.__new__(OriginalDescriptor);self.owners.append(owner)
        # Actual fresh openat + actual alias of THAT OFD, never an inode/seek
        # approximation or a reconstructed descriptor attestation.
        owner.fd=owner.anchor=-1;owner.closed=owner.lost=False
        owner.fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.directory.fd)
        owner.anchor=fcntl.fcntl(owner.fd,fcntl.F_DUPFD_CLOEXEC,0);info=os.fstat(owner.fd)
        owner.node=(info.st_dev,info.st_ino);owner.require(owner.fd);self.directory_guard()
        return owner

    def file(self,name):
        row=self.files[name];owner=row['owner'];owner.require(owner.fd);before=os.fstat(owner.fd)
        need(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o600 and before.st_nlink==1
            and before.st_uid==os.geteuid() and signature(before)==row['physical']
            and signature((self.root/name).lstat())==row['physical'])
        raw=os.pread(owner.fd,row['limit']+1,0);owner.require(owner.fd)
        need(raw==row['bytes'] and signature(os.fstat(owner.fd))==row['physical']);return row

    def require(self):
        need(not self.failed);self.directory_guard();need(not (self.root/PENDING).exists())
        for name,row in self.files.items():
            if not row.get('retired',False):self.file(name)
        self.directory_guard()

    def publish(self,name,nonce,raw):
        try:
            self.require();need(not self.stopped and not self.drained);need(name in FIXED or name=='world-render-storage-'+nonce+'.json')
            if name not in self.files:
                owner=self.create(name);self.files[name]=dict(owner=owner,bytes=b'',physical=signature(os.fstat(owner.fd)),limit=100000)
            row=self.file(name);self.events.append(('intent',name,nonce));pending=self.create(PENDING)
            marker=nonce.encode()+b'\n'+hashlib.sha256(raw).hexdigest().encode()+b'\n'
            need(os.write(pending.fd,marker)==len(marker));os.fsync(pending.fd);os.fsync(self.directory.fd)
            self.events.append(('pending-durable',name,len(raw)));need(0<len(raw)<=row['limit'])
            self.directory_guard();row['owner'].require(row['owner'].fd);os.ftruncate(row['owner'].fd,0)
            written=raw[:max(1,len(raw)//2)] if self.fault=='partial' else raw
            need(os.pwrite(row['owner'].fd,written,0)==len(written));os.fsync(row['owner'].fd)
            self.events.append(('written',name,len(written)))
            if self.fault=='partial':raise OSError('Actual partial native-model file write')
            row['owner'].require(row['owner'].fd);actual=os.pread(row['owner'].fd,len(raw)+1,0)
            stamp=signature(os.fstat(row['owner'].fd));need(actual==raw and signature((self.root/name).lstat())==stamp)
            self.directory_guard();row.update(bytes=raw,physical=stamp)
            if self.fault=='lost-complete':raise OSError('Actual completed native-model write/readback return lost')
            need(pending.close());os.unlink(PENDING,dir_fd=self.directory.fd);os.fsync(self.directory.fd);self.require()
        except BaseException:self.failed=True;raise

    def remove_receipt(self,nonce,digest):
        try:
            self.require();need(not self.stopped);name='world-render-storage-'+nonce+'.json'
            row=self.file(name);need(hashlib.sha256(row['bytes']).hexdigest()==digest)
            pending=self.create(PENDING);marker=nonce.encode()+b'\n'+digest.encode()+b'\n'
            need(os.write(pending.fd,marker)==len(marker));os.fsync(pending.fd);os.fsync(self.directory.fd)
            row=self.file(name);os.unlink(name,dir_fd=self.directory.fd);os.fsync(self.directory.fd)
            row['owner'].require(row['owner'].fd);need(os.fstat(row['owner'].fd).st_nlink==0 and not (self.root/name).exists())
            need(row['owner'].close());row['retired']=True
            need(pending.close());os.unlink(PENDING,dir_fd=self.directory.fd);os.fsync(self.directory.fd);self.require()
        except BaseException:self.failed=True;raise

    def stop(self):self.stopped=True

    def drain(self):
        self.require();need(self.stopped and not self.failed and all(row.get('retired',False)
            for name,row in self.files.items() if name not in FIXED))
        need(self.close_host());self.drained=True

    def close_host(self):
        results=[]
        for owner in reversed(self.owners):
            if getattr(owner,'fd',-1)<0 and getattr(owner,'anchor',-1)<0:continue
            results.append(owner.close())
        return all(results)
