"""Original paired Emote inspect/seal proof; process/SDK end is separate.

This pure owner consumes actual role journals and committed Actor originals.
It sends no input, HTTP or SDK request and grants no current-WAL discharge.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys import terminal
from feature_journeys.retirement_receipts import binding_from_context
from ios.adapters.emote_rooted_archive import grouped,reopen
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_rooted_publications import select

VERSION=1


class IOSEmoteTerminalWindow:
    def __init__(self,primary,actor):
        need(type(primary) is IOSEmoteRootedLive and type(actor) is IOSEmoteRootedLive)
        self.roles=dict(primary=primary,actor=actor);self.guard()

    def guard(self):
        p,a=self.roles['primary'],self.roles['actor']
        for live in self.roles.values():
            live.bound();need(live.state['pending'] is None and same(live.envelope(live.state),live.previous))
        need(p.role=='primary' and a.role=='actor' and p.run==a.run and p.fixture_url==a.fixture_url
            and p.phase_instance==a.phase_instance and p.primary_lock is p.lock and a.primary_lock is p.lock
            and a.lock.path!=p.lock.path and same(p.binding,p.primary_binding) and same(a.primary_binding,p.binding)
            and a.binding['targetFingerprint']!=p.binding['targetFingerprint'] and a.binding['sessionId']!=p.binding['sessionId']
            and all(a.binding[key]==p.binding[key] for key in ('artifactSha256','sourceRevision')))

    @staticmethod
    def held(measured):
        rows=[{key:row[key] for key in ('resource','kind','originalSha256')} for row in measured['held']]
        terminal.held(rows);return rows

    def describe(self,references):
        self.guard();exact(references,terminal.ROLES);roles={};ticket=None
        for role,live in self.roles.items():
            reference=references[role];need(reference in live.state['records'])
            measured=live.record(reference)['measurement']
            if ticket is None:ticket=measured['ticket']
            else:need(ticket==measured['ticket'])
            roles[role]=dict(binding=binding_from_context(live.binding),heldResources=self.held(measured),originalSha256=digest(measured))
        value=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='emotes',runId=self.roles['primary'].run,ticket=ticket,roles=roles)
        terminal.description(value);self.guard();return value

    def qualify(self,description,samples,references,*,publisher_store,record_store_for=PrivateFeatureState):
        self.guard();need(isinstance(publisher_store,PrivateFeatureState) and same(description,self.describe(references)))
        terminal.window(samples,description);primary,actor=self.roles['primary'],self.roles['actor']
        selected=primary.selected_many([pair['primary'] for pair in samples])
        for row in selected:
            need(row['measurement']['ticket']==description['ticket']
                and same(self.held(row['measurement']),description['roles']['primary']['heldResources']))
        actor_rows=[];snapshots=[];available={}
        for reference in actor.state['records']:
            row=actor.record(reference);sequence=row['measurement']['public']['sequence']
            need(sequence not in available);available[sequence]=row
        for pair in samples:
            sequence=pair['actor']['actorSequence'];need(sequence in available)
            row=available[sequence];measured=row['measurement']
            need(measured['ticket']==description['ticket']
                and same(self.held(measured),description['roles']['actor']['heldResources']))
            actor_rows.append(row);snapshots.append(actor.read_frame(row['reference'])['snapshot'])
        # The supplied entries select exact existing server receipts. They do
        # not provide feature facts or authorize an Actor publication.
        value=publisher_store.read();need(value is not None)
        publications=select(snapshots[-1],value,store=publisher_store,entries=[pair['actor'] for pair in samples],
            lock=actor.lock,primary_lock=actor.primary_lock,record_store_for=record_store_for)
        joined=[]
        with grouped(snapshots,lock=actor.lock,primary_lock=actor.primary_lock):
            for snapshot,row,publication in zip(snapshots,actor_rows,publications):
                keyed=reopen(snapshot,lock=actor.lock,primary_lock=actor.primary_lock)
                rendered=keyed.rendered_owner;rendered_original=rendered.original(keyed.original(snapshot['reference'])['renderedReference'])
                native=rendered.native_owner.original(rendered_original['nativeReference'])
                # Compare both actual private original payloads, not merely
                # their public projection, sequence or stored graph hashes.
                need(same(native['observation'],publication['observation']))
                joined.append(dict(live=deepcopy(row['reference']),publication=deepcopy(publication['reference']),
                    observation=deepcopy(publication['original']),entry=deepcopy(publication['entry'])))
        proof=dict(iosEmoteTerminalWindowVersion=VERSION,description=deepcopy(description),references=deepcopy(references),
            samples=deepcopy(samples),journals={role:deepcopy(live.previous) for role,live in self.roles.items()},
            primary=[deepcopy(row['reference']) for row in selected],actor=joined,publisher=deepcopy(value))
        seal=dict(featureTerminalSealVersion=1,description=deepcopy(description),windowSha256=digest(samples),liveOriginalSha256=digest(proof))
        terminal.sealed(seal,description,samples);need(same(publisher_store.read(),value));self.guard()
        return dict(seal=seal,original=proof)
