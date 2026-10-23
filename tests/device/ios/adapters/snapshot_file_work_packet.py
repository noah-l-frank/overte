"""Bounded original file-work packets with private segmented raw ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import decode,exact,need
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_packet_segments import OriginalPacketSegments
from adapters.script_feature.history import canonical,pack,unpack,same
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket,original,qualified
from ios.adapters import snapshot_file_work as source
import hashlib
import time


class FileWorkSegments(OriginalPacketSegments):PROFILE='snapshot-file-work'


class Frames:
    """Keep the ordinary immutable frame store's write/read contract intact."""
    def __init__(self,owner,live):
        self.owner=owner
        self.store=OriginalFrameStore(owner.store.path.parent,owner.binding,owner.run,owner.role,
            owner.guard if live else lambda:True,owner.storage if live else lambda *_:need(False),
            namespace=owner._namespace,schema_prefix=owner._schema)
    def __getattr__(self,key):return getattr(self.store,key)
    def read(self,reference):
        value=self.store.read(reference);exact(value,{'query','rawParts','acquisition'})
        owner=self.owner;owner.parent(value['rawParts'],value['query'])
        raw=owner.parts().read(value['rawParts']).decode('utf-8');packet=decode(raw,limit=owner._source.LIMIT)
        frame=dict(query=value['query'],raw=raw,packet=packet,acquisition=value['acquisition'])
        original(frame,owner.pid,owner._kind);return frame
    def write(self,index,frame):
        owner=self.owner;original(frame,owner.pid,owner._kind);parent=owner.state['rawParts']
        owner.parent(parent,frame['query']);need(owner.parts().read(parent).decode('utf-8')==frame['raw'])
        return self.store.write(index,dict(query=deepcopy(frame['query']),rawParts=deepcopy(parent),acquisition=deepcopy(frame['acquisition'])))


class SnapshotFileWorkPacket(SnapshotOwnedPacket):
    _name='native-filework'
    _key='iosSnapshotFileWorkPacketVersion'
    _namespace='snapshot-native-filework'
    _schema='snapshotNativeFileWork'
    _kind='file-work'
    _source=source
    _segments=FileWorkSegments
    _segment_subject=None

    def parts(self,live=False):
        return self._segments(self.store.path.parent,self.binding,self.run,self.role,self._segment_subject or self.role,
            self.guard if live else lambda:True,self.part_intent if live else lambda *_:need(False),monotonic=time.monotonic)
    def files(self,live=False):return Frames(self,live)
    def parent(self,value,query):
        self._source.command(query);self.parts().parent(value)
        need(value['label']=='raw' and value['tag']==hashlib.sha256(canonical(query)).hexdigest()
            and value['first']==(self.index-1)*8+1 and value['bytes']<=self._source.LIMIT)

    def load(self,value):
        states=unpack(value['payload']);need(len(states)==1);state=deepcopy(states[0]);need('rawParts' in state and 'snapshots' in state)
        parent,snapshots=state.pop('rawParts'),state.pop('snapshots')
        base=deepcopy(value);base['payload']=pack([state]);parsed=super().load(base)
        if parent is not None:
            self.parent(parent,parsed['query'])
            if snapshots is not None:self.parts().retained(parent,snapshots)
        else:need(snapshots is None)
        if parsed['phase']=='reserved':need(parent is None)
        if parsed['storage'] is not None:need(parent is not None)
        if parsed['phase']=='retained':
            body=self.files().store.read(parsed['storage']);need(same(body['rawParts'],parent))
        parsed.update(rawParts=parent,snapshots=snapshots);return parsed

    def reserve(self):
        self.bound();need(self.state is None)
        import uuid
        query=self._source.command(dict(schemaVersion=1,action=self._source.ACTION,commandId='ios-'+uuid.uuid4().hex,runId=self.run))
        self.state=dict(phase='reserved',query=query,started=None,storage=None,proof=None,rawParts=None,snapshots=None)
        self.save();return deepcopy(query)

    def part_intent(self,value):
        self.bound();need(self.state['phase']=='issued' and self.state['storage'] is None and self.state['snapshots'] is None)
        self.parent(value,self.state['query']);old=self.state['rawParts']
        if old is None:need(not value['chunks'] and not value['complete'])
        else:
            need(all(same(value[k],old[k]) for k in old if k not in ('chunks','complete')) and not old['complete'])
            before,after=old['chunks'],value['chunks']
            if len(after)==len(before)+1:
                need(same(before,after[:-1]) and all(r['phase']=='saved' for r in before) and after[-1]['phase']=='planned')
            elif len(after)==len(before) and after!=before:
                need(before and same(before[:-1],after[:-1]));a,b=before[-1],after[-1]
                need((a['phase'],b['phase']) in (('planned','opened'),('opened','saved'))
                    and all(same(a[k],b[k]) for k in a if k not in ('phase','file'))
                    and (a['phase']=='planned' or same(a['file'],b['file'])))
            else:need(same(before,after) and value['complete'] and all(r['phase']=='saved' for r in after))
        self.state['rawParts']=deepcopy(value);self.save()

    def freeze_partial(self):
        self.bound();need(self.state['phase']=='issued' and self.state['rawParts'] is not None)
        snapshot=self.parts().inspect(self.state['rawParts'])
        if self.state['snapshots'] is None:self.state['snapshots']=snapshot;self.save()
        else:need(same(self.state['snapshots'],snapshot))
        return deepcopy(snapshot)

    def retain(self):
        self.bound();need(self.state is not None and self.state['phase']=='issued')
        if self.state['storage'] is not None:return super().retain()
        try:
            parent=self.state['rawParts']
            if parent is None:
                raw=self.feature.original(remote=self.feature.remote.rsplit('/',1)[0]+'/'+self._source.FILE,limit=self._source.LIMIT)
                packet=decode(raw,limit=self._source.LIMIT);self._source.validate(packet,self.state['query'],self.pid)
                self.parts(live=True).write('raw',hashlib.sha256(canonical(self.state['query'])).hexdigest(),raw.encode(),(self.index-1)*8+1)
                parent=self.state['rawParts']
            # Recovery reads complete actual parts without repeating a query,
            # AFC read, allocation or original file write.
            raw=self.parts().read(parent).decode('utf-8');packet=decode(raw,limit=self._source.LIMIT)
            self._source.validate(packet,self.state['query'],self.pid);after=self.native.read(self.native.sequence)
            span=dict(self.state['started'],hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic(),nativeAfter=deepcopy(after))
            frame=dict(query=deepcopy(self.state['query']),raw=raw,packet=packet,acquisition=span);original(frame,self.pid,self._kind)
            proof=self.files(live=True).write(self.index,frame)
            self.state.update(phase='retained',proof=proof);self.save();return deepcopy(frame)
        except Exception:
            if self.state['rawParts'] is not None and self.state['phase']=='issued':self.freeze_partial()
            raise
