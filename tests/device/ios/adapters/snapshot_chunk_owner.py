"""Durable one-query original byte chunk using the existing Snapshot owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import uuid
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,integer,need
from ios.adapters import snapshot_chunks as chunks
from ios.adapters.snapshot_manifest import SnapshotManifest,FILE


def original(frame,pid):
    exact(frame,{'query','packet','clockJoin'});chunks.packet(frame['packet'],frame['query'],pid)
    validate_join(frame['clockJoin'],dict(chunk=frame['packet']))
    need(frame['clockJoin']['nativeBefore']['processId']==pid);return frame


class SnapshotChunk(SnapshotManifest):
    _name='chunk'
    _owner_key='iosSnapshotChunkOwnerVersion'
    _namespace='snapshot-chunk'
    _schema_prefix='snapshotChunk'
    _max_index=1024
    _file=FILE
    _limit=chunks.LIMIT
    _source_name='chunk'
    _query=staticmethod(chunks.command)
    _packet=staticmethod(chunks.packet)
    _frame=staticmethod(original)

    def reserve(self,mode):need(False)

    def reserve_original(self,manifest,basename,offset):
        """Select a real original row; never accept requested file contents."""
        need(isinstance(manifest,SnapshotManifest) and not isinstance(manifest,SnapshotChunk)
            and manifest.binding==self.binding and manifest.run==self.run and manifest.role==self.role
            and manifest.store.path.parent==self.store.path.parent and manifest.lock.path==self.lock.path)
        frame=manifest.historical();rows=[row for row in frame['packet']['files'] if row['name']==basename]
        need(len(rows)==1 and integer(offset,0,rows[0]['size']) and offset%chunks.CHUNK_BYTES==0
            and (offset<rows[0]['size'] or offset==rows[0]['size']==0))
        return self._reserve(chunks.command(dict(schemaVersion=2,commandId='ios-'+uuid.uuid4().hex,action='snapshot-files',operation='read',
            prefix=frame['query']['prefix'],name=rows[0]['name'],revision=rows[0]['revision'],offset=offset,chunkBytes=chunks.CHUNK_BYTES)))
