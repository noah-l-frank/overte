"""Each actual controller answer, durably stored before effect assessment."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.snapshot_cancel_originals import SnapshotCancelOriginals
from adapters.pico4.snapshot_originals import nonce
from adapters.script_journey.history import canonical
from feature_journeys.contract import typed_equal,json_document
from openxr_input.controller_protocol import validate_envelope

VERSION=1
LIMIT=96


class SnapshotCloseStatuses(SnapshotCancelOriginals):
    def __init__(self,path,run,binding,profile):
        need(nonce(run));self.root=PrivateFeatureState(path);self.profile=profile
        self.scope=dict(snapshotCloseStatusesVersion=VERSION,runId=run,binding=deepcopy(context(binding)),role='snapshot-close-controller-answers')
        self.history=ChatSourceChunks(self.root,self.scope);self.disk=self.root.read();self.values=[];self.indices={}
        if self.disk is not None:
            exact(self.disk,set(self.scope)|{'phase','chunks'})
            need(all(typed_equal(self.disk[key],value) for key,value in self.scope.items()) and self.disk['phase']=='reading')
            self.values=self.history.load(self.disk['chunks'])
        else:self.history.inventory(0)
        need(len(self.values)<=LIMIT)
        for index,value in enumerate(self.values):
            self.original(value);need(value['original']['sequence']==index+1 and (index==0 or value['original']['observedHostMonotonic']>=self.values[index-1]['original']['observedHostMonotonic']));digest=self.digest(value);need(digest not in self.indices);self.indices[digest]=index
        self.values_sha=self.digest(self.values);self.scope_sha=self.digest(self.scope);self.verify()

    def original(self,value):
        exact(value,{'kind','original'});need(value['kind']=='controller-status');row=value['original']
        exact(row,{'sequence','envelope','status','observedHostMonotonic'})
        need(integer(row['sequence'],1,LIMIT) and number(row['observedHostMonotonic'],0,1e15)
            and len(canonical(row))<=32768 and typed_equal(row,json_document(canonical(row))))
        validate_envelope(row['envelope'],self.profile)
        # status is the actual returned JSON value. It may be active, unknown,
        # incomplete or otherwise unusable. Storage never upgrades it to neutral.

    def verify(self):
        need(self.digest(self.values)==self.values_sha and self.digest(self.scope)==self.scope_sha
            and typed_equal(self.values,json_document(canonical(self.values))) and typed_equal(self.scope,json_document(canonical(self.scope))) and typed_equal(self.root.read(),self.disk))
        super().verify()

    def append(self,envelope,status,observed):
        self.verify();index=len(self.values);need(index<LIMIT and (index==0 or observed>=self.values[-1]['original']['observedHostMonotonic']))
        row=dict(sequence=index+1,envelope=deepcopy(envelope),status=deepcopy(status),observedHostMonotonic=observed)
        reference=self.put('controller-status',row);need(reference['snapshotOriginal']==index)
        self.values_sha=self.digest(self.values);self.verify();return index

    def read(self,index):
        need(integer(index,0,len(self.values)-1));return deepcopy(self.values[index]['original'])
