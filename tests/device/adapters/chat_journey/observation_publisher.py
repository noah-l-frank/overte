"""Original independent Chat publications from a complete fresh query cursor."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.observation_cursor import ChatObservationCursor,plain
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.chat_journey.evidence_archive import stamp,private
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import same,MAX_FRAMES
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.witness import Client,projection

VERSION=1


class ChatObservationPublisher:
    """One fresh original per publication, including repeated same-phase reads.

    The independently received common journal remains the proof of receipt.
    A lost or late POST is retained and never resent or replaced by an ACK.
    """
    def __init__(self,cursor,store):
        need(type(cursor) is ChatObservationCursor and cursor.current.stage=='initial'
            and cursor.scope['role']=='actor' and type(cursor.current.source.client) is Client
            and not cursor.rows and not cursor.failed and cursor._freeze_guard is None
            and type(store) is PrivateFeatureState and store.path.parent==cursor.store.path.parent
            and store.path not in (cursor.store.path,cursor.current.store.path) and store.read() is None)
        self.cursor,self.store,self.client=cursor,store,cursor.current.source.client
        self.previous=None;self.rows=[];self.hashes=[];self.failed=False;self.query_pending=False;self.root_stamp=None
        self.scope=dict(chatObservationPublisherVersion=VERSION,runId=cursor.scope['runId'],fixtureUrl=cursor.scope['fixtureUrl'],
            binding=deepcopy(cursor.scope['binding']),peerBinding=deepcopy(cursor.scope['peerBinding']),cursor=cursor.store.path.name)
        self.history=ChatSourceChunks(store,self.scope);self.history.inventory(0)
        self.base={**self.scope,'phase':'ready','delivery':'ready','chunks':[],'pending':None}
        self.read_guard=self.alive;cursor.bind_freeze(self.read_guard)

    def alive(self):
        return not self.failed and same(self.store.read(),self.previous)

    def control(self):
        need(self.alive() and self.cursor.current.source.client is self.client
            and len(self.rows)==len(self.hashes)==len(self.base['chunks'])
            and len(self.cursor.rows)==len(self.rows)+(1 if self.query_pending else 0))
        if self.root_stamp is not None:need(stamp(self.store.path.lstat())==self.root_stamp)
        plain(self.rows);need([digest(row) for row in self.rows]==self.hashes)
        self.history.verify();self.cursor.control()
        need(all(row['sequence']==index+1 and row['cursorSha256']==digest(self.cursor.rows[index])
            and row['payload']['actorSequence']==index+1 for index,row in enumerate(self.rows)))

    def write(self,phase,**changes):
        self.control();value={**self.base,**deepcopy(changes),'phase':phase};self.store.write(value,self.previous)
        need(same(self.store.read(),value));info=self.store.path.lstat();private(info)
        self.root_stamp=stamp(info);self.previous=self.base=deepcopy(value)

    def select(self,observation):
        need(not self.failed)
        try:
            self.control();need(self.base['phase']=='ready');self.cursor.select(observation);self.control()
        except Exception:self.failed=True;raise

    def preflight(self):
        """Expected input waiting happens before any publication/query intent."""
        observation=self.cursor.current;_flow,rows=observation.flow()
        if observation.stage=='initial' and len(rows)>1:
            raise PhasePending('Independent Chat publisher awaits its actual active source owner')
        authority,original=observation.current();active=observation.source.read(original)
        observation.matching(active,original)

    def publish(self):
        need(not self.failed and len(self.rows)<MAX_FRAMES);pending=None
        try:
            with self.cursor.held():
                try:
                    self.control();need(self.base['phase']=='ready');self.preflight()
                except PhasePending as error:pending=error
                if pending is None:
                    started=self.cursor.current.now();self.write('reading',delivery='acquiring')
                    sample=self.cursor.read(len(self.cursor.rows));self.query_pending=True
                    observed=self.cursor.rows[-1];original=self.cursor.current.rows[-1]
                    payload=dict(ticket=original['before']['activations'][-1]['ticket'],actor='owned-observer',
                        actorSequence=sample['sequence'],capturedEpochMs=sample['capturedEpochMs'],facts=projection('chat',sample['state']))
                    row=dict(sequence=sample['sequence'],cursorSha256=digest(observed),payload=deepcopy(payload))
                    self.write('reading',delivery='publishing',pending=row)
                    wire=deepcopy(payload);self.control();self.cursor.final(started)
                    self.client.request('/runs/'+self.scope['runId']+'/samples',wire)
                    need(same(wire,payload))
                    chunks=self.history.append(row,self.base['chunks'])
                    self.write('ready',delivery='ready',pending=None,chunks=chunks)
                    self.rows.append(row);self.hashes.append(digest(row));self.query_pending=False
                    self.control();self.cursor.final(started);clocks=self.cursor.clocks()
        except Exception:
            # Context-manager exit belongs to this same publication. A
            # completed-looking row cannot qualify an unreturned lock release.
            self.failed=True;raise
        if pending is not None:raise pending
        try:self.cursor.released_fresh(clocks,started)
        except Exception:self.failed=True;raise
        return row['sequence']
