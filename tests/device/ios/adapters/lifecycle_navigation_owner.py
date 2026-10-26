"""Navigation specialization of the existing durable one-send input owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters import lifecycle_navigation_controls as controls,lifecycle_navigation_inputs as inputs
from ios.adapters.snapshot_input_owner import SnapshotInputOwner


def reference(value,control):
    exact(value,{'scope','control','root'});scope=value['scope'];row=value['control']
    exact(scope,{'processId','instance','sampleEpochMs','elapsedMs','sequence'})
    need(integer(scope['processId'],1) and integer(scope['sampleEpochMs'],1) and integer(scope['elapsedMs']) and integer(scope['sequence']))
    inputs.uuid(scope['instance']);exact(row,{'id','token','enabled','focused'})
    need(row['id']==control and row['enabled'] is True and type(row['focused']) is bool);inputs.uuid(row['token'])
    controls.metadata(value['root']);need(value['root']['controlId']==control and value['root']['inputReady']);return row


class LifecycleNavigationOwner(SnapshotInputOwner):
    _owner_key='iosLifecycleNavigationOwnerVersion'
    _proof_namespace='lifecycle-navigation-proof'
    _proof_schema='lifecycleNavigationProof'
    _reference=staticmethod(reference)
    _input_source=inputs
    _root_is_stable=False

    @staticmethod
    def store_name(role):return 'ios-lifecycle-'+role+'-navigation.json'

    @staticmethod
    def root(event):return deepcopy(event['reference']['root'])

    def check_current(self,event):
        before=event['reference'];after=controls.project(self.native.capture(),event['controlId'])
        need(same(before['control'],after['control']) and same(before['root'],after['root'])
             and all(same(before['scope'][key],after['scope'][key]) for key in ('instance','processId','sequence'))
             and after['scope']['elapsedMs']>=before['scope']['elapsedMs'] and after['scope']['sampleEpochMs']>=before['scope']['sampleEpochMs'])
