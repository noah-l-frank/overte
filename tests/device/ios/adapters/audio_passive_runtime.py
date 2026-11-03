"""Explicit Actor-only passive capture on an existing, held canonical SDK.

The SDK parent ledger owns exact artifact child births before native Start.
No normal/public feature entrypoint selects this runtime or bypasses existing
Audio cleanup guards. Reopening first decodes original files without a source.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import os,stat,time
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.audio_passive_capture_source import FILE,MAX_ORIGINAL,hex32
from ios.adapters.audio_passive_owner import IOSAudioPassiveOwner
from ios.adapters.audio_runtime import IOSAudioRuntime
from ios.adapters.audio_session_owners import owners_absent,register_scope
from ios.adapters.emote_original_lease import EmoteOriginalLease


def identity(root):
    need(root.is_absolute() and root.resolve(strict=True)==root)
    value=root.lstat();need(stat.S_ISDIR(value.st_mode) and value.st_uid==os.geteuid() and stat.S_IMODE(value.st_mode)==0o700)
    return dict(device=value.st_dev,inode=value.st_ino)


def fsync_directory(root):
    fd=os.open(root,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
    try:os.fsync(fd)
    finally:os.close(fd)


class PassiveSDKLedger:
    """Pure typed historical admission, not permission to query a new SDK."""
    def __init__(self,runtime,selector,run,lease,root,client,lock):
        need(isinstance(runtime,IOSAudioPassiveRuntime) and hex32(run) and hex32(lease) and isinstance(client,Client) and isinstance(lock,ScriptSourceLock))
        self.runtime,self.selector,self.run,self.root,self.client,self.lock=runtime,selector,run,Path(root),client,lock
        self.selected_lease=lease
        self.sdkroot=runtime.state_path(selector).parent
        need(lock.path==self.sdkroot/'script-feature-sources.lock' and self.root!=self.sdkroot)
        lock.assert_held();self.root_identity=identity(self.root);identity(self.sdkroot)
        self.store=PrivateFeatureState(self.sdkroot/'ios-audio-passive-ledger.json')
        self.scope=PrivateFeatureState(self.sdkroot/'ios-audio-scope.json');self.previous=self.store.read();self.archives={};self.oldleases=[]
        self.admit()

    def envelope(self):
        return dict(iosAudioPassiveSDKLedgerVersion=1,binding=deepcopy(self.binding),runId=self.run,role='actor',
            sdkStateRoot=str(self.sdkroot),artifactRoot=str(self.root),rootIdentity=self.root_identity,
            fixtureUrl=self.client.url+'/runs/'+self.run+'/',leases=deepcopy(self.rows))

    def admit(self):
        self.lock.assert_held();need(identity(self.root)==self.root_identity)
        if self.previous is None:
            # A lost scope-only commit remains explicit duty. No orphan file or
            # directory may be inferred owned merely from its familiar name.
            need(owners_absent(self.runtime.adapter,self.selector) and not list(self.root.iterdir()))
            self.binding=None;self.rows=[];return
        value=self.previous;exact(value,{'iosAudioPassiveSDKLedgerVersion','binding','runId','role','sdkStateRoot',
            'artifactRoot','rootIdentity','fixtureUrl','leases'})
        self.binding=deepcopy(context(value['binding']));self.rows=deepcopy(value['leases'])
        need(type(value['iosAudioPassiveSDKLedgerVersion']) is int and value['iosAudioPassiveSDKLedgerVersion']==1
            and same(value,self.envelope()) and type(self.rows) is list and len(self.rows)<=16)
        expected_scope=dict(iosAudioScopeVersion=1,binding=self.binding,runId=self.run,artifactRoot=str(self.root))
        need(same(self.scope.read(),expected_scope))
        audio={path for path in self.sdkroot.iterdir() if path.name.startswith('ios-audio-')}
        need(audio=={self.scope.path,self.store.path})
        roots=set();ids=set()
        for row in self.rows:
            exact(row,{'leaseId','phase','rootIdentity'});lease=row['leaseId']
            need(hex32(lease) and lease not in ids and row['phase'] in ('planned','opened'));ids.add(lease)
            child=self.root/('ios-audio-passive-'+lease);roots.add(child)
            if row['phase']=='planned':
                need(lease==self.selected_lease)
                need(row['rootIdentity'] is None and not child.exists());continue
            exact(row['rootIdentity'],{'device','inode'})
            need(integer(row['rootIdentity']['device'],0) and integer(row['rootIdentity']['inode'],1) and identity(child)==row['rootIdentity'])
            store=PrivateFeatureState(child/'ios-audio-passive-owner.json')
            if store.read() is None:need(lease==self.selected_lease and not list(child.iterdir()))
            else:
                archive=IOSAudioPassiveOwner.archive(store,child,self.binding,self.run,lease,self.lock,self.client.url+'/runs/'+self.run+'/')
                if lease!=self.selected_lease:
                    archive.retired();self.oldleases.append(EmoteOriginalLease(child,[]))
                self.archives[lease]=archive
        need(set(self.root.iterdir())=={path for path in roots if path.exists()})

    def save(self):
        self.lock.assert_held();need(identity(self.root)==self.root_identity and same(self.store.read(),self.previous))
        value=self.envelope();self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def select(self,lease,binding):
        need(hex32(lease));context(binding);self.lock.assert_held()
        if self.binding is None:
            self.binding=deepcopy(binding);register_scope(self.runtime.adapter,self.selector,self.binding,self.run,self.root)
            self.save()
        else:need(same(self.binding,binding))
        for key,archive in self.archives.items():
            if key!=lease:archive.retired()
        rows=[row for row in self.rows if row['leaseId']==lease];need(len(rows)<=1)
        if rows:row=rows[0]
        else:
            need(len(self.rows)<16 and all(item['phase']=='opened' for item in self.rows))
            row=dict(leaseId=lease,phase='planned',rootIdentity=None);self.rows.append(row);self.save()
        child=self.root/('ios-audio-passive-'+lease)
        if row['phase']=='planned':
            # This exact predeclared path is born before any native capture.
            # A lost mkdir/birth return leaves planned+existing fail-closed.
            need(not child.exists());os.mkdir(child,0o700);fsync_directory(self.root)
            row.update(phase='opened',rootIdentity=identity(child));self.save()
        need(identity(child)==row['rootIdentity']);return child

    def guard(self):
        self.lock.assert_held();need(identity(self.root)==self.root_identity and same(self.store.read(),self.previous))
        need(same(self.scope.read(),dict(iosAudioScopeVersion=1,binding=self.binding,runId=self.run,artifactRoot=str(self.root))))
        need({path for path in self.sdkroot.iterdir() if path.name.startswith('ios-audio-')}=={self.scope.path,self.store.path})
        need(set(self.root.iterdir())=={self.root/('ios-audio-passive-'+row['leaseId']) for row in self.rows if row['phase']=='opened'})
        for row in self.rows:
            need(row['phase']=='opened' and identity(self.root/('ios-audio-passive-'+row['leaseId']))==row['rootIdentity'])
        for old in self.oldleases:old.guard()
        return True


class IOSAudioPassiveRuntime(IOSAudioRuntime):
    @contextmanager
    def passive_owner(self,selector,run,lease,artifact_root,client,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        """Private explicit Actor selection; never creates SDK/mic input."""
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        with lock.held():
            ledger=PassiveSDKLedger(self,selector,run,lease,artifact_root,client,lock)
            # Full pure historical decoding precedes the first fresh source.
            # Installed/SDK continuity still executes via existing factories.
            source=self._sources(selector);need(source['check']() is not False)
            child=ledger.select(lease,source['binding']);ledger.guard()
            original=source['check']
            def check():ledger.guard();need(original() is not False);ledger.guard();return True
            observer=source['observer'];remote=observer.remote.rsplit('/',1)[0]+'/'+FILE
            for transport in (observer,getattr(source['clock_source'].send,'__self__',None)):
                need(transport is not None);before=getattr(transport,'before_send',None)
                def final(before=before):
                    check()
                    if before is not None:need(before() is not False)
                    check()
                transport.before_send=final
            owner=IOSAudioPassiveOwner(PrivateFeatureState(child/'ios-audio-passive-owner.json'),child,source['binding'],run,lease,lock,check,
                native=source['clock_source'],transport=dict(send=observer.send,read=lambda:observer.original(remote=remote,limit=MAX_ORIGINAL)),
                phase=PhaseFixtureReader(client,run,'audio',epoch_ms=epoch_ms,monotonic=monotonic),
                epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
            with self.existing_input_session(selector):
                yield owner
                check()
