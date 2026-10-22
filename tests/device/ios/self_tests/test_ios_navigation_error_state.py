"""Actual provider joins and validators; native Qt modal/SDK clocks modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest

from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY
from feature_journeys.fixtures import context
from ios.adapters import navigation_error_state as measured
from ios.self_tests.test_ios_navigation_dialogs import Boundary,INPUTS,ORIGIN,TICKET,RUN
from ios.self_tests.test_ios_navigation_ui import observed,root as address_root
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from self_tests.test_completed_frame_lease import BINDING

BINDING=dict(BINDING,sourceRevision=INPUTS['sourceRevision'])


def join(originals):
    start=originals['dialogs']['clockBefore']['epochMs']-1
    end=max(originals['dialogs']['clockAfter']['epochMs'],originals['replies']['capturedEpochMs'],originals['ui']['sampleEpochMs'])+1
    return dict(clockJoinVersion=1,hostBeforeEpochMs=1_000_000.,hostAfterEpochMs=1_000_000.+end-start,
        hostBeforeMonotonic=10.,hostAfterMonotonic=10.+(end-start)/1000,nativeBefore=global_packet(start,1),
        nativeAfter=global_packet(end,2),originalsSha256=digest(originals),
        sourceTimes=[dict(source=key,field=field,epochMs=originals[key][field])
            for key,field in (('replies','capturedEpochMs'),('ui','sampleEpochMs'))])


class Harness:
    def __init__(self,*,missing=True,provider=None):
        self.source=Boundary();self.reader=self.source.reader();self.sequence=0
        self.provider=provider or NavigationResources(INPUTS,clock_ms=lambda:self.source.epoch()+86400000)
        if provider is None:self.provider.provision(RUN);self.provider.activate(RUN,TICKET)
        self.admission=dict(runId=RUN,ticket=TICKET,inputs=INPUTS,origin=ORIGIN,nativeAfterEpochMs=self.source.epoch(),
            providerAfterEpochMs=self.provider.snapshot(RUN)['capturedEpochMs'],afterEvent=0)
        self.proof=None
        if missing:
            with self.provider.response(DIRECTORY+'/'+context(RUN)['hidden'],'') as response:_code,_raw,id=response
            self.source.create(id)
            originals,clock=self.read()
            self.proof=measured.missing_proof(BINDING,originals,clock,self.provider.snapshot(RUN),self.admission)

    def read(self,*,address=False):
        packet=self.reader.read(RUN);self.sequence+=1;self.source.clock+=.001
        if self.source.native_error is not None:replies=self.source.replies()
        else:
            replies=dict(navigationReplyVersion=1,commandId='ios-'+str(self.sequence%10)*32,runId=RUN,instance='e'*32,
                sequence=self.sequence,processId=42,capturedEpochMs=self.source.epoch()+1,currentLookupGeneration=2,
                currentLookupActive=True,events=[])
        replies['sequence']=self.sequence
        self.source.clock+=.003;ui=observed(*([address_root()] if address else []))
        ui.update(sampleEpochMs=self.source.epoch(),elapsedMs=round(self.source.clock*1000),
            navigationDialogControlsVersion=1,navigationDialogSourceSequence=self.sequence)
        if self.source.rows and self.source.rows[0]['dialog'] is not None and self.source.rows[0]['dialog']['visible']:
            ui['controls']=[dict(row,frame=dict(x=10,y=20,width=300,height=40)) for row in self.source.controls()['controls']]
        originals=dict(dialogs=packet,replies=replies,ui=ui);return originals,join(originals)

    def project(self,sample,**changes):
        options=dict(missing=self.proof);options.update(changes)
        return measured.compose(RUN,BINDING,*sample,**options)


class NavigationErrorStateTests(unittest.TestCase):
    def test_original_visible_owned_error_keeps_server_native_modal_and_input_clocks(self):
        h=Harness();sample=h.read();before=deepcopy(sample);proof=deepcopy(h.proof);result=h.project(sample)
        self.assertEqual(dict(error='not-found',addressDialog=False),result['fields'])
        self.assertFalse(result['ownedDialogDrained']);self.assertEqual(before,sample);self.assertEqual(proof,h.proof)
        self.assertGreater(h.proof['joined']['http']['completedEpochMs'],h.proof['joined']['nativeError']['callbackEpochMs']+80000000)

    def test_no_owned_error_is_not_a_vacuous_owned_destruction_proof(self):
        h=Harness(missing=False);result=h.project(h.read())
        self.assertEqual('none',result['fields']['error']);self.assertIsNone(result['ownedDialogDrained'])
        self.assertIsNone(result['missingProofSha256'])

    def test_native_callback_without_retained_original_modal_proof_is_unresolved(self):
        h=Harness()
        with self.assertRaises(NativeUIError):h.project(h.read(),missing=None)
        h.source.respond();h.source.destroy()
        with self.assertRaises(NativeUIError):h.project(h.read(),missing=None)

    def test_response_hiding_and_partial_deletion_do_not_mean_dialog_and_listener_destroyed(self):
        for fault in ('hidden','ack-only','response','dialog-only','listener-only'):
            h=Harness()
            if fault=='hidden':h.source.rows[0]['dialog']['visible']=False
            elif fault!='ack-only':h.source.respond()
            if fault=='dialog-only':h.source.destroy(listener=False)
            elif fault=='listener-only':h.source.destroy(dialog=False)
            sample=h.read()
            if fault=='ack-only':
                self.assertEqual('not-found',h.project(sample)['fields']['error'])
            else:
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.project(sample)

    def test_actual_OK_and_both_destructions_clear_error_without_erasing_old_callback(self):
        h=Harness();proof=deepcopy(h.proof);h.source.respond();h.source.destroy();h.provider.activate(RUN,'f'*32)
        sample=h.read();result=h.project(sample)
        self.assertEqual(dict(error='none',addressDialog=False),result['fields']);self.assertTrue(result['ownedDialogDrained'])
        self.assertEqual(proof,h.proof);self.assertEqual(TICKET,h.proof['provider']['ticket'])
        self.assertEqual(proof['joined']['nativeError'],sample[0]['replies']['events'][0])

    def test_Go_To_still_open_after_OK_requires_separate_normal_close(self):
        h=Harness();h.source.respond();h.source.destroy()
        result=h.project(h.read(address=True));self.assertEqual(dict(error='none',addressDialog=True),result['fields'])
        self.assertTrue(result['ownedDialogDrained']);self.assertFalse(h.project(h.read())['fields']['addressDialog'])

    def test_wrong_response_cannot_pass_even_with_actual_destruction(self):
        h=Harness();h.source.respond(1);h.source.destroy()
        with self.assertRaises(NativeUIError):h.project(h.read())

    def test_visible_old_modal_cannot_borrow_a_new_current_lookup_generation(self):
        h=Harness();originals,_clock=h.read();originals['replies']['currentLookupGeneration']+=1
        with self.assertRaises(NativeUIError):h.project((originals,join(originals)))

    def test_foreign_unknown_or_replaced_source_cannot_be_adopted(self):
        for fault in ('dialog-birth','reply-birth','ui-birth','history','foreign','pid','unselected','incomplete','text','control'):
            h=Harness();originals,_clock=h.read()
            if fault=='dialog-birth':originals['dialogs']['instance']='f'*32
            elif fault=='reply-birth':originals['replies']['instance']='f'*32
            elif fault=='ui-birth':originals['ui']['instance']='11111111-2222-3333-4444-777777777777'
            elif fault=='history':originals['replies']['events']=[]
            elif fault=='foreign':originals['dialogs']['foreignModals']=1
            elif fault=='pid':originals['dialogs']['processId']=43
            elif fault=='unselected':originals['dialogs']['dialogs'][0]['dialog']['qmlSource']='qrc:/qml/OtherDialog.qml'
            elif fault=='incomplete':originals['dialogs']['complete']=False
            elif fault=='text':originals['dialogs']['dialogs'][0]['dialog']['text']='Another error'
            else:originals['ui']['controls']=[]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.project((originals,join(originals)))

    def test_new_unknown_callback_is_not_hidden_after_the_first_dialog_drains(self):
        h=Harness();h.source.respond();h.source.destroy();originals,_clock=h.read()
        event=deepcopy(originals['replies']['events'][0]);event.update(sequence=2,eventId='b'*32,responseId='c'*32)
        originals['replies']['events'].append(event)
        with self.assertRaises(NativeUIError):h.project((originals,join(originals)))

    def test_frozen_proof_ticket_barrier_and_materialized_modal_cannot_be_relabelled(self):
        for fault in ('ticket','barrier','modal','hash','candidate'):
            h=Harness()
            if fault=='ticket':h.proof['admission']['ticket']='f'*32
            elif fault=='barrier':h.proof['admission']['nativeAfterEpochMs']+=1000
            elif fault=='modal':h.proof['joined']['dialog']['text']='Borrowed outcome'
            elif fault=='candidate':h.proof['binding']['artifactSha256']='f'*64
            else:h.proof['originals']['ui']['elapsedMs']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.project(h.read())

    def test_original_clock_bracket_and_lifecycle_are_required_for_current_observation(self):
        for fault in ('hash','outside','lifecycle','input-cursor'):
            h=Harness();originals,clock=h.read()
            if fault=='hash':originals['ui']['elapsedMs']+=1
            elif fault=='outside':clock['nativeBefore']['capturedEpochMs']=clock['nativeBefore']['requestedEpochMs']=originals['ui']['sampleEpochMs']
            elif fault=='input-cursor':originals['ui']['navigationDialogSourceSequence']=0;clock=join(originals)
            else:clock['nativeAfter']['lifecycle']['activations']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.project((originals,clock))

    def test_historical_validation_preserves_original_events_and_proof_after_phase_changes(self):
        h=Harness();saved=json.dumps(h.proof,sort_keys=True);h.source.clock+=100
        h.provider.activate(RUN,'f'*32)
        measured.validate_proof(h.proof,BINDING,RUN)
        self.assertEqual(saved,json.dumps(h.proof,sort_keys=True))
