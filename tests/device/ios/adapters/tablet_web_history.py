"""Original cumulative Tablet facts across actual documents and app generations.

Old DOM packets keep their own active source frames. A later close, navigation
or VM replacement never retimes them or substitutes the current DOM for them.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.native_script_observation import NativeScriptObservation
from ios.adapters import tablet_web_source as trace,tablet_web_sources as sources,tablet_web_dom as dom,tablet_web_buttons as buttons
from ios.adapters import tablet_web_state as state,uikit_input as uikit,web_script_emissions as emissions,tablet_web_deferred as deferred
from ios.adapters import tablet_web_closures as closures
from ios.adapters.tablet_web_app_origin import admitted
from ios.adapters.tablet_web_documents import completed,current_document
from ios.adapters.tablet_web_echoes import chain
from ios.adapters.world_web_measurements import browser_original,origin

FIELDS={'ledger','sources','document','buttons','state','touches','emitter','deferred','closures','browser'}
TYPED={'ledger':trace,'sources':sources,'document':dom,'buttons':buttons,'state':state,'touches':uikit,'emitter':emissions,'deferred':deferred,'closures':closures}


def _profile_key(profile):return tuple(profile[key] for key in ('engineInstance','assignedUrl','loadGeneration','assignedEpochMs'))


def _deny(*_args,**_kwargs):need(False)


def _advance(module,old,value):
    module.original(value)
    if old is None:return
    if old['commandId']==value['commandId']:need(value==old)
    else:module.validate(value,dict(schemaVersion=1,action=module.ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'],previous=old)


def _live(frame,document):
    packet=frame['state'];view=document['source']['nativeView'];state.join(packet,frame['sources'],frame['ledger'],frame['touches'])
    need(packet['otherLiveTablets']==0)
    owners=[row for row in packet['owners'] if row['handle']==view['handle'] and row['source']==view['source'] and row['alive']]
    need(len(owners)==1);actual=owners[0]['current'];need(actual is not None and actual['generation']==view['grant'])
    for key in ('active','viewPresent','presentationPresent','presentationAttached','windowPresent','sourceCurrent'):need(actual[key])
    need(not any(actual[key] for key in ('cleanupFailed','loading','openTimerActive','deadlineActive','resumeOnForeground')))
    targets=[row for row in packet['targets'] if row['kind']=='wk' and row['source']['view']==document['source']['presentationAfter']['view']]
    need(len(targets)==1 and targets[0]['alive'] and targets[0]['windowAttached'])


def derive(frames,apps,binding,origins):
    """Derive actual facts; no requested state, normalized actor or SDK access."""
    need(type(frames) is list and 0<len(frames)<=256 and type(apps) is list and len(apps)<=32);binding=context(binding)
    exact(origins,{'primary','foreign'});need(origin(origins['primary'])!=origin(origins['foreign']))
    exact(frames[0],FIELDS);basis=frames[0]['ledger'];profiles={};file_floor=None;button_floor=None
    # Reuse the actual reader's pure code/module/membership transitions. Its
    # transport, clocks and guard all refuse invocation; no historical packet
    # is promoted to a live source read. Effects/load journals are independent
    # optional sources, not invented for this app-origin subset.
    script_history=NativeScriptObservation(_deny,_deny,_deny,_deny,int(binding['processIdentity']),ios=True)
    for app in apps:
        exact(app,{'owner','files','scripts','buttons','controls','afterEpochMs'})
        need(app['owner']['featureRun']==basis['runId'] and app['owner']['fixtureUrl']==basis['fixtureUrl'])
        value=admitted(app['owner'],app['files'],app['scripts'],app['buttons'],app['controls'],binding,after_epoch=app['afterEpochMs'])
        key=_profile_key(value['profile']);need(key not in profiles);profiles[key]=value
        native_files=app['files'];scripts=app['scripts']
        if file_floor is not None:
            need(native_files['instance']==file_floor['instance'] and native_files['sequence']>file_floor['sequence']
                and native_files['requestId']!=file_floor['requestId'] and native_files['requestedEpochMs']>=file_floor['capturedEpochMs'])
        file_floor=native_files
        need(script_history.instance in (None,scripts['instance']) and scripts['sequence']>script_history.sequence
            and scripts['capturedEpochMs']>=script_history.captured_epoch)
        transition=script_history._history_transition(scripts,require_code_identity=True,require_membership=True)
        script_history._commit_history(scripts,transition)
        _advance(buttons,button_floor,app['buttons']);button_floor=app['buttons']
    previous=None;retained={}
    for frame in frames:
        exact(frame,FIELDS)
        for key,module in TYPED.items():
            _advance(module,None if previous is None else previous[key],frame[key])
            need(all(frame[key][field]==frame['ledger'][field] for field in ('runId','fixtureUrl','processId')))
        need(str(frame['ledger']['processId'])==binding['processIdentity'])
        browser_original(frame['browser'],None if previous is None else previous['browser'])
        trace.join_sources(frame['ledger'],frame['sources']);uikit.join_sources(frame['touches'],frame['sources'],frame['ledger'])
        state.join(frame['state'],frame['sources'],frame['ledger'],frame['touches']);deferred.join_sources(frame['deferred'],frame['sources'],frame['ledger'])
        closures.join_sources(frame['closures'],frame['sources'],frame['ledger'])
        need(frame['emitter']['complete'])
        document=frame['document']
        if document['status']=='ready':
            _live(frame,document);measured=current_document(frame['ledger'],frame['sources'],document,frame['browser'],origins)
            key=trace.document_key(document['source']['nativeView']);retained[key]=(frame,measured)
        previous=frame
    latest=frames[-1];ledger=latest['ledger'];loads=completed(ledger,latest['sources'])
    need(set(retained)<={trace.document_key(row['identity']) for row in loads})
    attempts=[];delivered=[];accepted=[];echoes=[]
    for key,(frame,measured) in retained.items():
        document=frame['document'];view=document['source']['nativeView'];need(profiles)
        actual_calls={row['call'] for row in frame['emitter']['sinks'] if row['identity']==view and row['call'] is not None}
        choices=set()
        for call in frame['emitter']['calls']:
            if call['id'] not in actual_calls or call['caller'] is None:continue
            manager=call['caller']['manager'];choice=(manager['instance'],manager['url'],manager['loadGeneration'],manager['assignedEpochMs'])
            need(choice in profiles and call['caller']['code']==profiles[choice]['profile']['code']);choices.add(choice)
        need(len(choices)<=1)
        if choices:app=profiles[next(iter(choices))]
        else:
            candidates=[value for value in profiles.values() if value['profile']['assignedEpochMs']<=measured['document']['begin']['clock']['epochMs']]
            need(candidates);app=max(candidates,key=lambda value:value['profile']['assignedEpochMs'])
        joined=chain(frame['ledger'],frame['sources'],document,frame['touches'],frame['emitter'],app['profile'],app['locations'])
        if measured['origin']=='foreign':need(not joined['delivered'] and not joined['accepted'] and not joined['echoes'])
        for collection,target in (('attempts',attempts),('delivered',delivered),('accepted',accepted),('echoes',echoes)):target.extend(joined[collection])
    current=latest['document'];opened=current['status']=='ready'
    public=dict(surface='tablet',text='',page='none',bridgeMessages=len(accepted),bridgeEchoes=len(echoes),attemptedMessages=len(attempts),
        documentLoads=len(loads),httpStatus=0,origin='none',documentKind='none',inlineLeases=0,
        deferredMessages=sum(row['bufferPending'] for row in latest['deferred']['records']),error='none',focused=False,open=opened)
    public['inlineLeases']=sum(binding_['current'] for carrier in latest['sources']['carriers'] for binding_ in carrier['bindings'])
    if opened:
        key=trace.document_key(current['source']['nativeView']);need(key in retained);measured=retained[key][1];body=current['source']['dom']
        public.update(text=body['editor']['text'],focused=body['editor']['focused'],page=measured['page'],origin=measured['origin'],documentKind=measured['documentKind'],
            httpStatus=0 if measured['response'] is None else measured['response']['status'])
    else:state.closed(latest['state'],latest['sources'],ledger,latest['touches'],require_observed=bool(loads))
    if any(row['kind']=='callback-enter' and row['detail']['result']['error'] for row in ledger['events']):public['error']='native-callback'
    return dict(public=public,document=deepcopy(current) if opened else None,attempts=attempts,delivered=delivered,accepted=accepted,echoes=echoes)
