"""Explicit Primary-only control receiver and existing original ordering proof.

The adapter keeps its GET-only/peer-facts-filtered client. A separate scoped
capability permits two existing control POSTs, never fixture reader authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import secrets
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_clock_join import digest
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import same
from feature_journeys.witness import Client
from feature_journeys.avatar_primary_control import issuer,PURPOSES
from ios.adapters.authentication_origin import origin
from ios.adapters.emote_original_lease import EmoteOriginalLease


class AvatarPrimaryControl(Client):
    def __init__(self,url,value):
        issuer(value,value['runId'],url);need(value['phase']=='saved');origin(url)
        super().__init__(url,value['grant']['token']);self.run=value['runId'];self.request_id=value['requestId']
    def admit(self):
        nonce=secrets.token_hex(16);path='/runs/'+self.run+'/avatar/control-admission/'+self.request_id+'/'+nonce
        value=super().request(path)
        exact(value,{'avatarPrimaryControlAdmissionVersion','runId','role','purposes','requestId','nonce','usedPurposes'})
        need(type(value['avatarPrimaryControlAdmissionVersion']) is int and value['avatarPrimaryControlAdmissionVersion']==1
            and value['runId']==self.run and value['role']=='primary' and value['purposes']==PURPOSES
            and value['requestId']==self.request_id and value['nonce']==nonce and type(value['usedPurposes']) is list
            and len(value['usedPurposes'])<=2 and all(type(item) is str and item in PURPOSES for item in value['usedPurposes'])
            and len(set(value['usedPurposes']))==len(value['usedPurposes']))
        return value
    def request(self,path,value=None,method=None,**kwargs):
        need(not kwargs and method=='POST' and path in ('/runs/'+self.run+'/avatar/sessions','/runs/'+self.run+'/avatar/control'))
        self.admit();return super().request(path,value,method='POST')


def load(client,run,role,configuration):
    if 'authorityControlRoot' not in configuration:return None
    need(role=='primary');root=Path(configuration['authorityControlRoot']);need(root.is_absolute())
    store=PrivateFeatureState(root/('avatar-primary-control-'+run+'.json'));value=store.read()
    need(value is not None);issuer(value,run,client.url);need(value['phase']=='saved')
    return AvatarPrimaryControl(client.url,value)


def checkpoint_order(flow):
    """Existing Actor-private published original is a receipt, never peer facts.

    Source/native proof and the actual publisher record remain their original
    owners. This derives only token-free ordering metadata; no new endpoint,
    Actor output or publisher record is manufactured and no HTTP is required.
    """
    from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
    need(flow.role=='primary')
    path=flow.runtime.state_path(flow.selectors['actor']).with_name('ios-avatar-actor-feature.json')
    with flow.held(paired=True):
        flow.load();flow.cleanup_deadline();before=flow.phase.read();store=PrivateFeatureState(path);raw=store.read()
        if raw is None:raise AvatarFeaturePending('Original Actor checkpoint owner is not available')
        leases=[EmoteOriginalLease(root,[]) for root in {Path(raw['artifactRoot']),path.parent}]
        actor=IOSAvatarFeature.archive(flow.runtime,raw,flow.client,flow.locks)
        need(actor.role=='actor' and actor.run==flow.run and same(actor.selectors,flow.selectors)
            and same(actor.state['bindings'],flow.state['bindings']) and actor.state['phaseInstance']==flow.state['phaseInstance'])
        events=[row for row in actor.state['cleanup'] if row['kind']=='checkpoint']
        if not events or not events[0]['published']:raise AvatarFeaturePending('Original Actor checkpoint publication is unresolved')
        event=events[0];need(event['publisher'] is not None)
        # This is the existing pure checkpoint/native and publisher decoder,
        # not the GET /runs journal that deliberately redacts peer facts.
        actor.checkpoint_original();observer,reference,_record=actor.checkpoint_observer()
        publisher_store=PrivateFeatureState(path.with_name('phase-publication-avatar-people-'+flow.run+'-actor.json'))
        value=actor.kept(event['publisher'])
        state=PhaseWitnessPublisher.archive(value,store=publisher_store,binding=actor.state['bindings']['actor'],
            run=actor.run,area='avatar-people',fixture_url=flow.client.url,phase_instance=actor.state['phaseInstance'],
            validate_original=observer.validate_original)
        need(state['pending'] is None and state['records'])
        reader=object.__new__(PhaseWitnessPublisher);reader.store=publisher_store;reader.binding=actor.state['bindings']['actor']
        reader.run,reader.area=actor.run,'avatar-people';reader.url,reader.instance=flow.client.url,actor.state['phaseInstance']
        reader.validate_original=observer.validate_original
        last=reader.load(state['records'][-1]);need(last['mode']=='published' and same(last['intent']['original'],reference))
        body=last['intent']['body'];entry=last['entry'];ticket=flow.state['cleanup'][0]['ticket']
        need(body['ticket']==ticket and body['actor']=='owned-observer' and integer(body['actorSequence'],1)
            and entry['ticket']==ticket and entry['actorSequence']==body['actorSequence'] and integer(entry['sequence'],1))
        after=flow.phase.read()
        need(before['verb']==after['verb']=='cleanup' and before['ticket']==after['ticket']==ticket
            and before['status']['instance']==after['status']['instance']==flow.state['phaseInstance']
            and same(before['status']['activations'],after['status']['activations']) and same(store.read(),raw))
        for lease in leases:lease.guard()
        flow.cleanup_deadline()
        return dict(avatarCheckpointOrderReceiptVersion=1,runId=flow.run,role='actor',purpose='cleanup-checkpoint-order',
            phaseInstance=flow.state['phaseInstance'],ticket=ticket,actorSequence=body['actorSequence'],sequence=entry['sequence'],
            bodySha256=digest(body),publisherOriginalSha256=state['records'][-1]['sha256'])
