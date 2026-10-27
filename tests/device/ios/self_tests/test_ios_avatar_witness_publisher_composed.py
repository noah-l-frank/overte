"""Fresh Final2 originals through the actual Avatar publisher decode boundary.

The fixture's native/SDK/GPU clocks and the publisher projection/transport are
explicit host models. Real Final2 producers, journal/phase producers, durable
publisher records and both historical decoder paths remain unchanged. This is
neither the complete Avatar terminal callback nor a timing/device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack, nullcontext
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import builtins
import hashlib
import io
import os
import socket
import stat
import subprocess
import unittest

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from feature_journeys.contract import VERSION
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import Client, Journal
from ios.adapters.avatar_final import validation_round
from ios.adapters.avatar_held_final import IOSAvatarHeldFinal
from ios.adapters.avatar_witness_publisher import AvatarWitnessPublisher
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.self_tests.test_ios_avatar_final import RUN, TICKET
from ios.self_tests.test_ios_avatar_held_final import AvatarHeldFinalTests


class AvatarWitnessPublisherComposedTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AvatarHeldFinalTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);self.f=self.fixture.f

    @staticmethod
    def forbidden(*_args,**_kwargs):
        raise AssertionError('Historical comparison cannot perform live transport or writes')

    def census(self,roots):
        result={}
        for root in roots:
            for path in (root,*sorted(root.rglob('*'))):
                before=path.lstat();self.assertTrue(stat.S_ISDIR(before.st_mode) or stat.S_ISREG(before.st_mode))
                raw=None if stat.S_ISDIR(before.st_mode) else hashlib.sha256(path.read_bytes()).hexdigest()
                after=path.lstat();self.assertEqual(EmoteOriginalLease.signature(before),EmoteOriginalLease.signature(after))
                result[str(path)]=(EmoteOriginalLease.signature(after),raw)
        return result

    def produce(self):
        owner=self.fixture.owner();known={}
        journal=Journal(clock=self.f.host)
        # Seed only the real producer's fresh run identity to join this fixture.
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):
            self.assertEqual(RUN,journal.register('avatar-people'))
        journal.activate(RUN,TICKET)
        client=Client('https://controlled.invalid/feature-fixture/v1','a'*64)
        def transport(path,value=None,*,phase_nonce=None,**_kwargs):
            if path=='/runs/'+RUN+'/phase':return journal.phase(RUN,phase_nonce)
            if path=='/runs/'+RUN+'/samples':journal.publish(RUN,value);return {}
            self.assertEqual('/runs/'+RUN,path);return journal.snapshot(RUN)
        client.request=transport
        phase=PhaseFixtureReader(client,RUN,'avatar-people',epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
        phase.status();store=PrivateFeatureState(self.f.locks['actor'].path.with_name('phase-publication-avatar-people-'+RUN+'-actor.json'))
        def modeled_projection(value):
            need(digest(value) in known);return deepcopy(known[digest(value)])
        publisher=PhaseWitnessPublisher(store,owner.bindings['actor'],phase,self.f.locks['actor'],lambda:True,
            modeled_projection,epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
        for sequence in (1,2):
            if sequence>1:self.f.clock[0]+=1.7
            reference=self.f.capture(owner,sequence)
            original=dict(modeledFinalPublisherOriginalVersion=1,final=deepcopy(owner.previous),reference=reference)
            epoch=self.f.host();now=self.f.clock[0]
            public=dict(schemaVersion=1,contractVersion=VERSION,runId=RUN,sequence=sequence,capturedEpochMs=epoch,
                state=deepcopy(SCENARIOS['avatar-people']['baseline']),artifacts=[],resources=[],
                lifecycle=dict(backgrounds=0,activations=0,launches=1))
            known[digest(original)]=dict(ticket=TICKET,public=public,acquisition=dict(hostBeforeEpochMs=epoch,
                hostAfterEpochMs=epoch,hostBeforeMonotonic=now,hostAfterMonotonic=now))
            self.assertEqual(sequence,publisher.publish(original))
        self.assertEqual(2,len(publisher.state['records']));self.assertEqual(2,len(journal.snapshot(RUN)['entries']))
        return owner,publisher,known

    def test_actual_avatar_decode_reuses_old_groups_and_preserves_originals_and_read_membership(self):
        owner,publisher,known=self.produce();raw=publisher.store.read()
        roots={Path(config['root']) for config in owner.inputs.values()}
        roots.update(lock.path.parent for lock in owner.locks.values());roots.add(owner.root)
        roots={root for root in roots if not any(root!=parent and root.is_relative_to(parent) for parent in roots)}
        before=self.census(roots)
        native={role:len(case.f.calls) for role,case in self.f.cases.items()}
        web={role:len(boundary.commands) for role,boundary in self.fixture.web.items()}
        group_method=IOSAvatarHeldFinal._group;groups=[];callbacks=[];actual_reads=set()
        def grouped(subject,value):groups.append(value['sequence']);return group_method(subject,value)
        def original(value):
            need(digest(value) in known);callbacks.append(value['reference']['index'])
            archived=IOSAvatarHeldFinal.archive(value['final'],store=owner.store,root=owner.root,bindings=owner.bindings,
                run=owner.run,role=owner.role,locks=owner.locks,authority=owner.authority,inputs=owner.inputs)
            need(any(row['reference']==value['reference'] for row in archived.state['rows']));archived.record(value['reference'])
            return deepcopy(known[digest(value)])
        def observed_path(value):
            if isinstance(value,int):return
            path=Path(os.fsdecode(value))
            if not path.is_absolute():path=Path.cwd()/path
            if any(path.is_relative_to(root) for root in roots):actual_reads.add(str(path))
        os_open=os.open;io_open=io.open;builtin_open=builtins.open
        def open_fd(path,flags,*args,**kwargs):
            need(not flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            result=os_open(path,flags,*args,**kwargs);observed_path(path);return result
        def read_open(function,path,mode='r',*args,**kwargs):
            need(type(mode) is str and not any(flag in mode for flag in 'wax+'))
            result=function(path,mode,*args,**kwargs);observed_path(path);return result
        reports=[]
        with ExitStack() as stack:
            for subject,name in ((socket,'socket'),(subprocess,'Popen'),(PrivateFeatureState,'write'),(PrivateFeatureState,'discard')):
                stack.enter_context(patch.object(subject,name,self.forbidden))
            for name in ('unlink','remove','rename','replace','mkdir','rmdir'):
                stack.enter_context(patch.object(os,name,self.forbidden))
            stack.enter_context(patch.object(os,'open',open_fd))
            stack.enter_context(patch.object(io,'open',lambda path,mode='r',*a,**k:read_open(io_open,path,mode,*a,**k)))
            stack.enter_context(patch.object(builtins,'open',lambda path,mode='r',*a,**k:read_open(builtin_open,path,mode,*a,**k)))
            stack.enter_context(patch.object(IOSAvatarHeldFinal,'_group',grouped))
            for cls in (PhaseWitnessPublisher,AvatarWitnessPublisher):
                groups.clear();callbacks.clear();actual_reads.clear()
                with read_scope(fresh=True) as membership:
                    with (validation_round() if cls is PhaseWitnessPublisher else nullcontext()):
                        state=cls.archive(raw,store=publisher.store,binding=publisher.binding,run=RUN,area='avatar-people',
                            fixture_url=publisher.url,phase_instance=publisher.instance,validate_original=original)
                paths_read_by_decoder=set(actual_reads)
                self.assertEqual(before,self.census(roots));self.assertEqual([1,2],callbacks)
                reports.append(dict(state=state,groups=list(groups),membership=set(membership),actualReadPaths=paths_read_by_decoder))
        self.assertEqual([1,1,2],reports[0]['groups']);self.assertEqual([1,2],reports[1]['groups'])
        self.assertEqual(reports[0]['state'],reports[1]['state'])
        self.assertTrue(reports[0]['membership']);self.assertEqual(reports[0]['membership'],reports[1]['membership'])
        self.assertTrue(reports[0]['actualReadPaths']);self.assertEqual(reports[0]['actualReadPaths'],reports[1]['actualReadPaths'])
        self.assertEqual(before,self.census(roots))
        self.assertEqual(native,{role:len(case.f.calls) for role,case in self.f.cases.items()})
        self.assertEqual(web,{role:len(boundary.commands) for role,boundary in self.fixture.web.items()})
        print('Avatar publisher host seam: actual Final2 groups 3 -> 2; identical state, membership, read paths and original census',flush=True)


if __name__=='__main__':unittest.main()
