"""Single-use host history replay between two locked cleanup observations.

This authority reads private immutable transcripts only. It never permits a
target request, input, publication, recovery or an observed product result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import threading

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_script_history import canonical,same


def signature(path):
    info=path.lstat()
    return tuple(getattr(info,key) for key in ('st_dev','st_ino','st_uid','st_gid',
        'st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))


class SnapshotHistoryReadPass:
    """Pin actual owners while locked, replay all files, then requalify locked.

    File engines retain their normal actual opens, inode/mode/link/hash/schema
    and image checks and their own five-second deadlines. The final locked
    checks supply new target authority; this pass supplies historical bytes.
    """
    def __init__(self,role,prepared):
        f=role.feature;f.lock.assert_held();f.bound();role.bound();role.history_authority()
        need(f.role==role.role=='primary' and f.state['phase']=='cleaned'
            and f.state['current'] is None and f.state['handoff'] is None
            and role.state['phase']=='ready' and role.state['pending'] is None and not role._host_publication)
        # Full graph validation at _memory() below follows the phase callback;
        # checking the same graph twice during this preparation adds no guard.
        f.cleanup_observe_headers(role,prepared)
        f.cleanup_observe_phase(f.phase.status(),prepared['phase'])
        self.role,self.feature=role,f
        self.prepared=deepcopy(prepared)
        self.prepared_sha256=hashlib.sha256(canonical(self.prepared)).hexdigest()
        self.feature_store,self.role_store=f.store,role.store
        need(prepared['feature'] is not None and prepared['role'] is not None)
        self.paths=(f.store.path,role.store.path)
        self.root,self.run,self.configuration=f.root,f.run,deepcopy(f.config)
        self.scope=getattr(f.adapter,'_existing_input_scope',None)
        need(type(self.scope) is dict)
        self.scope_value=deepcopy(self.scope)
        self.process,self.thread=os.getpid(),threading.get_ident()
        self.signatures=tuple(signature(path) for path in self.paths)
        self.closed,self.started,self.replaying,self.digest=False,False,False,None
        self.files={}
        self.file_seal=self.file_seal_sha256=None
        self._headers();self._memory()

    def read_original(self,read,path,value):
        """Retain actual metadata around the unchanged full original reader."""
        need(self.replaying and self.file_seal is None)
        self.guard()
        actual=path(value);before=signature(actual)
        result=read(value)
        need(signature(actual)==before)
        self._file_pin(actual,before)
        return result

    def _file_pin(self,path,value):
        need(self.replaying and self.file_seal is None and path.parent==self.root)
        if path in self.files:need(self.files[path]==value)
        self.files[path]=value

    def absent(self,engine,value):
        need(self.replaying and self.file_seal is None)
        self.guard()
        need(engine.absent(value))
        path=engine._path(value)
        try:path.lstat()
        except FileNotFoundError:self._file_pin(path,None);return True
        need(False)

    def _verify_files(self):
        need(type(self.file_seal) is tuple and tuple(self.files.items())==self.file_seal
            and self._files_digest(self.file_seal)==self.file_seal_sha256)
        boundary=PrivateFeatureState(self.root/'snapshots-history-boundary.json')
        boundary._parent();root_before=signature(self.root)
        for path,pinned in self.file_seal:
            need(path.parent==self.root)
            try:actual=signature(path)
            except FileNotFoundError:need(pinned is None)
            else:need(pinned is not None and actual==pinned)
        boundary._parent();need(signature(self.root)==root_before)

    @staticmethod
    def _files_digest(files):
        return hashlib.sha256(canonical([[str(path),None if row is None else list(row)] for path,row in files])).hexdigest()

    def _memory(self,*,verify_graph=True):
        need(hashlib.sha256(canonical(self.prepared)).hexdigest()==self.prepared_sha256)
        if verify_graph:self.feature.cleanup_observe_owners(self.role,self.prepared)
        else:self.feature.cleanup_observe_headers(self.role,self.prepared)

    def _headers(self):
        f,r,p=self.feature,self.role,self.prepared
        need(not self.closed and os.getpid()==self.process and threading.get_ident()==self.thread
            and f.store is self.feature_store and r.store is self.role_store
            and (f.store.path,r.store.path)==self.paths and f.root==self.root and f.run==self.run
            and f.role==r.role=='primary' and not r._host_publication and same(f.config,self.configuration)
            and same(f.binding,p['binding']) and same(f.previous,p['feature']) and same(r.previous,p['role'])
            and getattr(f.adapter,'_existing_input_scope',None) is self.scope and same(self.scope,self.scope_value))
        for store,expected,pinned in zip((self.feature_store,self.role_store),
                (p['feature'],p['role']),self.signatures):
            # Semantic CAS alone cannot detect replacement followed by an ABA
            # restoration. Both actual metadata boundaries must retain the
            # original owner inode and modification/change timestamps too.
            need(signature(store.path)==pinned and same(store.read(),expected)
                and signature(store.path)==pinned)
        return True

    def guard(self):
        need(self.feature.lock._owner is None and self.started)
        return self._headers()

    def read(self):
        try:
            need(not self.closed and not self.started and self.feature.lock._owner is None)
            self.started=True;self.guard();self._memory()
            self.replaying=True
            try:frames=self.role._restore_historical_originals(self.guard,receipts=self)
            finally:self.replaying=False
            self.guard();self._memory()
            digest=hashlib.sha256(canonical(frames)).hexdigest()
            need(digest==self.prepared['framesSha256'])
            self.file_seal=tuple(self.files.items())
            self.file_seal_sha256=self._files_digest(self.file_seal)
            self.digest=digest
            return digest
        except BaseException:
            self.close();raise

    def finish(self):
        """Consume the pass under newly checked current target authority."""
        try:
            f,r=self.feature,self.role
            f.lock.assert_held();need(self.started and self.digest==self.prepared['framesSha256'])
            # No current acquisition consumes role.frames here. Its complete
            # digest is checked after all continuity callbacks below, before
            # this pass can authorize the next current read.
            self._headers();self._memory(verify_graph=False);self._verify_files()
            f.bound();r.bound();r.history_authority()
            need(f.state['phase']=='cleaned' and f.state['current'] is None and f.state['handoff'] is None)
            f.cleanup_observe_phase(f.phase.status(),self.prepared['phase'])
            self._headers();self._memory();self._verify_files()
            return True
        finally:self.close()

    def close(self):
        self.closed=True;self.replaying=False
