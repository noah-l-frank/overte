"""Original owned native missing-place modal tokens for ordinary pointer input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.places_controls import identity,scope
from ios.adapters.navigation_dialogs import component
from ios.adapters.places_http import identifier

PROFILE='ios-navigation-error-v1'
IDS=frozenset(('navigation.error.page','navigation.error.ok'))
EXTRA=frozenset(('profile','dialogId','runId','errorInstance','errorEventId','lookupGeneration','qmlSource','inputReady'))
BASE=frozenset(('id','token','enabled','focused'))


def metadata(value):
    exact(value,BASE|EXTRA);need(value['id'] in IDS and value['profile']==PROFILE)
    identity(value['token'])
    for key in ('dialogId','runId','errorInstance','errorEventId'):identifier(value[key])
    component(value['qmlSource']);need(integer(value['lookupGeneration'],1))
    for key in ('enabled','focused','inputReady'):need(type(value[key]) is bool)
    need(not value['inputReady'] or value['enabled'] and value['id']=='navigation.error.ok');return value


def snapshot(value):
    exact(value,{'navigationDialogControlsVersion','scope','controls'})
    need(type(value['navigationDialogControlsVersion']) is int and value['navigationDialogControlsVersion']==1
         and type(value['controls']) is list and len(value['controls'])<=2);scope(value['scope'])
    ids=set();tokens=set();sources=set()
    for row in value['controls']:
        metadata(row);need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
        sources.add(tuple(row[key] for key in ('dialogId','runId','errorInstance','errorEventId','lookupGeneration','qmlSource')))
    need(not sources or len(sources)==1 and 'navigation.error.page' in ids);return value


def project(value):
    need(type(value.get('navigationDialogControlsVersion')) is int and value['navigationDialogControlsVersion']==1 and value['ready'] is True)
    controls=[]
    for raw in value['controls']:
        if raw['id'] in IDS:
            row=deepcopy(raw);row.pop('frame',None);controls.append(row)
    return snapshot(dict(navigationDialogControlsVersion=1,scope={key:value[source] for key,source in
        (('instance','instance'),('processId','processId'),('sequence','lastSequence'),
         ('observationSequence','navigationDialogSourceSequence'),('elapsedMs','elapsedMs'),('sampleEpochMs','sampleEpochMs'))},controls=controls))


def reference(value):
    snapshot(value);rows=[row for row in value['controls'] if row['id']=='navigation.error.ok'];need(len(rows)==1)
    return dict(scope=deepcopy(value['scope']),control=deepcopy(rows[0]))


def same_reference(previous,current):
    snapshot(current);exact(previous,{'scope','control'});scope(previous['scope']);metadata(previous['control'])
    expected=reference(current);old,new=previous['scope'],current['scope']
    need(previous['control']['id']=='navigation.error.ok' and same(previous['control'],expected['control'])
         and all(same(old[key],new[key]) for key in ('instance','processId','sequence'))
         and new['observationSequence']>old['observationSequence'] and old['elapsedMs']<=new['elapsedMs']<old['elapsedMs']+1500
         and old['sampleEpochMs']<=new['sampleEpochMs']<old['sampleEpochMs']+1500)
    return expected['control']


def join_observation(value,observed,dialog_id):
    from ios.adapters.navigation_dialogs import original,history,TEXT
    original(observed);snapshot(value);identifier(dialog_id)
    need(observed['complete'] is True and observed['foreignModals']==0 and observed['processId']==value['scope']['processId']
         and observed['clockAfter']['epochMs']<=value['scope']['sampleEpochMs']<observed['clockAfter']['epochMs']+1500)
    need(dialog_id in history(observed));state=history(observed)[dialog_id]
    need(state['response'] is None);created=state['created']['details'];context=created['error'];error=context['event']
    entries=[entry for entry in observed['dialogs'] if entry['dialogId']==dialog_id];need(len(entries)==1)
    entry=entries[0];root=entry['dialog']
    need(entry['listenerAlive'] and root is not None and root['visible'] and root['text']==TEXT
         and root['buttons']==observed['enums']['okButton'] and root['icon']==observed['enums']['criticalIcon'])
    ref=reference(value);row=ref['control']
    need(row['dialogId']==dialog_id and row['runId']==observed['runId'] and row['errorInstance']==context['instance']
         and row['errorEventId']==error['eventId'] and row['lookupGeneration']==error['lookupGeneration'] and row['qmlSource']==root['qmlSource'])
    return ref
