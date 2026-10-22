"""Actual authorized HTTP/legacy files; scene native decoder is modeled here."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_retirement_publisher import PhaseRetirementPublisher,PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from adapters.script_feature.history import pack
from feature_journeys.retirement_receipts import PhaseRetirementJournal,SCENE_CLASSES,SCENE_STAGE,body,binding_from_context
from self_tests.test_completed_frame_lease import BINDING
from self_tests.test_phase_retirement_publisher import PhaseRetirementTests


class AvatarSceneRetirementTests(unittest.TestCase):
    def setUp(self):
        self.f=PhaseRetirementTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.attach('avatar-people')

    def scene(self,sequence=1):
        original=self.f.original(sequence);derived=self.f.known[digest(original)];public=derived.pop('public')
        derived['scene']=dict(sceneRetirementVersion=1,runId=self.f.run,sequence=sequence,capturedEpochMs=public['capturedEpochMs'],
            retired=list(SCENE_CLASSES),remaining=['account-session'],lifecycle=public['lifecycle'])
        return original

    def reader(self,stage):
        template=self.f.primary_reader()
        return PhaseRetirementReader(PrivateFeatureState(self.f.root/('retirement-'+stage+'-reader.json')),template.binding,
            template.phase,template.guard,template.admitted_original,template.validate_admission,
            epoch_ms=lambda:self.f.now,monotonic=lambda:10.1,stage=stage)

    def test_real_scene_receipt_is_separate_from_complete_and_uses_no_facts_channel(self):
        with self.f.lock.held():
            owner=self.f.owner();self.assertEqual(1,owner.publish(self.scene()))
        observed=self.f.adapter.request('/runs/'+self.f.run+'/retirements');entry=observed['entries'][0]
        self.assertEqual(2,observed['phaseRetirementJournalVersion']);self.assertEqual(SCENE_STAGE,entry['stage'])
        self.assertNotIn('cleanup',entry);self.assertNotIn('resources',entry['scene'])
        self.assertEqual(['account-session'],entry['scene']['remaining'])
        for forbidden in ('state','artifacts','facts','connection','principal','avatar','username'):
            self.assertNotIn(forbidden,entry['scene'])
        self.assertEqual(entry,self.reader(SCENE_STAGE).read()['entry'])
        with self.assertRaises(PublicationPending):self.f.primary_reader().read()
        with self.f.lock.held():self.assertEqual(2,self.f.owner().publish(self.f.original(2)))
        self.assertEqual('complete',self.f.primary_reader().read()['entry']['stage'])
        with self.assertRaises(PublicationPending):self.reader(SCENE_STAGE).read()

    def test_lost_actual_scene_POST_reply_resolves_without_republication_or_retiring_accounts(self):
        with self.f.lock.held():
            original=self.scene();owner=self.f.owner();calls,request=self.f.posts('lost-after')
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):owner.publish(original)
            again,request=self.f.posts('normal')
            with patch.object(self.f.actor,'request',side_effect=request):
                self.assertTrue(self.f.owner().resolve());self.assertEqual(1,self.f.owner().publish(original))
            self.assertEqual(1,len(calls));self.assertEqual([],again)
        self.assertEqual(['account-session'],self.reader(SCENE_STAGE).read()['entry']['scene']['remaining'])

    def test_unknown_uncommitted_scene_does_not_send_a_second_scene_or_complete(self):
        with self.f.lock.held():
            original=self.scene();calls,request=self.f.posts('lost-before')
            with patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):self.f.owner().publish(original)
            again,request=self.f.posts('normal')
            with patch.object(self.f.actor,'request',side_effect=request):
                for value in (original,self.f.original(2)):
                    with self.assertRaises(PublicationPending):self.f.owner().publish(value)
            self.assertEqual(1,len(calls));self.assertEqual([],again)

    def test_scene_strict_grammar_cannot_claim_account_or_whole_cleanup(self):
        with self.f.lock.held():_derived,valid=self.f.owner().original(self.scene())
        variants=[]
        for edit in ({'remaining':[]},{'remaining':['account-session','other']},{'resources':[]},{'retired':list(SCENE_CLASSES)+['account-session']},
                     {'sceneRetirementVersion':True},{'sequence':True}):
            value=deepcopy(valid);value['scene'].update(edit);variants.append(value)
        for edit in ({'stage':'complete'},{'phaseRetirementVersion':1},{'area':'emotes'},{'cleanup':{}},{'stage':'anything'}):
            value=deepcopy(valid);value.update(edit);variants.append(value)
        for value in variants:
            with self.subTest(value=value),self.assertRaises(ValueError):body(value)
        with self.f.lock.held():
            self.f.owner().publish(self.scene())
            with self.assertRaises(ValueError):self.f.actor.request('/runs/'+self.f.run+'/retirements',dict(valid,actorSequence=2,scene=dict(valid['scene'],sequence=2)))

    def test_scene_is_never_admitted_after_complete_or_from_reader_credentials(self):
        with self.f.lock.held():
            self.f.owner().publish(self.f.original())
            _derived,value=self.f.owner().original(self.scene(2))
        for client in (self.f.actor,self.f.reader,self.f.adapter):
            with self.subTest(client=client.token[0]),self.assertRaises(ValueError):client.request('/runs/'+self.f.run+'/retirements',value)

    def test_historical_journal_rejects_rehashed_duplicate_or_reordered_scene(self):
        with self.f.lock.held():
            owner=self.f.owner();owner.publish(self.scene());valid=self.f.server.phase_retirements.snapshot(self.f.run)
            _derived,complete=owner.original(self.f.original(2))
            first=deepcopy(valid['entries'][0]);duplicate=deepcopy(first)
            duplicate.update(sequence=2,actorSequence=2);duplicate['scene']['sequence']=2
            duplicate['receiptSha256']=digest({key:value for key,value in duplicate.items() if key not in ('sequence','receivedEpochMs','receiptSha256')})
            bad=deepcopy(valid);bad['entries'].append(duplicate)
            with self.assertRaises((ValueError,RuntimeError)):owner.journal(bad)
            complete['actorSequence']=1;complete['cleanup']['sequence']=1
            bad['entries']=[dict(complete,sequence=1,receivedEpochMs=self.f.now,receiptSha256=digest(complete)),duplicate]
            with self.assertRaises((ValueError,RuntimeError)):owner.journal(bad)

    def test_v1_original_writer_files_and_wire_are_read_without_conversion_or_http(self):
        # An independent literal legacy writer. It does not call current
        # Publisher.original/envelope/store_record or remove v2-only fields.
        f=self.f
        class LegacyJournal(PhaseRetirementJournal):
            def snapshot(self,run):
                with self.journal.lock:
                    current=self.journal.runs[run]
                    return dict(phaseRetirementJournalVersion=1,runId=run,area=current['area'],phaseInstance=self.journal.phase_instance,
                        ticket=current['ticket'],sampleEpochMs=self.journal.clock(),entries=deepcopy(self.runs.get(run,[])))
        f.server.phase_retirements=LegacyJournal(f.server.journal)
        original=f.original();derived=f.validate_original(original);public=derived['public'];retirement=derived['retirement']
        wire=dict(phaseRetirementVersion=1,runId=f.run,area=f.area,phaseInstance=f.phase.previous['instance'],ticket=f.ticket,
            role='actor',actorSequence=1,binding=binding_from_context(BINDING),originalSha256=retirement['originalSha256'],
            cleanup=dict(schemaVersion=1,contractVersion=16,runId=f.run,sequence=1,capturedEpochMs=public['capturedEpochMs'],resources=[],lifecycle=deepcopy(public['lifecycle'])),
            acquisition=deepcopy(derived['acquisition']),quiet=deepcopy(retirement['quiet']),provenance=deepcopy(retirement['provenance']))
        before=f.phase.status();f.actor.request('/runs/'+f.run+'/retirements',wire);journal=f.actor.request('/runs/'+f.run+'/retirements');after=f.phase.status(before)
        clock=dict(hostBeforeEpochMs=f.now,hostAfterEpochMs=f.now,hostBeforeMonotonic=10.1,hostAfterMonotonic=10.1)
        intent=dict(ordinal=1,original=original,derived=derived,body=wire,phase='issued')
        row=dict(intent=intent,phaseBefore=before,phaseAfter=after,acquisition=clock,mode='published',journal=journal,entry=journal['entries'][0])
        envelope=dict(binding=deepcopy(BINDING),runId=f.run,area=f.area,fixtureUrl=f.url,phaseInstance=before['instance'])
        record=dict(phaseRetirementPublicationRecordVersion=1,**envelope,payload=pack([row]));record_store=PrivateFeatureState(f.root/('phase-retirement-'+f.area+'-'+f.run+'-actor-1.json'))
        record_store.write(record,None)
        metadata=dict(phaseRetirementPublisherVersion=1,**envelope,payload=pack([dict(records=[dict(ordinal=1,sha256=digest(record))],pending=None)]))
        store=PrivateFeatureState(f.root/('phase-retirement-'+f.area+'-'+f.run+'-actor.json'));store.write(metadata,None)
        with f.lock.held(),patch.object(f.actor,'request',side_effect=AssertionError('Legacy original archive is file-only')):
            archived=PhaseRetirementPublisher.archive(metadata,store=store,binding=BINDING,run=f.run,area=f.area,
                fixture_url=f.url,phase_instance=before['instance'],validate_original=f.validate_original)
            owner=f.owner();self.assertEqual(wire,owner.load(archived['records'][0])['intent']['body'])
        reader=f.primary_reader();first=reader.phase.status();journal=reader.phase.client.request('/runs/'+f.run+'/retirements');last=reader.phase.status(first)
        receipt=dict(phaseBefore=first,journal=journal,phaseAfter=last,acquisition=clock,entry=journal['entries'][0]);receipt['sha256']=digest(receipt)
        legacy_reader=dict(phaseRetirementReaderVersion=1,runId=f.run,area=f.area,phaseInstance=first['instance'],fixtureUrl=f.url,
            binding=reader.binding,admittedOriginal=reader.admitted_original,payload=pack([dict(records=[receipt])]))
        reader.store.write(legacy_reader,None)
        restored=f.primary_reader();self.assertEqual(wire,{key:restored.state['records'][0]['entry'][key] for key in wire})
        self.assertEqual(legacy_reader,reader.store.read());self.assertEqual(metadata,store.read());self.assertEqual(record,record_store.read())


if __name__=='__main__':unittest.main()
