"""Existing immutable original archive on the warm Browser ownership graph.

Final source observations stay original evidence in the private artifact root.
This transaction does not detach host descriptors or claim a successful recipe.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os

from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,ChatEvidenceArchive,completed_archive
from adapters.chat_journey.source_chunks import digest,json_digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import state,parent_node
from adapters.pico4.browser_archive_source import PicoBrowserArchiveReleaseSource,PicoBrowserArchiveUnlinkFence
from adapters.pico4.browser_archive_context import BrowserArchiveContext,read_context
from adapters.script_journey.history import same,pack

VERSION=2
DIRECTORY_VERSION=3
OWNERSHIP_VERSION=1


def namespace_names(parent,prefix):
    # Scan every entry, including directories and symlinks. Within this exact
    # parent, names preserve the same membership as constructing each Path.
    with os.scandir(parent) as entries:
        return {entry.name for entry in entries if entry.name.startswith(prefix)}


def metadata_pngs(metadata,context):
    """Read the complete historical inventory through its versioned reference."""
    json_digest(metadata)
    version=metadata.get('picoBrowserEvidenceArchiveVersion')
    need(type(version) is int and version in (1,2,DIRECTORY_VERSION))
    if version==1:
        pngs=metadata['pngs']
    else:
        json_digest(context);need(digest(context)==metadata['contextSha256'])
        pngs=context['pngs']
        need(type(pngs) is list and type(metadata['pngCount']) is int and len(pngs)==metadata['pngCount']
            and json_digest(pngs)==metadata['pngsSha256'])
    need(type(pngs) is list and bool(pngs));return deepcopy(pngs)


class PicoBrowserEvidenceArchive:
    def __init__(self,primary,captures,*,directory_retirement=False):
        from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
        from adapters.pico4.browser_remote_capture_retirement import PicoBrowserRemoteCaptureRetirement
        need(type(primary) is PicoTabletWebFeature and primary.role=='primary'
            and type(captures) is PicoBrowserRemoteCaptureRetirement and captures.primary is primary
            and captures.completed and not captures.failed and primary.archive_release is None)
        self.primary,self.captures=primary,captures
        need(type(directory_retirement) is bool)
        self.version=DIRECTORY_VERSION if directory_retirement else VERSION
        self.directory_retirement=directory_retirement;self.namespace_group=None
        self.started=self.completed=self.failed=False;self.archive=None;self.result=None;self.result_sha=None
        self.catalog=ChatArchiveCatalog(hold_files=False);self.tail=None;self.host_closed=False
        self.root=primary.artifact_root;self.prefix='tablet-web-'+primary.run+'-'
        self.marker=PrivateFeatureState(self.root/(self.prefix+'archive-intent.json'))
        self.context=PrivateFeatureState(self.root/(self.prefix+'archive-context.json'))
        self.store=PrivateFeatureState(self.root/(self.prefix+'archive-complete.json'))
        self.sentry=PrivateFeatureState(primary.store.path.with_name('pico-tablet-web-archive-owner.json'))
        if directory_retirement:
            from adapters.pico4.tablet_web_binding import archive_sentry_prefix
            prefix=archive_sentry_prefix(primary.selector)
            need(primary.store.path.parent.name==prefix.removesuffix('-archive-owner-'))
            self.sentry=PrivateFeatureState(primary.store.path.parent.parent/(prefix+primary.run+'.json'))
        self.sentry_value=None;self.sentry_parent=parent_node(self.sentry)
        self.directory=self.root/(self.prefix+'source-archive')
        need(all(store.read() is None for store in (self.marker,self.context,self.store,self.sentry)) and not self.directory.exists())
        self.parent=parent_node(self.store)
        self.source=None
        self.namespace=self._sealed_namespace=None
        self.namespace_rows=self._sealed_namespace_rows=None

    def freeze_namespace(self):
        """Pin only explicit already-admitted paths; never discover originals."""
        need(self.namespace is None and self.namespace_rows is None and self.archive is None
            and type(self.catalog) is ChatArchiveCatalog and not self.catalog.hold_files and self.catalog.rows)
        state_parent=self.primary.store.path.parent;root=self.root;prefix=self.prefix
        rows=tuple((label,row,row['store'],row['store'].path) for label,row in self.catalog.rows.items())
        need(all(row['store'] is store and row['owner'].path is path for _label,row,store,path in rows))
        paths=frozenset(path for _label,_row,_store,path in rows)
        state_paths=frozenset(path for path in paths if path.parent==state_parent)
        artifact_paths=frozenset(path for path in paths if path.parent==root)
        need(len(paths)==len(rows) and state_parent!=root and paths==state_paths|artifact_paths
            and all(path.name.startswith('pico-tablet-web-') for path in state_paths)
            and all(path.name.startswith(prefix) for path in artifact_paths)
            and prefix=='tablet-web-'+self.primary.run+'-' and self.primary.artifact_root==root)
        self.namespace=self._sealed_namespace=(self.primary.store.path,state_parent,root,prefix,self.primary.run,
            paths,state_paths,artifact_paths)
        self.namespace_rows=self._sealed_namespace_rows=rows
        self.namespace_control()

    def namespace_control(self,remaining=None):
        """Current mutable scope pins, independent of current namespace scans."""
        need(self.namespace is self._sealed_namespace and type(self.namespace) is tuple and len(self.namespace)==8
            and self.namespace_rows is self._sealed_namespace_rows and type(self.namespace_rows) is tuple
            and len(self.namespace_rows)==len(self.catalog.rows))
        primary_path,state_parent,root,prefix,run,paths,state_paths,artifact_paths=self.namespace
        need(all(type(group) is frozenset for group in (paths,state_paths,artifact_paths))
            and self.primary.store.path==primary_path and self.primary.store.path.parent==state_parent
            and self.root==root and self.primary.artifact_root==root and self.prefix==prefix
            and self.primary.run==run and prefix=='tablet-web-'+run+'-')
        for (label,row),(original_label,original_row,store,path) in zip(self.catalog.rows.items(),self.namespace_rows):
            need(label==original_label and row is original_row and row['store'] is store and store.path is path)
        if remaining is not None:
            need(type(remaining) is set and remaining<=paths)
        return state_paths,artifact_paths

    def admit(self):
        primary,captures=self.primary,self.captures
        # Exact original receipts are admitted before any new artifact marker.
        self.source=primary.archive_release_source()
        need(type(self.source) is PicoBrowserArchiveReleaseSource)
        self.sentry_value=dict(picoBrowserArchiveOwnershipVersion=OWNERSHIP_VERSION,runId=primary.run,
            binding=deepcopy(self.source.owner['binding']),ownerToken=self.source.owner['ownerToken'],
            artifactRoot=str(self.root),archiveDirectory=self.directory.name,phase='archiving')
        self.sentry.write(self.sentry_value,None)
        for label,row in captures.catalog.rows.items():
            captures.catalog.verify(row);self.catalog.add(label,row['store'],row['expected'])
        self.catalog.add('primary/'+captures.store.path.name,captures.store,captures.previous)
        captures.chunks.verify()
        for index in range(len(captures.chunks.identities)):
            store=captures.chunks.store(index);self.catalog.add('primary/'+store.path.name,store,store.read())
        data=dict(source=self.source.admission(),pngs=deepcopy(captures.pngs));json_digest(data)
        self.context_owner=BrowserArchiveContext(self.context,primary.run,data)
        self.context_value=deepcopy(self.context_owner.previous);self.context_stamp=self.context_owner.stamp
        common=primary.cleanup_consumption.receipt()
        self.metadata=dict(picoBrowserEvidenceArchiveVersion=self.version,runId=primary.run,fixtureUrl=primary.fixture_url,
            binding=deepcopy(self.source.owner['binding']),ownerToken=self.source.owner['ownerToken'],
            commonSequenceSucceeded=common['header']['sequenceSucceeded'],contextSha256=digest(data),
            sourceMarker=self.source.store.path.name,contextMarker=self.context.path.name,
            capturesSha256=digest(self.source.capture_receipt),actorReturnSha256=digest(self.source.return_receipt),
            pngsSha256=json_digest(captures.pngs),pngCount=len(captures.pngs))
        need(same(metadata_pngs(self.metadata,data),captures.pngs))
        self.freeze_namespace();self.source.bind_namespace_guard(self.namespace_control)
        self.fence=PicoBrowserArchiveUnlinkFence(self.source)
        groups=()
        if self.directory_retirement:
            from adapters.chat_journey.directory_retirement import OriginalDirectoryRetirement
            self.namespace_group=OriginalDirectoryRetirement(self.catalog,primary.store.path.parent,
                self.root/(self.prefix+'state-originals'))
            groups=(self.namespace_group,)
        self.archive=ChatEvidenceArchive(self.catalog,self.directory,self.marker,self.metadata,self.source,self.inventory,
            unlink_fence=self.fence,indexed_verify=True,directory_retirements=groups)

    def pngs(self):
        original_sha,windows=self.captures.original_png_windows()
        need(original_sha==self.metadata['pngsSha256'] and len(windows)==self.metadata['pngCount'])
        directory=self.catalog.parents[self.root]
        if directory.closed:
            # Final host closure has deliberately retired this original pair.
            # The existing independent full-byte reader remains available.
            for value,stamp in windows:self.primary._original_image_bytes(value,expected=stamp)
        else:
            self.catalog.verify_parent(self.root)
            for value,stamp in windows:
                self.primary._original_image_bytes(value,expected=stamp,directory=directory)
            self.catalog.verify_parent(self.root)

    def inventory(self,remaining):
        """Actual complete namespace scans reject extra or missing originals."""
        p=self.primary
        state_paths,artifact_paths=self.namespace_control(remaining)
        group=getattr(self,'namespace_group',None)
        if group is not None and group.moved:
            group.verify(historical=True);actual=set()
        else:actual=namespace_names(self.namespace[1],'pico-tablet-web-')
        expected_state=remaining&state_paths
        if self.sentry.path.parent==self.namespace[1] and self.sentry.path.exists():expected_state.add(self.sentry.path)
        need(actual=={path.name for path in expected_state} and same(self.sentry.read(),self.sentry_value)
            and parent_node(self.sentry)==self.sentry_parent)
        expected=remaining&artifact_paths
        expected.update({self.context.path,self.source.store.path})
        expected.update(store.path for store in self.context_owner.stores())
        expected.update(self.source.chunks.store(index).path for index in range(len(self.source.chunks.identities)))
        if not self.source.store.path.exists():expected.remove(self.source.store.path)
        if self.marker.path.exists():expected.add(self.marker.path)
        if self.store.path.exists():expected.add(self.store.path)
        host=getattr(p,'browser_host_close',None)
        if host is not None:
            from adapters.pico4.browser_host_close import PicoBrowserHostClose
            need(type(host) is PicoBrowserHostClose and host.plan is self)
            expected.update(store.path for store in (host.store,host.receipt_store) if store.path.exists())
        if self.directory.exists():expected.add(self.directory)
        if group is not None and group.destination.exists():expected.add(group.destination)
        actual=namespace_names(self.root,self.prefix)
        need(actual=={path.name for path in expected} and same(self.context.read(),self.context_value)
            and state(self.context)[2]==self.context_stamp and parent_node(self.store)==self.parent)
        self.pngs()

    def source_tail(self):
        """Only exact already issued source files; never directory adoption."""
        self.source.control();self.source.chunks.verify()
        rows=[]
        for store in (*self.context_owner.stores(),self.source.store,*[self.source.chunks.store(index)
                for index in range(len(self.source.chunks.identities))]):
            value,raw,physical=state(store)
            rows.append(dict(name=store.path.name,sha256=hashlib.sha256(raw).hexdigest(),stamp=physical))
        return rows

    def run(self):
        need(not self.started and not self.failed);self.started=True;p=self.primary
        try:
            self.admit()
            with p.lock.held(),p.adapter.existing_input_session(p.selector):
                result=self.archive.retire();self.source.final(self.source.last)
                self.tail=self.source_tail();self.source.frozen=True
                value=dict(picoBrowserEvidenceArchiveVersion=self.version,runId=p.run,phase='complete',
                    qualification='original-browser-source-archive-only',commonSequenceSucceeded=self.metadata['commonSequenceSucceeded'],
                    archive=result,originalSourceTail=pack(self.tail),contextSha256=self.metadata['contextSha256'],
                    hostReleased=False,fullFeatureRecipe=False,deviceAcceptance=False)
                self.store.write(value,None);self.original,self.original_raw,self.original_stamp=state(self.store)
                need(same(value,self.original));self.inventory(set());self.archive.verify_archive()
                self.source.final(self.source.last);candidate=deepcopy(value)
                sentry={**self.sentry_value,'phase':'archived-awaiting-host'}
                self.sentry.write(sentry,self.sentry_value);self.sentry_value=sentry
            # Keep the final original product age through actual lock exit.
            self.source.control();self.source.clocks(self.source.epochs);self.inventory(set())
            self.result=candidate;self.result_sha=json_digest(candidate);self.completed=True;return candidate
        except BaseException:
            self.failed=True
            raise NativeUIError('Original Browser source archive is unresolved; originals or immutable copies remain') from None

    def receipt(self):
        need(self.completed and not self.failed and json_digest(self.result)==self.result_sha)
        try:
            need(state(self.store)==(self.original,self.original_raw,self.original_stamp))
            proof=completed_archive(self.directory)
            need(same(proof['metadata'],self.metadata) and proof['archiveSha256']==self.result['archive']['archiveSha256']
                and proof['finalSha256']==self.result['archive']['finalSha256'])
            need(same(metadata_pngs(proof['metadata'],read_context(self.context,self.primary.run)),self.captures.pngs))
            need(self.source_tail()==self.tail);self.inventory(set());return deepcopy(self.result)
        except BaseException:self.failed=True;raise
