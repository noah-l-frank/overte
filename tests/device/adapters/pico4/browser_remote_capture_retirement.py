"""Existing complete capture retirement after actual independent Actor return."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json

from adapters.chat_journey.source_chunks import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.browser_actor_return import PicoBrowserActorReturn
from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
from adapters.pico4.browser_stereo import original_name
from adapters.script_journey.history import same,unpack

VERSION=1


class PicoBrowserRemoteCaptureRetirement(PicoBrowserCaptureRetirement):
    """No Actor reconstruction or input; original Parent supplies new queries."""
    def __init__(self,primary,returned):
        from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
        need(type(primary) is PicoTabletWebFeature and primary.role=='primary'
            and type(returned) is PicoBrowserActorReturn and returned.complete and not returned.failed
            and returned.lock.path==primary.lock.path
            and returned.export.path.parent==primary.store.path.parent
            and returned.expected['runId']==primary.run and returned.expected['fixtureUrl']==primary.fixture_url
            and returned.expected['foreignFixtureUrl']==primary.foreign_url
            and returned.expected['artifactRoot']==str(primary.artifact_root)
            and returned.expected['sceneUrl']==primary.adapter.scene_url)
        self.returned=returned
        self.initialize(primary,None,'pico-tablet-web-remote-capture-retirement.json')

    def admit(self):
        returned=self.returned.receipt() # Outside a distinct same-inode Parent lock.
        need(self.store.read() is None)
        primary_owner,_state=self.role(self.primary);remote=self.returned.graph
        self.scope=dict(picoBrowserRemoteCaptureRetirementVersion=VERSION,runId=self.primary.run,
            fixtureUrl=self.primary.fixture_url,binding=deepcopy(self.binding),ownerToken=primary_owner['ownerToken'])
        with self.returned.lock.held():
            remote.verify();need(same(remote.owner,primary_owner))
            # Admit every exact physical source, including metadata; original
            # PNGs retain their separate full-byte readers below.
            for row in remote.manifest:
                parent=remote.export.path.parent if row['location']=='state' else remote.artifacts
                path=parent/row['name']
                if row['location']=='artifact' and not row['name'].endswith('.native.json'):continue
                raw=remote.file(path);value=json.loads(raw);store=PrivateFeatureState(path)
                need(same(store.read(),value));self.add(store,value,'actor')
            for image in remote.role['images']:
                name=original_name(self.primary.run,'actor',image['journalId'])
                rows=unpack(json.loads(remote.file(remote.artifacts/name))['payload'])
                need(len(rows)==1);original=rows[0];proof=deepcopy(original['proof']);png=deepcopy(original['image'])
                need(all(row['value']['name']!=png['name'] for row in self.pngs))
                self.proofs.append(proof)
                self.pngs.append(dict(role='actor',value=png,stamp=deepcopy(remote.files[('artifact',png['name'])]['stamp'])))
            self.add(remote.export,remote.root,'actor')
            for index in range(len(remote.export_chunks.identities)):
                store=remote.export_chunks.store(index);self.add(store,store.read(),'actor')
            receiver=self.returned.receiver
            self.add(receiver.store,receiver.consumed(historical=True)[0],'actor')
            self.add(receiver.ack_store,receiver.intent,'actor')
            for index in range(len(receiver.history.identities)):
                store=receiver.history.store(index);self.add(store,store.read(),'actor')
            self.add(self.returned.store,returned,'actor');remote.verify()
        need(self.proofs)
        self.scope.update(capturesSha256=digest(self.proofs),actorRetirementSha256=digest(remote.retirement),
            actorReturnSha256=digest(returned))
        self.begin_original_queries()
