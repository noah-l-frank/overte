"""Once-only original host-handle finalization after sealed Chat evidence.

This reports only this host's captured descriptor pairs/windows. Product,
actor and process release remain the independent originals in the archive.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os

from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.chat_journey.evidence_archive import ChatEvidenceArchive
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.chat_journey.source_chunks import digest
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.chat_archive import PicoChatArchivePlan
from adapters.pico4.chat_restart_io import PicoChatRestartIO
from adapters.script_journey.history import same
from adapters.host_process_identity import host_identity
from openxr_input.binding_transfer import OriginalBindingTransfer

VERSION=1


class PicoChatHostClose:
    """Unknown intent/owner is retained; no detach adoption or retry exists."""
    def __init__(self,parent,store):
        need(isinstance(store,PrivateFeatureState) and store.read() is None and not parent.failed)
        self.parent,self.store=parent,store;self.previous=None;self.started=self.complete=False
        plan=parent.archive_plan;peer=parent.peer;io=parent.restart_io
        need(type(plan) is PicoChatArchivePlan and plan.parent is parent and type(plan.archive) is ChatEvidenceArchive
            and plan.archive.complete and plan.archive.version==4
            and type(peer) is OwnedChatPeer and type(io) is PicoChatRestartIO and type(io.transfer) is OriginalBindingTransfer)
        self.archive=plan.archive;self.pairs=[];self.windows=[];self.journal_pairs=[]
        need(store.path.parent==self.archive.directory.parent and store.path.parent in self.archive.catalog.parents)
        self.directory_owner=self.archive.catalog.parents[store.path.parent]
        self.directory_owner.require(self.directory_owner.fd);self.parent_node=self.directory_owner.node
        need(self.archive.metadata.get('picoChatArchivePlanVersion')==4
            and self.archive.metadata.get('runId')==parent.source.run
            and same(self.archive.metadata.get('oldBinding'),parent.binding)
            and same(self.archive.metadata.get('newBinding'),parent.application_close.new_binding))
        for owner,method,expected in ((plan,'close_host',PicoChatArchivePlan.close_host),
            (self.archive,'close_host',ChatEvidenceArchive.close_host),(peer,'close_host',OwnedChatPeer.close_host),
            (io,'close_host',PicoChatRestartIO.close_host),(io.transfer,'close_host',OriginalBindingTransfer.close_host)):
            need(getattr(getattr(owner,method),'__func__',None) is expected)
        for label,owner in self.archive.catalog.parents.items():self.add('catalog-parent/'+str(label),owner)
        for label,row in self.archive.catalog.rows.items():self.add('catalog/'+label,row['owner'])
        for label,row in self.archive.archived.items():self.add('archive/'+label,row['owner'])
        need(not self.archive.catalog.uncertain);self.add('archive-root',self.archive.root)
        need(peer.files is not None and peer.process is not None)
        for name in ('files','retirement_files','process'):
            owner=getattr(peer,name)
            if owner is not None:self.add('peer/'+name,owner.fd_owner)
        for name in ('old','new','lock_owner','root'):
            owner=getattr(io.transfer,name)
            if owner is not None:self.add('session/'+name,owner)
        need(self.pairs and self.windows)
        self.host=host_identity()
        self.scope=dict(picoChatHostCloseVersion=VERSION,sourceScope='original-host-chat-handles',
            runId=parent.source.run,oldBinding=deepcopy(parent.binding),newBinding=deepcopy(parent.application_close.new_binding),
            archiveDirectory=self.archive.directory.name,archiveSha256=self.archive.manifest['sha256'],
            finalSha256=self.archive.receipt['sha256'],hostProcessIdentity=self.host,
            parentNode=list(self.parent_node),pairs=deepcopy([row for _owner,row in self.pairs]),closedWindows=len(self.windows))
        self.scope_digest=digest(self.scope)

    def add(self,label,owner):
        if type(owner) is ClosedOriginalFile:
            need(not owner.failed and owner.active is None);self.windows.append(owner);return
        need(type(owner) is OriginalDescriptor and not owner.lost)
        if any(owner is original for original,_row in self.pairs):return
        if owner.closed:need(owner.fd==owner.anchor==-1)
        else:owner.require(owner.fd)
        self.pairs.append((owner,dict(label=label,node=list(owner.node),fd=owner.fd,anchor=owner.anchor,alreadyClosed=owner.closed)))

    def save(self,phase):
        self.parent_current()
        need(digest(self.scope)==self.scope_digest and host_identity()==self.host and same(self.store.read(),self.previous))
        value={**self.scope,'phase':phase};self.store.write(value,self.previous)
        self.sync_parent();self.parent_current()
        need(digest(self.scope)==self.scope_digest and same(self.store.read(),value));self.previous=deepcopy(value)

    def parent_current(self):
        self.store._parent();info=self.store.path.parent.lstat()
        need((info.st_dev,info.st_ino)==self.parent_node)

    def sync_parent(self):
        """Durable metadata, with bounded windows of the SAME original node.

        These windows carry no target/source facts. A lost alias is retained,
        never replaced or closed as though its historical OFD had survived.
        """
        self.parent_current();owner=self.directory_owner;temporary=False
        if owner.closed:
            need(len(self.journal_pairs)<3)
            owner=OriginalDescriptor(self.store.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.journal_pairs.append(owner);temporary=True
        try:
            owner.require(owner.fd);need(owner.node==self.parent_node)
            os.fsync(owner.fd);owner.require(owner.fd);self.parent_current()
        finally:
            if temporary:need(OriginalDescriptor.close(owner) and owner.closed and owner.fd==owner.anchor==-1)

    def run(self):
        need(not self.started);self.started=True
        self.save('detach-issued')
        # This complete original-byte pass follows the durable host intent.
        # It neither refreshes nor relabels the archived native final packet.
        self.archive.verify_archive();okay=True
        for owner,row in self.pairs:
            need(not owner.lost and owner.node==tuple(row['node']) and owner.fd==row['fd'] and owner.anchor==row['anchor']
                and owner.closed is row['alreadyClosed'])
            # Call the actual kernel-owning implementation, never a supplied
            # close ACK. Wrappers are detached only after these real closes.
            okay=OriginalDescriptor.close(owner) and okay
        okay=all(owner.closed and not owner.lost and owner.fd==owner.anchor==-1 for owner,_row in self.pairs) and okay
        if not okay:self.save('unresolved');need(False)
        from adapters.pico4.chat_composition import PicoChatComposition
        okay=PicoChatComposition.detach(self.parent) is True and okay
        okay=all(owner.closed and not owner.lost and owner.fd==owner.anchor==-1 for owner,_row in self.pairs) and okay
        okay=all(not owner.failed and owner.active is None for owner in self.windows) and okay
        if not okay:self.save('unresolved');need(False)
        self.save('closed');result=dict(picoChatHostCloseVersion=VERSION,sourceScope=self.scope['sourceScope'],
            hostProcessIdentity=self.host,archiveSha256=self.scope['archiveSha256'],finalSha256=self.scope['finalSha256'],
            ownershipSha256=self.scope_digest,closedPairs=len(self.pairs),closedWindows=len(self.windows))
        try:
            self.parent_current()
            self.store.discard(self.previous)
            self.sync_parent()
            self.parent_current();need(self.store.read() is None and host_identity()==self.host)
        except Exception:
            self.parent_current()
            if self.store.read() is None:
                need(digest(self.scope)==self.scope_digest)
                failed={**self.scope,'phase':'final-unavailable'}
                self.store.write(failed,None);self.sync_parent();self.previous=deepcopy(failed)
            raise
        need(all(owner.closed and not owner.lost and owner.fd==owner.anchor==-1 for owner in self.journal_pairs))
        result['closedJournalWindows']=len(self.journal_pairs)
        self.complete=True;return result
