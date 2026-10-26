"""Closed Lifecycle profile of the existing one-send normal-input owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters import lifecycle_inputs as inputs,lifecycle_fields as fields,tablet_back_controls as back
from ios.adapters.normal_input import observation
from ios.adapters.snapshot_input_owner import SnapshotInputOwner


def reference(value,control):
    exact(value,{'scope','control','root'});need(control in inputs.IDS);scope=value['scope'];row=value['control']
    exact(scope,{'processId','instance','sampleEpochMs','elapsedMs','sequence'})
    need(integer(scope['processId'],1) and integer(scope['sampleEpochMs'],1) and integer(scope['elapsedMs']) and integer(scope['sequence']))
    inputs.uuid(scope['instance']);exact(row,{'id','token','enabled','focused','field'})
    need(row['id']==control and row['enabled'] is True and type(row['focused']) is bool);inputs.uuid(row['token'])
    minimal=dict(schemaVersion=1,commandId=row['token'],instance=scope['instance'],sequence=scope['sequence']+1,
                 observedElapsedMs=scope['elapsedMs'],fieldToken=row['token'],operation='activate')
    inputs.root(value['root'],control,minimal)
    if control=='tablet.back':
        need(row['field'] is None);actual=value['root']['observation']
        need(actual['inputReady'] and all(same(row[key],actual[key]) for key in ('id','token','enabled','focused')))
    else:
        field=fields.metadata(row['field']);need(field['attached'] and field['visible'] and field['enabled'] and not field['readOnly']
            and field['focused']==row['focused'] and same(field['identity'],value['root']['identity']))
    return row


def project(value,control):
    observation(value,value['processId'],value['sampleEpochMs']);need(control in inputs.IDS)
    rows=[row for row in value['controls'] if row['id']==control];need(len(rows)==1);actual=rows[0]
    if control=='tablet.back':
        back.metadata(actual);root=dict(kind='back',observation={key:deepcopy(actual[key]) for key in {'id','token','enabled','focused'}|back.FIELDS});field=None
    else:
        field=fields.active(value['lifecycleFieldInventory']);need(field is not None)
        need(field['identity']['editor']==fields.IDS.get(control,'chat'))
        root=dict(kind='field',identity=deepcopy(field['identity']))
    result=dict(scope=dict(processId=value['processId'],instance=value['instance'],sampleEpochMs=value['sampleEpochMs'],
        elapsedMs=value['elapsedMs'],sequence=value['lastSequence']),
        control={key:deepcopy(actual[key]) for key in ('id','token','enabled','focused')},root=root)
    result['control']['field']=deepcopy(field);reference(result,control);return result


class LifecycleInputOwner(SnapshotInputOwner):
    _owner_key='iosLifecycleInputOwnerVersion'
    _proof_namespace='lifecycle-input-proof'
    _proof_schema='lifecycleInputProof'
    _reference=staticmethod(reference)
    _input_source=inputs
    _root_is_stable=False

    @staticmethod
    def store_name(role):return 'ios-lifecycle-'+role+'-inputs.json'

    @staticmethod
    def root(event):return deepcopy(event['reference']['root'])

    def replace_reference(self,event,row):
        need(row['focused'] and row['field']['textOwned'])
        editor=row['field']['identity']['editor'];text=event['command']['text']
        need(fields.owned_text(text,editor) and (text=='' or text.endswith(self.run)))
        need(row['field']['text']=='' or row['field']['text'].endswith(self.run))

    def check_current(self,event):
        before=event['reference'];after=project(self.native.capture(),event['controlId'])
        need(same(before['control'],after['control']) and same(before['root'],after['root'])
             and all(same(before['scope'][key],after['scope'][key]) for key in ('instance','processId','sequence'))
             and after['scope']['elapsedMs']>=before['scope']['elapsedMs'] and after['scope']['sampleEpochMs']>=before['scope']['sampleEpochMs'])
