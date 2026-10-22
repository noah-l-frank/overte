"""Passively acquire an already-owned native fixture peer; never discover/start."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import time

from adapters.chat_actor_files import ChatActorFiles,SOURCE,stamp,validate_actor_source
from adapters.native_chat_observation import ChatCaptureOwner,NativeChatObservation,OwnedChatCapture
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from fixture.chat_actor_process import LinuxChatActorProcess
from fixture.owned_processes import OWNER_VARIABLE



class OwnedChatPeer:
    """Static compiled identity + actual kernel/executable/native FD ownership.

    The existing fixture config selects the peer's original private directory;
    only the original native SOURCE supplies its PID and cache birth. No process
    enumeration, launch, signal, Chat command or cache mutation occurs here.
    """
    def __init__(self,config_store,files_store,*,source_lock=None,clock_ms=lambda:int(time.time()*1000),
                 monotonic=time.monotonic,sleep=time.sleep):
        self.process=self.files=None
        try:
            need(isinstance(config_store,PrivateFeatureState) and isinstance(files_store,PrivateFeatureState)
                and config_store.path!=files_store.path and all(callable(value) for value in (clock_ms,monotonic,sleep)))
            self.config_store,self.files_store=config_store,files_store
            self.clock_ms,self.monotonic,self.sleep=clock_ms,monotonic,sleep
            before=config_store.path.lstat();self.config=deepcopy(config_store.read());self.config_stamp=stamp(before)
            need(stamp(config_store.path.lstat())==self.config_stamp)
            exact(self.config,{'actorFilesVersion','directory','expectedScriptSha256','expectedExecutableSha256','ownerToken','configHome'})
            need(type(self.config['actorFilesVersion']) is int and self.config['actorFilesVersion']==1
                and all(type(self.config[key]) is str and re.fullmatch('[0-9a-f]{64}',self.config[key])
                    for key in ('expectedScriptSha256','expectedExecutableSha256','ownerToken')))
            self.directory=Path(self.config['directory']);home=Path(self.config['configHome'])
            need(self.directory.is_absolute() and self.directory.resolve(strict=True)==self.directory
                and home.is_absolute() and home.resolve(strict=True)==home and home.is_dir())
            native=PrivateFeatureState(self.directory/SOURCE).read()
            native=validate_actor_source(native,native.get('processId'),self.config['expectedScriptSha256'],clock_ms())
            need(native['actorVersion']==2 and native['build']['cleanConfiguredSource'] is True)
            self.process=LinuxChatActorProcess(native['processId'],self.directory,self.config['expectedExecutableSha256'],self._owned)
            self.process_guard()
            self.binding=context(dict(sourceRevision=native['build']['compiledSourceRevision'],artifactSha256=self.process.sha256,
                processIdentity=self.process.process_identity,sessionId=native['instance'],generation=0,
                targetFingerprint=hashlib.sha256((str(self.directory)+'\0'+self.process.process_identity+'\0'+native['instance']+'\0'+self.process.sha256).encode()).hexdigest()))
            self.lock=ScriptSourceLock(files_store.path.with_name('script-sources.lock')) if source_lock is None else source_lock
            need(isinstance(self.lock,ScriptSourceLock) and self.lock.path==files_store.path.with_name('script-sources.lock'))
            self.files=ChatActorFiles(self.directory,files_store,self.binding,self.config['expectedScriptSha256'],
                self.process_guard,self.process.released,clock_ms=clock_ms,monotonic=monotonic,sleep=sleep)
            need(self.files.source==native and self.files.require_compiled_source()==self.binding['sourceRevision'])
            self.guard_callback=self.guard;self.guard()
        except Exception:
            self.close_host();raise NativeUIError('Original owned Chat peer is unavailable; no process or input is adopted') from None

    def config_guard(self):
        need(stamp(self.config_store.path.lstat())==self.config_stamp and self.config_store.read()==self.config
            and stamp(self.config_store.path.lstat())==self.config_stamp)
        return True

    def _owned(self,pid):
        self.config_guard();root=Path('/proc')/str(pid)
        need(root.stat().st_uid==os.geteuid())
        with (root/'environ').open('rb') as stream:raw=stream.read(4*1024*1024+1)
        need(len(raw)<=4*1024*1024);environment=raw.split(b'\0')
        result=(environment.count((OWNER_VARIABLE+'='+self.config['ownerToken']).encode())==1
            and environment.count(('XDG_CONFIG_HOME='+self.config['configHome']).encode())==1)
        self.config_guard();return result

    def process_guard(self):
        self.config_guard();need(self.process is not None and self.process.guard() is True);self.config_guard();return True

    def guard(self):
        try:
            self.process_guard();need(self.files is not None);self.files._check_source()
            need(context(self.binding)==self.files.binding
                and self.binding['sourceRevision']==self.files.require_compiled_source()
                and self.binding['artifactSha256']==self.config['expectedExecutableSha256']==self.process.sha256
                and self.binding['processIdentity']==self.process.process_identity
                and self.binding['sessionId']==self.files.source['instance'])
            return True
        except Exception:raise NativeUIError('Original Chat peer source ownership is unavailable') from None

    def reader(self):
        self.guard()
        def send(request):self.lock.assert_held();self.files.send(request)
        def read():self.lock.assert_held();return self.files.read()
        reader=NativeChatObservation(send,read,self.clock_ms,self.guard_callback,self.process.pid,
            monotonic=self.monotonic,sleep=self.sleep)
        # The dispatcher binds its final phase admission to the actual writer,
        # including the file owner's own last durable publication CAS.
        reader._chat_transport=self.files
        return reader

    def capture(self,run):
        reader=self.reader();owner=ChatCaptureOwner(PrivateFeatureState(self.files_store.path.with_name('chat-capture-owner.json')),
            self.binding,self.guard_callback)
        return OwnedChatCapture(reader,owner,run)

    def admit_capture(self,run):
        self.lock.assert_held();capture=self.capture(run);owned=capture.owner.begin(run)
        need(not owned['active']);value=capture.reader.perform(run,'inspect')
        need(value['chatVersion']==3 and not value['source']['scopePresent'] and not value['source']['retired'])
        capture.owner.admit(value);return capture

    def cache_lifetime(self,run):
        from adapters.chat_journey.cache_lifetime import ChatCacheLifetime
        self.lock.assert_held()
        return ChatCacheLifetime(self.capture(run),PrivateFeatureState(self.files_store.path.with_name('chat-cache-lifetime.json')),
            self.lock,monotonic=self.monotonic)

    def close_host(self):
        """Detach only owned host handles; never retire native state/journals."""
        if self.files is not None:self.files.detach();self.files=None
        if self.process is not None:self.process.close();self.process=None
