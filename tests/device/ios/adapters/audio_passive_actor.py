"""Independent Actor capture scheduling on the existing passive original owner.

Arm/birth is only an input-order cue for the ordinary Primary recording input.
Native completion, exact raw files and separate resource absence remain owned
by IOSAudioPassiveOwner. No waveform is classified as acoustic playback here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import time
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.audio_api_clock import operation
from ios.adapters.audio_passive_capture_source import hex32,original_frame
from ios.adapters.audio_passive_runtime import IOSAudioPassiveRuntime,PassiveSDKLedger

VERSION=1
SECONDS=8


def lease_id(run,ticket):
    need(hex32(run) and hex32(ticket))
    return hashlib.sha256(('ios-audio-passive-actor-v1:'+run+':'+ticket).encode('ascii')).hexdigest()[:32]


class IOSAudioPassiveActor:
    def __init__(self,runtime,selector,run,artifact_root,client,*,epoch_ms=lambda:time.time()*1000,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(runtime,IOSAudioPassiveRuntime) and hex32(run) and isinstance(client,Client)
            and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.run,self.root,self.client=runtime,selector,run,Path(artifact_root),client
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self.phase=PhaseFixtureReader(client,run,'audio',epoch_ms=epoch_ms,monotonic=monotonic)
        self.lock=ScriptSourceLock(runtime.state_path(selector).with_name('script-feature-sources.lock'))
    def owner(self,lease):
        return self.runtime.passive_owner(self.selector,self.run,lease,self.root,self.client,
            epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
    def archive(self,lease=None):
        """Read all original membership before any fresh canonical SDK source.

        This never calls _sources/native or creates/adopts a child. Return only
        inside the actual SDK lock because every archive keeps that lock domain.
        """
        self.lock.assert_held()
        value=PrivateFeatureState(self.runtime.state_path(self.selector).with_name('ios-audio-passive-ledger.json')).read()
        if value is None:return None
        need(type(value) is dict and type(value.get('leases')) is list)
        if not value['leases']:
            # The real initial scope/ledger commit can return uncertain before
            # any child path or Native Start was planned. Fully admit that
            # empty existing owner; only its original normal select may resume.
            selected='0'*32 if lease is None else lease;need(hex32(selected))
            ledger=PassiveSDKLedger(self.runtime,self.selector,self.run,selected,self.root,self.client,self.lock)
            need(not ledger.rows and not ledger.archives);return None
        # Pure historical reads can inspect an older retired episode while
        # the current episode is active. Admit the actual latest selected duty
        # first, preserving every other lease's required retirement proof.
        current=value['leases'][-1]['leaseId'];need(hex32(current))
        selected=current if lease is None else lease;need(hex32(selected))
        ledger=PassiveSDKLedger(self.runtime,self.selector,self.run,current,self.root,self.client,self.lock)
        rows=[row for row in ledger.rows if row['leaseId']==selected];need(len(rows)<=1)
        return None if not rows else (selected,ledger.archives.get(selected))
    def trigger(self,status,lease):
        rows=[row for row in status['activations'] if row['stimulus']['verb']=='record-start'
            and lease_id(self.run,row['ticket'])==lease]
        need(len(rows)==1);return rows[0]
    def birth(self,owner,ticket):
        need(owner.state['birth'] is not None)
        proof=owner.proof(owner.state['birth']);selected=owner.proof(proof['selection'])
        for packet in (selected['phaseBefore'],selected['phaseAfter']):
            need(packet['active'] and packet['activations'][-1]['ticket']==ticket
                and packet['activations'][-1]['stimulus']['verb']=='record-start')
        need(owner.lease==lease_id(self.run,ticket))
        return dict(reference=owner.state['birth'],selection=proof['selection'],clockJoin=deepcopy(selected['clockJoin']))
    def handoff(self,owner,ticket):
        # This is the original native Start/intent birth and input metadata,
        # not proof that Primary recorded, played, emitted or was heard.
        birth=self.birth(owner,ticket)
        return dict(iosAudioPassiveActorVersion=VERSION,runId=self.run,ticket=ticket,leaseId=owner.lease,
            phase=owner.state['phase'],birth=birth,snapshot=owner.state['snapshot'],absence=owner.state['absence'],
            physicalADCQualified=False,acousticQualified=False,peerQualified=False,wholeQualified=False)
    def ready(self,ticket):
        """Pure input-order handoff; no SDK query, write or current-data cache."""
        with self.lock.held():
            current=self.archive(lease_id(self.run,ticket))
            if current is None or current[1] is None or current[1].state['birth'] is None:return None
            owner=current[1];need(owner.state['release'] is None and owner.state['absence'] is None)
            return self.handoff(owner,ticket)
    @operation
    def arm(self,ticket):
        status=self.phase.read();need(status['verb']=='record-start' and status['ticket']==ticket)
        with self.owner(lease_id(self.run,ticket)) as owner:
            if owner.state['birth'] is None:owner.start(SECONDS)
            need(owner.state['release'] is None and owner.state['absence'] is None)
            return self.handoff(owner,ticket)
    @operation
    def step(self):
        status=self.phase.status()
        with self.lock.held():
            previous=self.archive()
            if previous is None:lease=archived=ticket=birth=None
            else:
                lease,archived=previous;ticket=self.trigger(status,lease)['ticket']
                birth=None if archived is None or archived.state['birth'] is None else self.birth(archived,ticket)
                retired=archived is not None and archived.state['absence'] is not None
                if retired:
                    newest=status['activations'][-1] if status['active'] and status['activations'] else None
                    if newest is None or newest['stimulus']['verb']!='record-start' or newest['ticket']==ticket:
                        return self.handoff(archived,ticket) if birth is not None else dict(retired=True,captureAvailable=False)
                    lease=archived=ticket=birth=None
        if lease is None:
            if not status['active'] or not status['activations'] or status['activations'][-1]['stimulus']['verb']!='record-start':return None
            return self.arm(status['activations'][-1]['ticket'])
        if not status['active'] or status['activations'][-1]['stimulus']['verb']=='cleanup':
            with self.owner(lease) as owner:
                owner.retire()
                return self.handoff(owner,ticket) if owner.state['birth'] is not None else dict(retired=True,captureAvailable=False)
        if birth is None:
            # Resolve uncertain Start through the owner's Observe/original intent,
            # never a second Start. The original triggering phase must still hold.
            return self.arm(ticket)
        now=self.monotonic();started=birth['clockJoin']['hostAfterMonotonic'];need(now>=started)
        if now-started<SECONDS:
            # The host clock only schedules a later query, outside every SDK
            # lock. It cannot declare that native samples have completed.
            with self.lock.held():return self.handoff(self.archive(lease)[1],ticket)
        with self.owner(lease) as owner:
            if owner.state['snapshot'] is None:
                _index,observation=owner.control('observe')
                if not observation['packet']['source']['state']['complete']:return self.handoff(owner,ticket)
                owner.capture()
            owner.retire();return self.handoff(owner,ticket)
    def original(self,ticket):
        """Untouched original Actor WAV/native rows for later window analysis.

        No current public acquisition timestamp, ticket or acoustic verdict is
        fabricated. The actual native selection phase and clock are returned.
        """
        with self.lock.held():
            current=self.archive(lease_id(self.run,ticket));need(current is not None and current[1] is not None)
            owner=current[1];handoff=self.handoff(owner,ticket);need(handoff['snapshot'] is not None and handoff['absence'] is not None)
            snapshot=owner.proof(handoff['snapshot']);selection=owner.proof(snapshot['selection']);value=owner.snapshot()
            raw=owner.assembled(snapshot['chunks']['capture'],'capture',snapshot['selection'],handoff['snapshot'])
            native=original_frame(raw,value['wav'],owner.state['capture'],owner.pid)
            return dict(handoff=handoff,wav=value['wav'],native=native,selection=deepcopy(selection),original=snapshot)
