"""Real closed callback/reference traversal with one explicit inner join seam.

Fresh Final2/whole-snapshot/publisher producers and literal callback methods run.
The metadata carrier and _final_join's missing Scene/Login/Marker connection
are modeled, never full Feature admission or an Actor factory qualification.
The Primary Final2 producer's own role/binding is preserved throughout.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack, nullcontext
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import builtins
import io
import os
import socket
import subprocess
import unittest

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack
from feature_journeys.contract import VERSION
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import Client, Journal
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_final import validation_round
from ios.adapters.avatar_held_final import IOSAvatarHeldFinal
from ios.adapters.avatar_witness_publisher import AvatarWitnessPublisher
from ios.self_tests import test_ios_avatar_witness_publisher_composed as fixture
from ios.self_tests.test_ios_avatar_final import RUN, TICKET


class CallbackMetadataCarrier:
    """Explicit fixture metadata; no claim of IOSAvatarFeature.load admission."""
    snapshot_ledger=IOSAvatarFeature.snapshot_ledger
    keep=IOSAvatarFeature.keep
    kept=IOSAvatarFeature.kept
    terminal_witness_original=IOSAvatarFeature.terminal_witness_original
    terminal_live_proof=IOSAvatarFeature.terminal_live_proof
    lifetime_resources=staticmethod(IOSAvatarFeature.lifetime_resources)

    def __init__(self,owner):
        self.owner=owner;self.root,self.run,self.role=owner.root,owner.run,owner.role
        self.authority=owner.authority;self.lock=owner.locks[self.role]
        self.store=PrivateFeatureState(owner.store.path.with_name('avatar-witness-callback-carrier.json'))
        self.previous=None;self.state=dict(bindings=deepcopy(owner.bindings),snapshots=[],cleanup=[])
        self.joins=[];self.save()

    def save(self):
        self.lock.assert_held();need(self.store.read()==self.previous)
        value=dict(modeledAvatarCallbackCarrierVersion=1,runId=self.run,role=self.role,payload=pack([self.state]))
        self.store.write(value,self.previous);need(self.store.read()==value);self.previous=deepcopy(value)

    def _final_join(self,event,*,terminal):
        """Only the absent Scene/Login/Marker connection is modeled here.

        Real Final2 archive/quiet validation still reconstructs both original
        SDK subjects, clocks, files, independent pointer/Web data and authority.
        Empty modeled resources supply no product cleanup/held-end verdict.
        """
        need(terminal is True and event in self.state['cleanup']);self.joins.append(event['references'][-1]['index'])
        owner=self.owner
        archived=IOSAvatarHeldFinal.archive(self.kept(event['owner']),store=owner.store,root=owner.root,
            bindings=owner.bindings,run=owner.run,role=owner.role,locks=owner.locks,authority=owner.authority,inputs=owner.inputs)
        self.kept(event['inputs'])
        quiet=archived.quiet(event['references'],sequence=archived.record(event['references'][-1])['sequence'])
        public=dict(schemaVersion=1,contractVersion=VERSION,runId=self.run,sequence=quiet['sequence'],
            capturedEpochMs=quiet['capturedEpochMs'],state=deepcopy(SCENARIOS['avatar-people']['baseline']),
            artifacts=[],resources=[],lifecycle=deepcopy(quiet['lifecycle']))
        proof=dict(ticket=quiet['ticket'],public=public,acquisition=deepcopy(quiet['acquisition']))
        login={subject:[dict(heldResources=[])] for subject in ('primary','actor')}
        return proof,login,{subject:[] for subject in login}


class AvatarWitnessCallbackConnectionTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.AvatarWitnessPublisherComposedTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.f=self.base.f;self.native_fixture=self.base.fixture

    def produce(self):
        owner=self.native_fixture.owner();carrier=CallbackMetadataCarrier(owner);known={}
        journal=Journal(clock=self.f.host)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):
            self.assertEqual(RUN,journal.register('avatar-people'))
        journal.activate(RUN,TICKET);client=Client('https://controlled.invalid/feature-fixture/v1','a'*64)
        def transport(path,value=None,*,phase_nonce=None,**_kwargs):
            if path=='/runs/'+RUN+'/phase':return journal.phase(RUN,phase_nonce)
            if path=='/runs/'+RUN+'/samples':journal.publish(RUN,value);return {}
            self.assertEqual('/runs/'+RUN,path);return journal.snapshot(RUN)
        client.request=transport
        phase=PhaseFixtureReader(client,RUN,'avatar-people',epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0]);phase.status()
        store=PrivateFeatureState(owner.locks[carrier.role].path.with_name('phase-publication-avatar-people-'+RUN+'-actor.json'))
        def projection(value):need(digest(value) in known);return deepcopy(known[digest(value)])
        publisher=PhaseWitnessPublisher(store,owner.bindings[carrier.role],phase,owner.locks[carrier.role],lambda:True,projection,
            epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
        references=[];events=[];originals=[]
        for sequence in (1,2,3,4):
            if references:self.f.clock[0]+=1.7
            references.append(self.f.capture(owner,sequence))
            if sequence<3:continue
            event=dict(kind='final-observation',owner=carrier.keep(owner.previous),references=deepcopy(references),
                inputs=carrier.keep(dict(modeledMissingSceneLoginMarkerConnection=True)))
            carrier.state['cleanup'].append(event);carrier.save();events.append(event)
            original=dict(iosAvatarTerminalObservationReferenceVersion=1,reference=carrier.keep(event));originals.append(original)
            # Actual callback includes real Final2 archive/quiet; only the named
            # inner connection and metadata carrier are fixture models.
            known[digest(original)]=carrier.terminal_witness_original(original)
            self.assertEqual(sequence,publisher.publish(original))
        self.assertEqual(2,len(publisher.state['records']));self.assertEqual(2,len(journal.snapshot(RUN)['entries']))
        return owner,carrier,publisher,events,originals

    def test_actual_saved_reference_callback_and_publisher_reject_foreign_refs_before_the_modeled_join(self):
        owner,carrier,publisher,events,originals=self.produce();raw=publisher.store.read()
        # A real independently retained snapshot is not cleanup membership.
        foreign=carrier.keep(dict(events[0],unadmittedFixtureSnapshot=True))
        missing=dict(originals[0],reference=dict(index=len(carrier.state['snapshots'])+1,sha256='a'*64))
        changed=dict(originals[0],reference=dict(originals[0]['reference'],sha256='b'*64))
        unadmitted=dict(originals[0],reference=foreign)
        carrier.joins.clear()
        for name,value in (('missing',missing),('changed-reference',changed),('foreign-cleanup-snapshot',unadmitted)):
            with self.subTest(fault=name),self.assertRaises(NativeUIError):carrier.terminal_witness_original(value)
        self.assertEqual([],carrier.joins)
        roots={Path(item['root']) for item in owner.inputs.values()}
        roots.update(lock.path.parent for lock in owner.locks.values());roots.add(owner.root)
        roots={root for root in roots if not any(root!=parent and root.is_relative_to(parent) for parent in roots)}
        before=self.base.census(roots)
        native={role:len(case.f.calls) for role,case in self.f.cases.items()}
        web={role:len(boundary.commands) for role,boundary in self.native_fixture.web.items()}
        method=IOSAvatarHeldFinal._group;groups=[];paths=set()
        def grouped(subject,value):groups.append(value['sequence']);return method(subject,value)
        original_os_open,original_io_open,original_open=os.open,io.open,builtins.open
        def observed(value):
            if isinstance(value,int):return
            path=Path(os.fsdecode(value));path=path if path.is_absolute() else Path.cwd()/path
            if any(path.is_relative_to(root) for root in roots):paths.add(str(path))
        def open_fd(path,flags,*args,**kwargs):
            need(not flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            result=original_os_open(path,flags,*args,**kwargs);observed(path);return result
        def read_open(function,path,mode='r',*args,**kwargs):
            need(type(mode) is str and not any(flag in mode for flag in 'wax+'))
            result=function(path,mode,*args,**kwargs);observed(path);return result
        reports=[]
        with ExitStack() as stack:
            for subject,name in ((socket,'socket'),(subprocess,'Popen'),(PrivateFeatureState,'write'),(PrivateFeatureState,'discard')):
                stack.enter_context(patch.object(subject,name,self.base.forbidden))
            for name in ('unlink','remove','rename','replace','mkdir','rmdir'):
                stack.enter_context(patch.object(os,name,self.base.forbidden))
            stack.enter_context(patch.object(os,'open',open_fd))
            stack.enter_context(patch.object(io,'open',lambda path,mode='r',*a,**k:read_open(original_io_open,path,mode,*a,**k)))
            stack.enter_context(patch.object(builtins,'open',lambda path,mode='r',*a,**k:read_open(original_open,path,mode,*a,**k)))
            stack.enter_context(patch.object(IOSAvatarHeldFinal,'_group',grouped))
            for cls in (PhaseWitnessPublisher,AvatarWitnessPublisher):
                groups.clear();paths.clear();carrier.joins.clear()
                with read_scope(fresh=True) as membership:
                    with (validation_round() if cls is PhaseWitnessPublisher else nullcontext()):
                        state=cls.archive(raw,store=publisher.store,binding=publisher.binding,run=RUN,area='avatar-people',
                            fixture_url=publisher.url,phase_instance=publisher.instance,validate_original=carrier.terminal_witness_original)
                decoder_paths=set(paths);self.assertEqual([3,4],carrier.joins);self.assertEqual(before,self.base.census(roots))
                reports.append(dict(state=state,groups=list(groups),membership=set(membership),paths=decoder_paths))
        self.assertEqual([1,2,3,1,2,3,4],reports[0]['groups']);self.assertEqual([1,2,3,4],reports[1]['groups'])
        for key in ('state','membership','paths'):self.assertTrue(reports[0][key]);self.assertEqual(reports[0][key],reports[1][key])
        self.assertEqual(before,self.base.census(roots))
        self.assertEqual(native,{role:len(case.f.calls) for role,case in self.f.cases.items()})
        self.assertEqual(web,{role:len(boundary.commands) for role,boundary in self.native_fixture.web.items()})
        print('Actual callback host connection: missing/changed/unadmitted refs fail before join; Final2 groups 7 -> 4 with unchanged original reads/census',flush=True)


if __name__=='__main__':unittest.main()
