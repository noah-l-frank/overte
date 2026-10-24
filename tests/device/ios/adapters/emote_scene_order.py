"""Historical once-per-ticket scene ordering, separate from current cleanup.

Only this closed Emote owner accepts an older committed scene. It preserves the
original receipt and all shared admission/journal checks. Fresh local/Actor
cleanup and terminal-window observations remain separate mandatory evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.phase_retirement_publisher import PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from adapters.script_feature.history import same
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE,stage

VERSION=1


class IOSEmoteSceneOrder(PhaseRetirementReader):
    def __init__(self,*args,**kwargs):
        kwargs.setdefault('stage',WEB_SCENE_STAGE);super().__init__(*args,**kwargs)
        need(self.area=='emotes' and self.stage==WEB_SCENE_STAGE
            and self.store.path.name=='ios-emote-primary-scene-order-'+self.run+'.json')

    def envelope(self,state,version=None):
        need(version is None or version==3)
        return dict(iosEmoteSceneOrderVersion=VERSION,reader=super().envelope(state,version=3))

    def decode(self,value):
        exact(value,{'iosEmoteSceneOrderVersion','reader'})
        need(type(value['iosEmoteSceneOrderVersion']) is int and value['iosEmoteSceneOrderVersion']==VERSION
            and type(value['reader']) is dict and type(value['reader'].get('phaseRetirementReaderVersion')) is int
            and value['reader']['phaseRetirementReaderVersion']==3)
        # Preserve the literal shared historical grammar. This explicit outer
        # owner changes live read semantics; a default reader rejects it.
        reader=object.__new__(PhaseRetirementReader);reader.__dict__.update(self.__dict__)
        return reader.decode(value['reader'])

    def read(self):
        need(self.guard() is not False and same(self.store.read(),self.previous)
            and same(self.admission(),self.actor) and len(self.state['records'])<128)
        epoch,started=self.epoch_ms(),self.monotonic()
        floor=self.state['records'][-1]['phaseAfter'] if self.state['records'] else None
        before=self.phase.status(floor);journal=self.phase.client.request('/runs/'+self.run+'/retirements')
        after=self.phase.status(before);self.journal(journal)
        if not journal['entries'] or stage(journal['entries'][-1])!=WEB_SCENE_STAGE:
            raise PublicationPending('No committed Emote scene ordering original is present')
        record=dict(phaseBefore=before,journal=journal,phaseAfter=after,
            acquisition=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=self.epoch_ms(),
                hostBeforeMonotonic=started,hostAfterMonotonic=self.monotonic()),entry=deepcopy(journal['entries'][-1]))
        record['sha256']=digest(record);self.record(record)
        need(self.guard() is not False and same(self.admission(),self.actor) and same(self.store.read(),self.previous))
        self.state['records'].append(record);value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        end,mono=self.epoch_ms(),self.monotonic()
        need(number(end,record['acquisition']['hostAfterEpochMs'],epoch+1500) and end-epoch<1500
            and number(mono,record['acquisition']['hostAfterMonotonic'],started+1.5) and mono-started<1.5
            and self.guard() is not False and same(self.admission(),self.actor) and same(self.store.read(),self.previous))
        return deepcopy(record)
