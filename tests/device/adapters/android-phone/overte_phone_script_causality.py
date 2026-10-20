"""Original native load causality and bounded readiness for normal Script input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import integer,need,number
from adapters.native_script_observation import NativeScriptObservation,validate,measured_effect,loaded_relative_modules,submitted_source
from adapters.native_script_loads import result as load_result
from adapters.native_script_files import originals
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,identifier
from overte_phone_script_measurements import owned_tree
import hashlib

VERSION=1


class ScriptReadinessPending(NativeUIError):
    pass


def check(call,before,current,directory,epoch):
    """Validate actual scoped callbacks, without turning a verb into state."""
    arguments('feature.scripts.act',call);run=identifier(call['runId'])
    validate(before,before.get('requestId'),before.get('processId'),before.get('capturedEpochMs'))
    validate(current,current.get('requestId'),before['processId'],epoch)
    need(current['requestId']!=before['requestId'] and current['instance']==before['instance'] and current['sequence']>before['sequence']
         and current['capturedEpochMs']>=before['capturedEpochMs'])
    for packet in (before,current):
        source=packet['source']
        need(source.get('effectSourceVersion')==1 and source.get('sourceIdentityVersion')==1
             and source.get('loadSourceVersion')==1 and source.get('membershipSourceVersion')==1
             and source['membership']['complete'])
    old,new=before['source']['loads'],current['source']['loads']
    need(new['instance']==old['instance'] and new['events'][:old['sequence']]==old['events'])
    def scoped(url):
        return owned_tree(url,directory) or url.startswith(call['fixtureUrl']+'tickets/')
    added=[event for event in new['events'][old['sequence']:] if scoped(event['url'])]
    verb=call['verb']
    if verb in ('picker-accept','load-url'):
        target=(directory+'/'+call['inputs']['resource']) if verb=='picker-accept' else (
            call['fixtureUrl']+'tickets/'+call['ticket']+'/missing.js')
        need(all(event['url']==target for event in added) and len(added)<=1)
        if not added:raise ScriptReadinessPending('Normal Script load has not produced its original callback')
        event=load_result(current,target,after_sequence=old['sequence'],after_epoch=before['capturedEpochMs'])
        if verb=='load-url':
            need(event['success'] is False and event['status']=='NotFound')
        else:need(event['success'] is True)
    else:
        need(not added)
        event=None
    return deepcopy(event)


def ready(call,before,current,directory,epoch):
    event=check(call,before,current,directory,epoch)
    verb,run=call['verb'],call['runId']
    source=current['source']
    engines=[row for row in source['engines'] if owned_tree(row['url'],directory)]
    known=[row for row in source['membership']['managers'] if row['assigned'] and owned_tree(row['url'],directory)]
    if verb=='picker-accept':
        target=directory+'/'+call['inputs']['resource']
        need(len(engines)<=1 and len(known)<=1 and all(row['url']==target for row in engines+known))
        if not engines or not known:raise ScriptReadinessPending('Normal Script engine is still loading')
        engine=engines[0]
        need(engine['required']['instance']==known[0]['instance']==event['managerInstance']
             and known[0]['loadGeneration']==event['loadGeneration']
             and before['capturedEpochMs']<=known[0]['assignedEpochMs']<=event['callbackEpochMs'])
        if not engine['running'] or engine['stopping'] or engine['finished']:
            raise ScriptReadinessPending('Normal Script engine has not reached running state')
        if not engine['code']['submitted']:raise ScriptReadinessPending('Normal Script source has not been submitted')
        code=submitted_source(current,target)
        raw=originals(run)[call['inputs']['resource']].decode().encode('utf-16-le')
        need(code['codeUnits']==len(raw)//2 and code['sha256']==hashlib.sha256(raw).hexdigest())
        companions=loaded_relative_modules(engine)
        need(all(row['url']==target.rsplit('/',1)[0]+'/companion.js' and not row['cached']
                 for row in engine['required']['modules']))
        if companions!=['companion.js']:raise ScriptReadinessPending('Normal Script companion has not loaded')
        # Empty initial entity data may precede the first controlled timer tick.
        rows=[row for row in source['effects']['entities'] if row['name']=='e2e-'+run+'-script']
        need(len(rows)<=1)
        if not rows or rows[0]['userData']=='':raise ScriptReadinessPending('Normal Script effect has not initialized')
        effect=measured_effect(current,run)
        need(effect is not None)
        if effect['ticks'] is None or effect['ticks']<1:raise ScriptReadinessPending('Normal Script effect has not advanced')
    elif verb in ('stop-owned','load-url'):
        if engines or known:raise ScriptReadinessPending('Owned Script work has not retired')
        need(measured_effect(current,run) is None)
    # Other inputs get callback-causality checking; their actual UI and effects
    # remain fresh measurements from the full observer, never desired defaults.
    return event


def wait(call,before,directory,reader,*,monotonic=time.monotonic,sleep=time.sleep,record=None):
    need(isinstance(reader,NativeScriptObservation) and callable(monotonic) and callable(sleep)
         and (record is None or callable(record)))
    started=previous=monotonic();need(number(started,0,1e15))
    for attempt in range(64):
        need(reader.guard() is not False)
        current=reader.read(reader.sequence,require_effects=True,require_code_identity=True,
                            require_load_history=True,require_membership=True)
        if record is not None:record(deepcopy(current))
        now=monotonic();need(number(now,0,1e15) and previous<=now and now-started<20);previous=now
        try:
            ready(call,before,current,directory,reader.clock_ms())
            return current
        except ScriptReadinessPending:
            need(attempt<63)
            sleep(.25)
    raise NativeUIError('Normal Script readiness did not settle')
