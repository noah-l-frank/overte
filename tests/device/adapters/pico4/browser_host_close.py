"""Actual original host descriptor closure after the Browser source archive."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os

from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.chat_journey.source_chunks import digest,json_digest
from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import parent_node,state
from adapters.script_journey.history import same

VERSION=1


class PicoBrowserHostClose:
    def __init__(self,plan):
        from adapters.pico4.browser_evidence_archive import PicoBrowserEvidenceArchive
        need(type(plan) is PicoBrowserEvidenceArchive and plan.completed and not plan.failed)
        self.plan=plan;self.primary=plan.primary;self.host=host_identity()
        self.store=PrivateFeatureState(plan.root/(plan.prefix+'host-close.json'))
        self.receipt_store=PrivateFeatureState(plan.root/(plan.prefix+'host-complete.json'))
        need(self.store.read() is None and self.receipt_store.read() is None)
        self.parent=parent_node(self.store);self.previous=None;self.previous_sha=json_digest(None)
        self.started=self.completed=self.failed=False;self.pairs=[];self.windows=[];self.journal_pairs=[]
        self.result=self.result_sha=self.receipt_raw=self.receipt_stamp=None

    def add(self,label,owner):
        if type(owner) is ClosedOriginalFile:
            need(not owner.failed and owner.active is None);self.windows.append(owner);return
        need(type(owner) is OriginalDescriptor and not owner.lost)
        if any(owner is previous for previous,_row in self.pairs):return
        need(not owner.closed);OriginalDescriptor.require(owner,owner.fd)
        for method in ('require','close'):
            need(getattr(getattr(owner,method),'__func__',None) is getattr(OriginalDescriptor,method))
        self.pairs.append((owner,dict(label=label,node=list(owner.node),fd=owner.fd,anchor=owner.anchor)))

    def admit(self):
        plan=self.plan;self.archive_receipt=plan.receipt()
        for prefix,catalog in (('archive',plan.catalog),('capture',plan.captures.catalog)):
            need(not catalog.failed and not catalog.uncertain)
            for path,owner in catalog.parents.items():self.add(prefix+'/parent/'+str(path),owner)
            for label,row in catalog.rows.items():self.add(prefix+'/'+label,row['owner'])
        for name,row in plan.archive.archived.items():self.add('immutable/'+name,row['owner'])
        self.add('immutable/root',plan.archive.root)
        process=plan.captures.returned.process
        from fixture.chat_observer_process import LinuxChatObserverProcess
        need(type(process) is LinuxChatObserverProcess)
        for method in ('require_absent','_absent','close'):
            need(getattr(getattr(process,method),'__func__',None) is getattr(LinuxChatObserverProcess,method))
        self.process=process;self.process_absence=process.require_absent()
        self.add('independent-observer/executable',process.fd_owner)
        self.add('independent-observer/entry',process.entry_owner)
        need(self.pairs and self.windows)
        self.directory_owner=plan.catalog.parents[plan.root]
        self.scope=dict(picoBrowserHostCloseVersion=VERSION,runId=self.primary.run,hostProcessIdentity=self.host,
            archiveSha256=self.archive_receipt['archive']['archiveSha256'],
            finalSha256=self.archive_receipt['archive']['finalSha256'],sourceArchiveSha256=digest(self.archive_receipt),
            commonSequenceSucceeded=self.archive_receipt['commonSequenceSucceeded'],
            processAbsence=deepcopy(self.process_absence),
            pairs=[deepcopy(row) for _owner,row in self.pairs],closedWindows=len(self.windows))
        self.scope_sha=json_digest(self.scope)

    def control(self):
        need(not self.failed and host_identity()==self.host and parent_node(self.store)==self.parent
            and json_digest(self.scope)==self.scope_sha and json_digest(self.previous)==self.previous_sha
            and same(self.store.read(),self.previous))

    def sync_parent(self):
        need(parent_node(self.store)==self.parent);owner=self.directory_owner;temporary=False
        if owner.closed:
            need(len(self.journal_pairs)<4)
            owner=OriginalDescriptor(self.plan.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.journal_pairs.append(owner);temporary=True
        try:
            OriginalDescriptor.require(owner,owner.fd);need(owner.node==tuple(self.parent[:2]))
            os.fsync(owner.fd);OriginalDescriptor.require(owner,owner.fd)
            need(parent_node(self.store)==self.parent)
        finally:
            if temporary:need(OriginalDescriptor.close(owner) and owner.closed and not owner.lost)

    def retire_sentry(self):
        plan=self.plan
        need(plan.sentry_value is not None and plan.sentry_value['phase']=='archived-awaiting-host'
            and parent_node(plan.sentry)==plan.sentry_parent)
        original=deepcopy(plan.sentry_value);plan.sentry.discard(original);plan.sentry_value=None
        need(len(self.journal_pairs)<5)
        owner=OriginalDescriptor(plan.sentry.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.journal_pairs.append(owner)
        try:
            OriginalDescriptor.require(owner,owner.fd);need(owner.node==tuple(plan.sentry_parent[:2]))
            os.fsync(owner.fd);need(parent_node(plan.sentry)==plan.sentry_parent)
        finally:need(OriginalDescriptor.close(owner) and owner.closed and not owner.lost)

    def save(self,phase):
        self.control();value={**self.scope,'phase':phase}
        self.store.write(value,self.previous);self.sync_parent();need(same(self.store.read(),value))
        self.previous=deepcopy(value);self.previous_sha=json_digest(value);self.control()

    def closed(self):
        need(all(owner.closed and not owner.lost and owner.fd==owner.anchor==-1 for owner,_row in self.pairs)
            and all(owner.active is None and not owner.failed for owner in self.windows)
            and all(owner.closed and not owner.lost and owner.fd==owner.anchor==-1 for owner in self.journal_pairs))

    def run(self):
        need(not self.started and not self.failed);self.started=True
        try:
            self.admit();self.save('close-issued');self.plan.receipt()
            with self.primary.lock.held(),self.primary.adapter.existing_input_session(self.primary.selector):
                self.plan.source.final(self.plan.source.last)
            self.plan.source.control();self.plan.source.clocks(self.plan.source.epochs)
            for owner,row in self.pairs:
                need(owner.fd==row['fd'] and owner.anchor==row['anchor'] and owner.node==tuple(row['node']))
                need(OriginalDescriptor.close(owner))
            from fixture.chat_observer_process import LinuxChatObserverProcess
            need(LinuxChatObserverProcess.close(self.process) and self.process.fd==-1)
            self.closed();self.save('closed');self.closed();self.plan.receipt()
            result=dict(picoBrowserHostCloseVersion=VERSION,runId=self.primary.run,hostProcessIdentity=self.host,
                archiveSha256=self.scope['archiveSha256'],finalSha256=self.scope['finalSha256'],
                sourceArchiveSha256=self.scope['sourceArchiveSha256'],closedPairs=len(self.pairs),closedWindows=len(self.windows),
                commonSequenceSucceeded=self.scope['commonSequenceSucceeded'],hostReleased=True,
                fullFeatureRecipe=False,deviceAcceptance=False)
            self.receipt_store.write(result,None);observed,self.receipt_raw,self.receipt_stamp=state(self.receipt_store)
            need(same(observed,result));self.sync_parent();self.closed();self.control()
            self.store.discard(self.previous);self.sync_parent();self.closed()
            self.retire_sentry();self.closed()
            self.plan.receipt();self.plan.source.clocks(self.plan.source.epochs)
            LinuxChatObserverProcess._absent(self.process)
            need(self.store.read() is None and parent_node(self.store)==self.parent)
            self.result=deepcopy(result);self.result_sha=json_digest(result);self.completed=True;self.plan.host_closed=True
            return deepcopy(result)
        except BaseException:
            self.failed=True
            if self.previous is not None and self.store.read() is None:
                failure={**self.previous,'phase':'final-unavailable'}
                self.store.write(failure,None)
            if self.plan.sentry.read() is None:
                failed=dict(picoBrowserArchiveOwnershipVersion=VERSION,runId=self.primary.run,
                    binding=deepcopy(self.plan.source.owner['binding']),ownerToken=self.plan.source.owner['ownerToken'],
                    artifactRoot=str(self.plan.root),archiveDirectory=self.plan.directory.name,phase='final-unavailable')
                self.plan.sentry.write(failed,None);self.plan.sentry_value=failed
            raise NativeUIError('Original Browser host closure is unresolved; no closed receipt is admitted') from None

    def receipt(self):
        need(self.completed and not self.failed and json_digest(self.result)==self.result_sha)
        try:
            self.closed();need(self.store.read() is None and host_identity()==self.host
                and self.plan.sentry.read() is None and self.plan.sentry_value is None
                and parent_node(self.receipt_store)==self.parent
                and state(self.receipt_store)==(self.result,self.receipt_raw,self.receipt_stamp))
            self.plan.receipt();return deepcopy(self.result)
        except BaseException:self.failed=True;raise
