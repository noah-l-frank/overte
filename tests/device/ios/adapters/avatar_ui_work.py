"""Original installed Avatar/Pal timer births, weak death and dispatch counts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from ios.adapters.avatar_state import identity
from ios.adapters.places_http import installed

VERSION=2
READS=(1,2)
SUFFIXES=('/system/avatarapp.js','/system/pal.js','/system/libraries/peopleConnection.js','/modules/request.js','/system/request-service.js')
IMMUTABLE=('timerId','handle','callerChain','createdEpochMs','singleShot','intervalMs','activeAtBirth','remainingAtBirthMs')
COUNTERS=('fired','entered','left')
TIMES=('destroyedEpochMs','lastFiredEpochMs','lastCallbackEpochMs','lastDispatchEpochMs')


def validate(value,epoch,previous=None,*,schema='avatarUiWorkVersion',suffixes=SUFFIXES):
    """Validate a native timer instance with its original schema and filters.

    Snapshot uses a separate producer instance; its packet is never relabeled
    into an Avatar original. The defaults preserve the existing Avatar wire.
    """
    need(type(schema) is str and type(suffixes) is tuple and suffixes
        and all(type(suffix) is str and suffix.startswith('/') for suffix in suffixes))
    version=value.get(schema) if type(value) is dict else None;actual=schema=='avatarUiWorkVersion' and version==2
    exact(value,{schema,'instance','complete','timers'}|({'callerStacks'} if actual else set()))
    need(type(version) is int and version in (READS if schema=='avatarUiWorkVersion' else (1,)) and identity(value['instance'])
        and type(value['complete']) is bool and type(value['timers']) is list and len(value['timers'])<=256)
    immutable=(set(IMMUTABLE)-{'callerChain'}|{'callerStackId'}) if actual else set(IMMUTABLE)
    from ios.adapters import avatar_call_stack
    caller_table=avatar_call_stack.table(value['callerStacks'],epoch,single_engine=True) if actual else {}
    used_callers=set();stack_history=avatar_call_stack.History()
    identifiers=[];handles=set()
    for row in value['timers']:
        exact(row,immutable|set(COUNTERS)|set(TIMES)|{'depth','pendingDispatch'})
        identity(row['timerId']);identifiers.append(row['timerId']);need(integer(row['handle'],1,2**31-1)
            and integer(row['createdEpochMs'],1,epoch) and type(row['singleShot']) is bool and type(row['activeAtBirth']) is bool
            and integer(row['intervalMs'],-2**31,2**31-1) and integer(row['remainingAtBirthMs'],-1,2**31-1)
            and (row['remainingAtBirthMs']>=0 if row['activeAtBirth'] else row['remainingAtBirthMs']==-1))
        if actual:
            identity(row['callerStackId']);need(row['callerStackId'] in caller_table);caller=caller_table[row['callerStackId']]
            avatar_call_stack.validate(caller['callerStack'],caller['callerModules'],row['createdEpochMs'])
            need(caller['callerModules']);stack_history.accept(caller['callerStack']);used_callers.add(caller['id'])
        else:
            chain=row['callerChain'];need(type(chain) is list and 1<=len(chain)<=32)
            relevant=False
            for caller in chain:
                need(type(caller) is str and len(caller)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in caller))
                for suffix in suffixes:
                    if caller.endswith(suffix):installed(caller,suffix);relevant=True
            need(relevant)
        for key in COUNTERS:need(integer(row[key],0,9007199254740991))
        need(integer(row['depth'],0,16) and integer(row['pendingDispatch'],0,16)
            and row['left']<=row['entered']<=row['fired'] and row['depth']==row['entered']-row['left']
            and row['depth']<=row['pendingDispatch']<=row['fired'])
        for key in TIMES:
            if row[key] is not None:need(integer(row[key],row['createdEpochMs'],epoch))
        need((row['lastFiredEpochMs'] is None)==(row['fired']==0) and (row['lastCallbackEpochMs'] is None)==(row['entered']==0))
        if row['fired']==0:need(row['lastDispatchEpochMs'] is None)
        if row['fired'] and row['pendingDispatch']==0:
            need(row['lastDispatchEpochMs'] is not None and row['lastDispatchEpochMs']>=row['lastFiredEpochMs'])
        if row['destroyedEpochMs'] is None:
            need(row['handle'] not in handles);handles.add(row['handle'])
        elif row['lastFiredEpochMs'] is not None:need(row['lastFiredEpochMs']<=row['destroyedEpochMs'])
    need(identifiers==sorted(set(identifiers)))
    if actual and value['complete']:need(used_callers==set(caller_table))
    if previous is not None:
        validate(previous,epoch,schema=schema,suffixes=suffixes);need(value['instance']==previous['instance']
            and version==previous[schema] and (previous['complete'] or not value['complete']))
        current={row['timerId']:row for row in value['timers']}
        if actual:
            old=previous['callerStacks'];need(len(value['callerStacks'])>=len(old) and value['callerStacks'][:len(old)]==old)
        for old in previous['timers']:
            need(old['timerId'] in current);row=current[old['timerId']]
            need(all(row[key]==old[key] for key in immutable) and all(row[key]>=old[key] for key in COUNTERS))
            for key in TIMES:
                if old[key] is not None:need(row[key] is not None and row[key]>=old[key])
            if old['destroyedEpochMs'] is not None:need(row['destroyedEpochMs']==old['destroyedEpochMs'] and row['fired']==old['fired'])
    return value


def drained_since(before,after,manager_ids,expected_code,*,require_actual=False):
    """Own only actual timer births absent from the original baseline.

    Destruction plus callback depth alone is insufficient: a singleShot may
    have died while its original timerFired stack has not entered JS yet.
    Every owned timer must also finish that actual native dispatch stack.
    """
    from ios.adapters import avatar_scripts
    from ios.adapters.avatar_code import for_worker
    avatar_scripts.original(before);avatar_scripts.original(after)
    need(type(require_actual) is bool)
    if require_actual:need(before['iosAvatarScriptsVersion']==after['iosAvatarScriptsVersion']==2)
    avatar_scripts.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=avatar_scripts.ACTION,runId=after['runId']),
        after['processId'],previous=before)
    need(type(manager_ids) is set and manager_ids);old={row['membership']['instance']:row for row in before['source']['workers']}
    current={row['membership']['instance']:row for row in after['source']['workers']};owned={};endpoint=0
    relevant={};names=set()
    for manager,row in old.items():
        present={suffix for code in row['avatar']['code'] for suffix in SUFFIXES if code['url'].endswith(suffix)}
        if present:relevant[manager]=present;names|=present
    need(manager_ids==set(relevant) and {'/system/avatarapp.js','/system/pal.js'}<=names)
    need({manager for manager,row in current.items() if row['avatar']['code']}==set(relevant))
    for manager in manager_ids:
        identity(manager);need(manager in old and manager in current and 'uiWork' in old[manager] and 'uiWork' in current[manager])
        a,b=old[manager]['uiWork'],current[manager]['uiWork'];validate(b,after['clockAfter']['epochMs'],a)
        for_worker(before,manager,expected_code,required=relevant[manager])
        for_worker(after,manager,expected_code,required=relevant[manager])
        need(a['complete'] and b['complete']);prior={row['timerId'] for row in a['timers']}
        if require_actual:
            from ios.adapters import avatar_call_stack
            for observed,worker,epoch in ((a,old[manager],before['clockAfter']['epochMs']),(b,current[manager],after['clockAfter']['epochMs'])):
                need(observed['avatarUiWorkVersion']==2)
                caller_table=avatar_call_stack.table(observed['callerStacks'],epoch,single_engine=True)
                for timer in observed['timers']:
                    caller=caller_table[timer['callerStackId']]
                    required={suffix for module in caller['callerModules'] for suffix in SUFFIXES if module['url'].endswith(suffix)}
                    need(required)
                    avatar_call_stack.bound(caller['callerStack'],caller['callerModules'],timer['createdEpochMs'],worker['avatar']['code'],
                        expected_code,required=required)
        new={row['timerId']:deepcopy(row) for row in b['timers'] if row['timerId'] not in prior};owned[manager]=new
        for row in new.values():
            need(row['destroyedEpochMs'] is not None and row['depth']==row['pendingDispatch']==0)
            endpoint=max(endpoint,*[stamp for key in TIMES if (stamp:=row[key]) is not None])
    return dict(owned=owned,endpointEpochMs=endpoint)
