"""Shared protocol tests; UIKit/native/OS/SDK boundaries are explicit models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from contracts import validate_operation_arguments,validate_operation_result
from feature_journeys import terminal
from feature_journeys.engine import Journey
from self_tests import test_feature_journeys as common


class Boundary(common.Boundary):
    def __init__(self,fault=''):
        super().__init__('world-navigation');self.terminal_fault=fault
        self.ended=self.closed=False;self.stops=self.closes=0;self.terminal_calls=[]
        binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,targetFingerprint='c'*64,
            sessionSha256='d'*64,generation=1,processIdentity='31')
        self.descriptor=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area=self.area,runId=self.run,ticket=common.TICKET,
            roles={role:dict(binding=deepcopy(binding),originalSha256=('e' if role=='primary' else '9')*64,
                heldResources=[dict(resource='panel:cached-address-root',kind='qt-root',originalSha256='f'*64)]) for role in terminal.ROLES})

    def observe(self,fields):
        if self.ended:raise AssertionError('Ended native process cannot provide a live observation')
        return super().observe(fields)

    def invoke(self,operation,fields):
        if not operation.endswith('.terminal'):
            value=super().invoke(operation,fields)
            if operation.endswith('.cleanup'):
                self.resources=['panel:cached-address-root']
                if self.terminal_fault=='extra-resource':self.resources.append('file:unretired-output')
                if self.terminal_fault=='unrestored':self.state['location']='B'
            return value
        validate_operation_arguments(operation,fields);stage=fields['stage'];self.terminal_calls.append(stage)
        if stage=='inspect':
            self.descriptor['ticket']=self.ticket
            value=dict(stage=stage,description=deepcopy(self.descriptor))
            if self.terminal_fault=='foreign-description':value['description']['runId']='f'*32
        elif stage=='seal':
            if self.closed or self.ended:raise AssertionError('Live seal must precede process/fixture retirement')
            terminal.window(fields['samples'],self.descriptor)
            if self.terminal_fault=='lost-seal':raise OSError('Modeled lost live seal')
            self.seal=dict(featureTerminalSealVersion=1,description=deepcopy(self.descriptor),
                windowSha256=terminal.digest(fields['samples']),liveOriginalSha256='1'*64)
            value=dict(stage=stage,seal=deepcopy(self.seal))
            if self.terminal_fault=='changed-window':value['seal']['windowSha256']='2'*64
        else:
            if not self.closed or self.ended:raise AssertionError('Normal Stop requires the retired fixture and once delivery')
            self.stops+=1;self.ended=True
            if self.terminal_fault=='lost-stop':raise OSError('Modeled lost final Stop result')
            start=self.epoch();mono=self.clock;self.clock+=3.1
            os=dict(source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',instance='3'*32,
                processId=31,samples=3,originalSha256='4'*64,hostAfterFirstEpochMs=start,hostBeforeLastEpochMs=self.epoch(),
                hostAfterFirstMonotonic=mono,hostBeforeLastMonotonic=self.clock,osAfterFirstEpochMs=100000,
                osBeforeLastEpochMs=103100,osAfterFirstMonotonicMs=0,osBeforeLastMonotonicMs=3100)
            roles={role:dict(binding=deepcopy(row['binding']),heldOriginalSha256=row['originalSha256'],stopOriginalSha256='5'*64,
                osAbsence=deepcopy(os),sdkDeletionOriginalSha256='6'*64,archiveSha256='7'*64) for role,row in self.descriptor['roles'].items()}
            roles['actor']['osAbsence']['originalSha256']='a'*64
            value=dict(stage=stage,end=dict(featureTerminalEndVersion=1,seal=deepcopy(self.seal),roles=roles))
            if self.terminal_fault=='short-os-quiet':value['end']['roles']['actor']['osAbsence']['osBeforeLastEpochMs']=102999
            if self.terminal_fault=='foreign-pid':value['end']['roles']['actor']['osAbsence']['processId']=32
            if self.terminal_fault=='second-sdk-delete':value['end']['roles']['actor']['sdkDeletionOriginalSha256']='8'*64
            if self.terminal_fault=='borrowed-os':value['end']['roles']['actor']['osAbsence']['originalSha256']='4'*64
        return validate_operation_result(operation,value)

    def close(self):self.closes+=1;self.closed=True

    def journey(self,*,profile=terminal.PROFILE):
        return Journey(self.area,self.run,'http://controlled.test/feature-fixture/v1/runs/'+self.run+'/',
            invoke=self.invoke,witness=self.witness,activate=self.activate,read_artifact=self.files.__getitem__,
            image_policy=common.POLICY,continuity=self.continuity,monotonic=lambda:self.clock,epoch_ms=self.epoch,
            sleep=self.sleep,report=self.reports.append,navigation_source=self.navigation_source,
            terminal_profile=profile,retire_fixture=self.close)


class FeatureTerminalTests(unittest.TestCase):
    def test_live_restoration_precedes_once_stop_and_no_live_observation_follows_process_end(self):
        model=Boundary();journey=model.journey();journey.execute()
        self.assertEqual(['inspect','seal','finish'],model.terminal_calls)
        self.assertEqual((1,1),(model.stops,model.closes));self.assertTrue(model.ended)
        report=model.reports[-1];self.assertTrue(report['sequenceCompleted']);self.assertTrue(report['cleanupSucceeded'])
        self.assertTrue(all(row['resources']==['panel:cached-address-root'] for row in report['samples'] if row['phase']=='cleanup-restored-baseline'))
        self.assertEqual(journey.terminal_seal,report['terminalRetirement']['end']['seal'])
        self.assertEqual(2,sum(operation.endswith('.cleanup') for operation,_ in model.actions))

    def test_default_v16_cleanup_still_refuses_a_hidden_live_root(self):
        model=Boundary()
        with self.assertRaises(AssertionError):model.journey(profile=None).execute()
        self.assertEqual([],model.terminal_calls);self.assertEqual(0,model.stops)
        self.assertNotIn('terminalRetirement',model.reports[-1]);self.assertFalse(model.reports[-1]['cleanupSucceeded'])

    def test_foreign_or_unsealed_or_not_restored_originals_cannot_authorize_stop(self):
        for fault in ('extra-resource','unrestored','foreign-description','changed-window','lost-seal'):
            model=Boundary(fault)
            with self.subTest(fault=fault),self.assertRaises((ValueError,AssertionError,OSError)):model.journey().execute()
            self.assertEqual(0,model.stops);self.assertEqual(0,model.closes)
            self.assertFalse(model.reports[-1]['cleanupSucceeded'])

    def test_lost_stop_and_wrong_or_short_os_absence_never_receive_a_green_result_or_a_repeat(self):
        for fault in ('lost-stop','short-os-quiet','foreign-pid','second-sdk-delete','borrowed-os'):
            model=Boundary(fault)
            with self.subTest(fault=fault),self.assertRaises((ValueError,OSError)):model.journey().execute()
            self.assertEqual(1,model.stops);self.assertEqual(1,model.terminal_calls.count('finish'))
            self.assertFalse(model.reports[-1]['sequenceCompleted'])

    def test_window_rejects_replayed_actor_relabelled_resources_state_change_and_short_interval(self):
        model=Boundary();journey=model.journey();journey.execute();rows=journey.terminal_samples
        self.assertEqual(rows,terminal.window(rows,journey.terminal_descriptor))
        for fault in ('actor','resource','state','ticket','short'):
            values=deepcopy(rows)
            if fault=='actor':values[-1]['actor']['actorSequence']=values[0]['actor']['actorSequence']
            elif fault=='resource':values[-1]['primary']['resources']=[]
            elif fault=='state':values[-1]['primary']['state']['location']='B'
            elif fault=='ticket':values[-1]['actor']['ticket']='e'*32
            else:values=values[:3]
            with self.subTest(fault=fault),self.assertRaises(ValueError):terminal.window(values,journey.terminal_descriptor)

    def test_closed_profile_rejects_arbitrary_classes_paths_versions_and_extra_verdicts(self):
        model=Boundary()
        for key,value in (('kind','file'),('resource','file:retained'),('originalSha256','not-a-sha')):
            descriptor=deepcopy(model.descriptor);descriptor['roles']['primary']['heldResources'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):terminal.description(descriptor)
        with self.assertRaises(ValueError):model.journey(profile='unknown')
        for fields in (dict(contractVersion=16,runId=model.run,stage='inspect'),
            dict(contractVersion=1,runId=model.run,stage='inspect',passed=True)):
            with self.assertRaises(ValueError):validate_operation_arguments('feature.world-navigation.terminal',fields)


if __name__=='__main__':unittest.main()
