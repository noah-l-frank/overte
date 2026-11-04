"""Private reuse of an actual Common cleanup window, with original G1 sources.

This participant neither dispatches the fourteen-step journey nor qualifies
Actor authentication, acoustic capture, source retirement or a public route.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import hashlib

from adapters.native_feature_observation import need,number,fresh
from adapters.script_journey.history import canonical
from feature_journeys.contract import result
from feature_journeys.engine import Journey
from feature_journeys.witness import projection,Client


class AudioCommonCleanup1:
    def __init__(self,owner):
        self.owner=owner;self.budget=owner.budget
        need(self.budget.common_owner is self and self.budget.common_credit==2*1048576)
        self.journey=None;self.callback=self.consume;self.invoke=self.observe;self.read_witness=self.witness
        self.started=self.consumed=False
        self.failed=False;self.failure=None;self.rows=[];self.pending_peer=None
        self.first=self.previous=self.keys=None;self.first_host=self.previous_host=None
        self.windows=0;self.complete=False;self.raw=None;self.refusal=None;self.host_rows=[]
        self.authenticated=self.budget.common_authenticated
        self.actor_base=0;self.actor_phase=None;self.publication=None
        self.primary_client=self.actor_client=None
        if self.authenticated:
            self.primary_client=owner.source.client;self.actor_client=owner.actor.source.client
            need(type(self.primary_client) is Client and type(self.actor_client) is Client
                and self.primary_client.token!=self.actor_client.token
                and self.primary_client.url==self.actor_client.url
                and owner.actor.source.client is owner.actor._phase_client
                and hashlib.sha256(self.actor_client.token.encode()).hexdigest()==owner.actor.raw_scope['actorCredentialSha256'])
            self.actor_base=owner.actor.state['sequence']
            need(type(self.actor_base) is int and 0<=self.actor_base<=1000000000)
        self._primary_credential_sha=None if self.primary_client is None else hashlib.sha256(self.primary_client.token.encode()).hexdigest()
        self.actor_context=self.actor_context_reference=None
        if self.authenticated:
            self.actor_context=canonical(dict(audioCleanupActorContextVersion=1,
                runId=owner.recipe.run,binding=owner.state['newBinding'],
                nativeInstance=owner.state['newProof']['native']['native']['instance'],
                originalActorHeader=owner.actor.header_ref,
                actorCredentialSha256=owner.actor.raw_scope['actorCredentialSha256'],
                primaryCredentialSha256=self._primary_credential_sha,actorSequenceBase=self.actor_base))
            need(len(self.actor_context)<=4096)
        self._actor_context=self.actor_context
        self._original_actor_base=self.actor_base

    def poison(self,error):
        if self.failure is None:self.failure=(error,error.__traceback__)
        self.failed=True;self.owner.poison(error)

    def attach(self,journey):
        need(type(journey) is Journey and journey.area=='audio'
            and journey.run==self.owner.recipe.run and journey.url==self.owner.source.fixture_url
            and journey.after_cleanup_baseline is self.callback
            and journey.invoke is self.invoke and journey.witness is self.read_witness
            and journey.audio_cleanup_poll_profile=='pico-audio-cleanup1'
            and self.journey is None and not self.started)
        self.journey=journey

    def control(self):
        j=self.journey
        need(self.budget.common_owner is self and not self.failed and j is not None
            and j.invoke is self.invoke and j.witness is self.read_witness
            and j.after_cleanup_baseline is self.callback and j.run==self.owner.recipe.run
            and j.url==self.owner.source.fixture_url)
        need(self.authenticated is self.budget.common_authenticated and self.actor_base==self._original_actor_base)
        if self.authenticated:
            need(self.primary_client is self.owner.source.client and self.actor_client is self.owner.actor._phase_client
                and self.actor_client is self.owner.actor.source.client
                and self.owner.actor.source is self.owner.actor._phase_source
                and self.primary_client.url==self.actor_client.url
                and self.primary_client.url+'/runs/'+self.owner.recipe.run+'/'==self.owner.source.fixture_url
                and hashlib.sha256(self.primary_client.token.encode()).hexdigest()==self._primary_credential_sha
                and self.actor_context is self._actor_context and type(self.actor_context) is bytes
                and len(self.actor_context)<=4096
                and self.primary_client.token!=self.actor_client.token
                and hashlib.sha256(self.actor_client.token.encode()).hexdigest()==self.owner.actor.raw_scope['actorCredentialSha256'])
        j.poll_policy()

    def begin(self):
        try:
            owner=self.owner;self.control()
            need(not self.started and not self.failed and self.journey is not None)
            owner.guard();owner.phase();self.budget.admit_new_quiet(owner)
            if self.authenticated:
                self.actor_phase=owner.actor.source.read(owner.state['fixture'])
                need(self.actor_phase['ticket']==owner.state['fixture']['activations'][-1]['ticket']
                    and self.actor_phase['verb']=='cleanup' and self.actor_phase['inputs']=={})
            owner._quiet_tokens=[];owner._quiet_rows=[];owner._quiet_compact=[]
            if self.authenticated:
                token=owner.actor.raws.reserve('audio-cleanup-actor-context',
                    dict(audioCleanupActorContextVersion=1,runId=owner.recipe.run,
                        contextSha256=hashlib.sha256(self.actor_context).hexdigest()),4096)
                self.actor_context_reference=owner.actor.raws.retain(token,self.actor_context)
            owner.quiet_tokens(0);owner.issue('quiet-reading');self.started=True
        except BaseException as error:self.poison(error);raise

    def project(self,sampler,encoded):
        compact=self.owner.quiet_projection(sampler,encoded)
        # This full snapshot parse is confined to this method; only immutable
        # small projected bytes cross its return. The old quiet work stays held.
        value=json.loads(encoded)
        frame=dict(schemaVersion=1,contractVersion=16,runId=self.owner.recipe.run,
            sequence=value['sequence'],capturedEpochMs=min(value['originalClocks']),
            state=value['state'],artifacts=[],resources=[],lifecycle=value['lifecycle'])
        result('feature.audio.observe',frame)
        raw=canonical(frame);need(len(raw)<=2048)
        return compact,raw

    def observe(self,operation,fields):
        try:
            self.control()
            need(self.budget.common_owner is self and self.started and not self.failed and not self.consumed and self.pending_peer is None
                and operation=='feature.audio.observe' and fields==dict(contractVersion=16,
                    runId=self.owner.recipe.run,afterSequence=self.journey.sequence))
            owner=self.owner;attempt=len(self.rows);need(attempt<41)
            if attempt>=len(owner._quiet_tokens):owner.quiet_tokens(attempt)
            raws=[];compact=[];frames=[]
            for sampler in self.budget.new_samplers:
                encoded=sampler.sample();raws.append(encoded)
                part,frame=self.project(sampler,encoded);compact.append(part);frames.append(frame)
            framed=(b'AudioQuietPair1\x00'+len(raws[0]).to_bytes(4,'big')+raws[0]
                +len(raws[1]).to_bytes(4,'big')+raws[1])
            need(len(framed)<=2*16384+32)
            ref=owner.actor.raws.retain(owner._quiet_tokens[attempt],framed)
            owner._quiet_rows.append(ref);owner._quiet_compact=compact
            measured=[json.loads(part) for part in compact]
            clocks=[stamp for row in measured for stamp in row['clocks']]
            keys=[row['key'] for row in measured];now=owner.now()
            self.host_rows.append(now)
            need(all(number(stamp,1,1e15) for stamp in clocks))
            if self.first is None:
                self.first=list(clocks);self.first_host=now;self.keys=keys
            else:
                need(keys==self.keys and all(a>=b for a,b in zip(clocks,self.previous)))
                if now-self.previous_host>.5 or any(a-b>500 for a,b in zip(clocks,self.previous)):
                    self.windows+=1;need(self.windows<8)
                    self.first=list(clocks);self.first_host=now
            self.previous=list(clocks);self.previous_host=now
            self.complete=now-self.first_host>=3 and all(a-b>=3000 for a,b in zip(clocks,self.first))
            primary=json.loads(frames[0]);peer=json.loads(frames[1])
            self.rows.append((frames[0],frames[1],ref))
            self.pending_peer=peer
            return primary
        except BaseException as error:self.poison(error);raise

    def witness(self):
        try:
            self.control()
            need(self.budget.common_owner is self and self.started and not self.failed and self.pending_peer is not None)
            peer=self.pending_peer
            if self.authenticated:return self.authenticated_witness(peer)
            self.pending_peer=None
            # This declared in-process journal transport model grants no real
            # publisher credential. Its facts come ONLY from the second reader.
            captured=peer['capturedEpochMs'];now=self.owner.io.adapter.epoch_milliseconds(self.owner.io.target)
            return dict(schemaVersion=1,runId=self.owner.recipe.run,area='audio',
                ticket=self.owner.state['fixture']['activations'][-1]['ticket'],sampleEpochMs=now,
                entries=[dict(ticket=self.owner.state['fixture']['activations'][-1]['ticket'],
                    actor='owned-observer',actorSequence=peer['sequence'],capturedEpochMs=captured,
                    facts=projection('audio',peer['state']),sequence=peer['sequence'],receivedEpochMs=now)])
        except BaseException as error:self.poison(error);raise

    def authenticated_witness(self,peer):
        # Original phase metadata is checked both sides of the independent
        # source acquisition. It is never copied into observed product facts.
        need(self.publication is None)
        packet=dict(ticket=self.actor_phase['ticket'],actor='owned-observer',
            actorSequence=self.actor_base+peer['sequence'],capturedEpochMs=peer['capturedEpochMs'],
            facts=projection('audio',peer['state']))
        self.publication=packet  # Strong uncertainty BEFORE actual POST.
        self.actor_client.request('/runs/'+self.owner.recipe.run+'/samples',packet)
        observed=self.primary_client.request('/runs/'+self.owner.recipe.run)
        need(observed['runId']==self.owner.recipe.run and observed['area']=='audio')
        rows=[row for row in observed['entries'] if row['actorSequence']==packet['actorSequence']]
        need(len(rows)==1 and all(rows[0][key]==value for key,value in packet.items()))
        self.pending_peer=None;self.publication=None
        return observed

    def consume(self,raw):
        try:
            self.control();j=self.journey;owner=self.owner
            self.refusal=dict(complete=self.complete,samples=len(self.rows),tokens=len(owner._quiet_tokens),
                commonSamples=len(j.samples),windows=self.windows,firstHost=self.first_host,lastHost=self.previous_host,
                hostRows=list(self.host_rows),firstNative=self.first,lastNative=self.previous,
                rawBytes=len(raw) if type(raw) is bytes else None,pendingPeer=self.pending_peer is not None,
                sequenceSucceeded=j._cleanup_sequence_succeeded,commonPhase=j.phases[-1] if j.phases else None)
            need(self.budget.common_owner is self and not self.failed and not self.consumed and self.started and self.pending_peer is None
                and type(raw) is bytes and raw is j.cleanup_consumption and j.cleanup_hook_started
                and len(raw)<=262144 and not j._cleanup_sequence_succeeded
                and self.complete and len(self.rows)==len(owner._quiet_tokens)
                and len(self.rows)==len(j.samples) and j.phases[-1]['stableSeconds']>=3)
            for sample,(primary_raw,peer_raw,_ref) in zip(j.samples,self.rows):
                primary=json.loads(primary_raw);peer=json.loads(peer_raw)
                need(all(sample[key]==primary[key] for key in
                    ('sequence','capturedEpochMs','state','resources','lifecycle'))
                    and sample['witness']['facts']==projection('audio',peer['state'])
                    and sample['witness']['actorSequence']==self.actor_base+peer['sequence']
                    and sample['witness']['capturedEpochMs']==peer['capturedEpochMs']
                    and sample['witness']['ticket']==sample['ticket'])
            if self.authenticated:
                after=owner.actor.source.read(self.actor_phase['status'])
                need(after['ticket']==self.actor_phase['ticket'] and after['verb']=='cleanup' and after['inputs']=={})
            self.raw=raw
            owner.phase();owner.io.guard_identity(owner.state['newBinding']['processIdentity'])
            value=deepcopy(owner.state);value.update(phase='new-quiet',roleQuiet=dict(
                version=1,first=self.first,last=self.previous,firstHost=self.first_host,
                lastHost=self.previous_host,keys=self.keys,incompleteWindows=self.windows,
                references=deepcopy(owner._quiet_rows),complete=True))
            if self.authenticated:
                need(owner.actor.raws.literal(self.actor_context_reference)==self.actor_context)
                value['roleQuiet'].update(version=2,actorContext=self.actor_context_reference,
                    actorCredentialSha256=owner.actor.raw_scope['actorCredentialSha256'],actorSequenceBase=self.actor_base)
            owner.save(value);owner.guard()
            fresh(min(self.previous),self.budget.new_samplers[0].native.clock_ms())
            self.consumed=True
        except BaseException as error:self.poison(error);raise
