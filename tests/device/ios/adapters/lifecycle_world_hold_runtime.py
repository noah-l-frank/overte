"""Current installed/PID-gated composition; authenticated HID stays explicit.

No canonical RPC supplies a retained HID context yet. A caller must already
own that actual factory; absent transport cannot be reconstructed or installed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need,exact
from copy import deepcopy
import hashlib
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import canonical
from feature_journeys.contract import identifier,json_document
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import same
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.lifecycle_originals import IOSLifecycleSources
from ios.adapters.lifecycle_editors import LifecycleEditors
from ios.adapters.lifecycle_world_attempt import LifecycleWorldAttempt
from ios.adapters.lifecycle_world_hold import LifecycleWorldHold


def passive_world_original(frame,binding,run,owner):
    """Strict typed RAW+carrier join. Transport correlation is NOT live ownership."""
    from adapters.native_feature_observation import decode,validate as native,integer,number
    from adapters.native_clock_join import validate_join
    from ios.adapters import lifecycle_world as world
    from ios.adapters.lifecycle_world_attempt import source_frame_original
    exact(frame,{'originalKeeperPassiveWorldFrameVersion','ordinal','phase','originals','clockJoin','reads','previousReference'})
    need(type(frame['originalKeeperPassiveWorldFrameVersion']) is int and frame['originalKeeperPassiveWorldFrameVersion']==1
        and integer(frame['ordinal'],1,6) and frame['phase']==('held' if frame['ordinal']==1 else 'released' if frame['ordinal']==2 else 'quiet'))
    exact(frame['originals'],{'world','worldClock'});joined=validate_join(frame['clockJoin'],frame['originals'])
    packet=source_frame_original(frame,binding,run);reads=frame['reads'];need(type(reads) is list and len(reads)==3)
    phase='holding' if frame['phase']=='held' else 'released';lease=None;indices=[];ids=[]
    for row,action,original in zip(reads,('feature-native-observe',world.ACTION,'feature-native-observe'),(joined['nativeBefore'],packet,joined['nativeAfter'])):
        exact(row,{'originalKeeperPassiveRawVersion','queryIndex','query','nativeFile','hostBefore','hostAfter','passiveLeaseId','passivePhase'})
        need(type(row['originalKeeperPassiveRawVersion']) is int and row['originalKeeperPassiveRawVersion']==1 and integer(row['queryIndex'],1,32)
            and row['passivePhase']==phase);identifier(row['passiveLeaseId']);lease=row['passiveLeaseId'] if lease is None else lease;need(row['passiveLeaseId']==lease)
        query=row['query'];exact(query,{'schemaVersion','commandId','action'}|({'runId'} if action==world.ACTION else set()))
        need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']==action
            and query['commandId']==original.get('requestId') and (action!=world.ACTION or query['runId']==run))
        flags={'queryIssuanceOwned','freshNativeAcquisitionEstablished','installedCandidateBound','physicalFileIdentityEstablished',
            'nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        value=row['nativeFile'];exact(value,{'originalKeeperNativeFileVersion','ownerInstance','source','action','requestId','rawJson','bytes','sha256','passiveLeaseId','passivePhase'}|flags)
        need(type(value['originalKeeperNativeFileVersion']) is int and value['originalKeeperNativeFileVersion']==4
            and value['ownerInstance']==owner and value['source']=='original-rsd-house-arrest' and value['action']==action
            and value['requestId']==query['commandId'] and value['passiveLeaseId']==lease and value['passivePhase']==phase
            and type(value['rawJson']) is str and type(value['bytes']) is int and value['bytes']==len(value['rawJson'].encode())
            and value['sha256']==hashlib.sha256(value['rawJson'].encode()).hexdigest() and all(value[k] is False for k in flags)
            and decode(value['rawJson'],limit=world.LIMIT)==original)
        for point in (row['hostBefore'],row['hostAfter']):
            exact(point,{'epochMs','monotonic'});need(number(point['epochMs'],1,1e15) and number(point['monotonic'],0,1e15))
        a,b=row['hostBefore'],row['hostAfter'];need(0<=b['epochMs']-a['epochMs']<1500 and 0<=b['monotonic']-a['monotonic']<1.5
            and abs((b['epochMs']-a['epochMs'])-(b['monotonic']-a['monotonic'])*1000)<=250)
        if action==world.ACTION:world.validate(original,query,int(binding['processIdentity']))
        else:native(original,query['commandId'],int(binding['processIdentity']),original['capturedEpochMs'])
        indices.append(row['queryIndex']);ids.append(query['commandId'])
    need(indices==list(range(indices[0],indices[0]+3)) and len(set(ids))==3)
    begin=reads[0]['hostAfter'] if frame['phase']=='quiet' else reads[0]['hostBefore'];end=reads[2]['hostAfter']
    need(joined['hostBeforeEpochMs']==begin['epochMs'] and joined['hostBeforeMonotonic']==begin['monotonic']
        and joined['hostAfterEpochMs']==end['epochMs'] and joined['hostAfterMonotonic']==end['monotonic'])
    need((frame['ordinal']==1)==(frame['previousReference'] is None));return frame



class IOSLifecycleWorldHoldRuntime:
    def __init__(self,adapter):self.adapter=adapter
    def native_original_acquisition(self,selector,run,*,selected_query=None):
        """Reread the original child's immutable bytes; no fresh/input verdict.

        Actual capture clocks stay in the original frame. Transporting it
        later never samples a replacement native clock or changes its age.
        """
        import base64,time,re
        from adapters.native_feature_observation import decode,integer,number
        from adapters.script_feature.history import same,canonical
        from adapters.native_clock_join import validate_join
        from ios.adapters.lifecycle_world_attempt import source_frame_original
        from ios.adapters import lifecycle_world as world,native_geometry
        identifier(run);source=IOSScriptRuntime(self.adapter)._sources(selector);source['check']()
        binding=source['binding'];client=source['client'];session=source['session'];target=source['target']
        if selected_query is not None:
            need(type(selected_query) is str and re.fullmatch('ios-[0-9a-f]{32}',selected_query) is not None)
        operation='touch-native-acquire' if selected_query is None else 'touch-native-motion-acquire'
        extra={} if selected_query is None else dict(selectedQueryId=selected_query)
        result=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation=operation,
            args=dict(binding=deepcopy(binding),runId=run,resultsDirectory=target['testBuild']['resultsDirectory'],
                origin=target['testBuild']['fixtureOrigin'],**extra)))
        source['check']()
        flags={'nativeAcquisitionBound','installedCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        exact(result,{'originalKeeperNativeAcquisitionVersion','ownerInstance','encoding','acquisitionJson'}|flags)
        need(type(result['originalKeeperNativeAcquisitionVersion']) is int and result['originalKeeperNativeAcquisitionVersion']==(1 if selected_query is None else 3)
            and result['encoding']=='canonical-json-ascii' and type(result['acquisitionJson']) is str
            and len(result['acquisitionJson'])<=2048 and result['acquisitionJson'].isascii()
            and all(result[key] is False for key in flags));identifier(result['ownerInstance'])
        payload=json_document(result['acquisitionJson']);exact(payload,{'binding','runId','reference'})
        need(same(payload['binding'],binding) and payload['runId']==run and canonical(payload).decode('ascii')==result['acquisitionJson'])
        # Reuse only the existing exact reference/envelope codec. The HOST
        # never opens this remote path or treats its inode as local authority.
        codec=OriginalFrameStore(self.adapter.state_path(selector).parent,binding,run,'primary',source['check'],
            lambda *_:need(False),namespace='lifecycle-native-acquisition',schema_prefix='iosLifecycleNativeAcquisition')
        reference=payload['reference'];codec.expand(reference);reference_json=canonical(reference).decode('ascii')
        raw=[];started=time.monotonic()
        def transfer_current():
            source['check']();now=time.monotonic();need(number(now,started,started+5) and now-started<5)
        for offset in range(0,reference['bytes'],4096):
            transfer_current()
            chunk=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation='touch-native-acquisition-read',
                args=dict(binding=deepcopy(binding),runId=run,referenceJson=reference_json,offset=offset)))
            transfer_current();exact(chunk,{'originalKeeperNativeAcquisitionReadVersion','ownerInstance','encoding','originalJson'}|flags)
            need(type(chunk['originalKeeperNativeAcquisitionReadVersion']) is int and chunk['originalKeeperNativeAcquisitionReadVersion']==1
                and chunk['ownerInstance']==result['ownerInstance'] and chunk['encoding']=='canonical-json-ascii'
                and type(chunk['originalJson']) is str and chunk['originalJson'].isascii() and len(chunk['originalJson'])<12000
                and all(chunk[key] is False for key in flags))
            value=json_document(chunk['originalJson']);exact(value,{'reference','offset','contentBase64'})
            need(canonical(value).decode('ascii')==chunk['originalJson'] and same(value['reference'],reference)
                and type(value['offset']) is int and value['offset']==offset and type(value['contentBase64']) is str
                and len(value['contentBase64'])<=5464)
            data=base64.b64decode(value['contentBase64'],validate=True)
            need(len(data)==min(4096,reference['bytes']-offset));raw.append(data)
        raw=b''.join(raw);need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        body=decode(raw.decode('utf-8'),limit=1024*1024);need(canonical(body)==raw)
        exact(body,{'iosLifecycleNativeAcquisitionFrameVersion','kind','binding','runId','role','index','frame'})
        need(type(body['iosLifecycleNativeAcquisitionFrameVersion']) is int and body['iosLifecycleNativeAcquisitionFrameVersion']==1
            and body['kind']=='sources' and body['role']=='primary' and same(body['binding'],binding) and body['runId']==run
            and type(body['index']) is int and body['index']==reference['index'])
        frame=body['frame']
        if selected_query is not None:return self._selected_motion_original_result(source,run,selected_query,result,reference,frame,transfer_current)
        exact(frame,{'originalKeeperNativeAcquisitionFrameVersion','originals','clockJoin','reads'})
        need(type(frame['originalKeeperNativeAcquisitionFrameVersion']) is int and frame['originalKeeperNativeAcquisitionFrameVersion']==1)
        originals=frame['originals'];exact(originals,{'world','worldClock','geometry'})
        joined=validate_join(frame['clockJoin'],originals);source_frame_original(frame,binding,run)
        first,last=joined['nativeBefore'],joined['nativeAfter'];geometry=originals['geometry'];packet=originals['world']
        native_geometry.validate(geometry,geometry['commandId'],native_epoch_ms=last['capturedEpochMs'])
        need(first['capturedEpochMs']<=geometry['observation']['sampleEpochMs']<=packet['clockBefore']['epochMs'])
        reads=frame['reads'];need(type(reads) is list and len(reads)==4)
        actions=['feature-native-observe','native-geometry-snapshot',world.ACTION,'feature-native-observe']
        packets=[first,geometry,packet,last];indices=[]
        file_flags={'queryIssuanceOwned','freshNativeAcquisitionEstablished','installedCandidateBound','physicalFileIdentityEstablished',
            'nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        for row,action,original in zip(reads,actions,packets):
            exact(row,{'query','queryIndex','original'});need(integer(row['queryIndex'],1,32));indices.append(row['queryIndex'])
            query=row['query'];fields={'schemaVersion','commandId','action'}
            if action==world.ACTION:fields.add('runId')
            exact(query,fields);need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']==action
                and type(query['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',query['commandId']) is not None
                and query['commandId']==original.get('requestId',original.get('commandId')) and (action!=world.ACTION or query['runId']==run))
            read=row['original'];exact(read,{'originalKeeperNativeFileVersion','ownerInstance','source','action','requestId','rawJson','bytes','sha256'}|file_flags)
            need(type(read['originalKeeperNativeFileVersion']) is int and read['originalKeeperNativeFileVersion']==1
                and read['ownerInstance']==result['ownerInstance'] and read['source']=='original-rsd-house-arrest'
                and read['action']==action and read['requestId']==query['commandId'] and type(read['rawJson']) is str
                and type(read['bytes']) is int and read['bytes']==len(read['rawJson'].encode('utf-8'))
                and read['sha256']==hashlib.sha256(read['rawJson'].encode('utf-8')).hexdigest()
                and all(read[key] is False for key in file_flags)
                and same(decode(read['rawJson'],limit=262144),original))
        need(indices==list(range(indices[0],indices[0]+4)) and len({row['query']['commandId'] for row in reads})==4)
        transfer_current()
        return dict(originalKeeperNativeAcquisitionVersion=1,ownerInstance=result['ownerInstance'],binding=deepcopy(binding),
            runId=run,reference=deepcopy(reference),originalFrame=deepcopy(frame),nativeAcquisitionBound=False,
            installedCandidateBound=False,nativeMotionGuardAvailable=False,nativeTouchSupport=False,resourceRetirementEstablished=False)

    def _selected_motion_original_result(self,source,run,selected_query,result,reference,frame,transfer_current):
        """Decode the existing selected3 source original; no host-created owner."""
        import re
        from urllib.parse import quote,unquote
        from adapters.native_feature_observation import number
        from adapters.native_clock_join import validate_join
        from ios.adapters.lifecycle_world_attempt import source_frame_original,gesture
        from ios.adapters.lifecycle_touch_resource_owner import selected_motion_original
        from ios.adapters import native_geometry
        binding=source['binding']
        exact(frame,{'originalKeeperNativeAcquisitionFrameVersion','originals','clockJoin','reads','sdkWindow','selectedCandidate'})
        need(type(frame['originalKeeperNativeAcquisitionFrameVersion']) is int and frame['originalKeeperNativeAcquisitionFrameVersion']==3)
        originals=frame['originals'];exact(originals,{'world','worldClock','geometry','window'})
        joined=validate_join(frame['clockJoin'],originals);packet=source_frame_original(frame,binding,run)
        candidate=frame['selectedCandidate'];selected_motion_original(candidate,frame,binding,run,result['ownerInstance'])
        need(candidate['selectionQueryId']==selected_query)
        geometry=originals['geometry'];native_geometry.validate(geometry,geometry['commandId'],native_epoch_ms=joined['nativeAfter']['capturedEpochMs'])
        need(joined['nativeBefore']['capturedEpochMs']<=geometry['observation']['sampleEpochMs']<=packet['clockBefore']['epochMs'])
        sdk=frame['sdkWindow'];exact(sdk,{'method','path','reply','hostBeforeMonotonic','hostAfterMonotonic'})
        need(sdk['method']=='GET' and type(sdk['path']) is str and len(sdk['path'])<=512
            and sdk['path'].startswith('/session/') and sdk['path'].endswith('/window/rect'))
        session=unquote(sdk['path'][9:-12]);need(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',session) is not None
            and sdk['path']=='/session/'+quote(session,safe='')+'/window/rect')
        need(type(sdk['reply']) is dict and sdk['reply'].get('value')==originals['window']
            and number(sdk['hostBeforeMonotonic'],joined['hostBeforeMonotonic'],joined['hostAfterMonotonic'])
            and number(sdk['hostAfterMonotonic'],sdk['hostBeforeMonotonic'],joined['hostAfterMonotonic']))
        # Actual same raw UIKit geometry/window derives the complete path;
        # no x/y or dimensions arrive as caller-chosen movement authority.
        gesture(packet,geometry,originals['window'],'selected-original-reader')
        transfer_current()
        return dict(originalKeeperNativeAcquisitionVersion=3,ownerInstance=result['ownerInstance'],binding=deepcopy(binding),runId=run,
            reference=deepcopy(reference),originalFrame=deepcopy(frame),nativeAcquisitionBound=False,installedCandidateBound=False,
            nativeMotionGuardAvailable=False,nativeTouchSupport=False,resourceRetirementEstablished=False)

    def resource_metadata(self,selector,run,*,recover=False):
        """Read the original child's passive resource DTO, never borrow auth.

        Actual loop/Task/RSD objects remain in that child. This consumer opens
        no lease/session, grants no input or native-end/production admission.
        """
        from ios.adapters.lifecycle_touch_resource_owner import owner_header,capture_original
        identifier(run);need(type(recover) is bool)
        source=IOSScriptRuntime(self.adapter)._sources(selector);source['check']()
        operation='touch-resource-recover' if recover else 'touch-resource-capture'
        value=source['client'].execute(source['session'],'mobile: overteOriginalKeeperOperation',
                                      dict(operation=operation,args=dict(binding=deepcopy(source['binding']),runId=run)))
        source['check']()
        exact(value,{'originalKeeperTouchResourceVersion','ownerInstance','encoding','resourceJson',
                     'nativeTouchSupport','resourceRetirementEstablished'})
        need(type(value['originalKeeperTouchResourceVersion']) is int and value['originalKeeperTouchResourceVersion']==2
             and value['encoding']=='canonical-json-ascii' and type(value['resourceJson']) is str
             and len(value['resourceJson'])<=12288 and value['resourceJson'].isascii()
             and value['nativeTouchSupport'] is False and value['resourceRetirementEstablished'] is False)
        identifier(value['ownerInstance'])
        payload=json_document(value['resourceJson']);exact(payload,{'capture','owner'})
        need(value['resourceJson']==canonical(payload).decode('ascii'))
        state=owner_header(payload['owner'],source['binding'],run)
        need(state['pending'] is None and state['frames'])
        # Reuse existing reference codec and canonical original-body hash.
        # This checks DTO content correlation, NOT remote inode authority or
        # a local substitute for the child's original file/worker ownership.
        codec=OriginalFrameStore(self.adapter.state_path(selector).parent,source['binding'],run,'primary',
            source['check'],lambda *_:need(False),namespace='lifecycle-touch-resource',schema_prefix='iosLifecycleTouchResource')
        references=[codec.expand(ref) for ref in state['frames']]
        need([ref['index'] for ref in references]==list(range(1,len(references)+1)))
        capture=capture_original(payload['capture'],state);reference=references[-1]
        body=dict(iosLifecycleTouchResourceFrameVersion=1,kind='sources',binding=source['binding'],
                  runId=run,role='primary',index=reference['index'],frame=capture)
        raw=canonical(body)
        need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        source['check']()
        return dict(originalKeeperTouchResourceVersion=2,ownerInstance=value['ownerInstance'],
                    capture=deepcopy(capture),owner=deepcopy(payload['owner']),
                    nativeTouchSupport=False,resourceRetirementEstablished=False)

    def native_passive_world(self,selector,run,phase):
        """Existing child/pipe+chunk path. Four quiet calls are distinct originals.

        These originals remain partial observations; no canonical child or
        current native/input/resource-retirement capability is opened here.
        """
        import base64,time
        from adapters.native_feature_observation import decode,number
        from adapters.script_feature.history import canonical
        from adapters.original_frame_store import OriginalFrameStore
        identifier(run);need(phase in ('held','released','quiet'))
        source=IOSScriptRuntime(self.adapter)._sources(selector);source['check']()
        binding,client,session,target=source['binding'],source['client'],source['session'],source['target']
        flags={'nativeAcquisitionBound','installedCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        result=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation='touch-native-acquire',args=dict(
            binding=deepcopy(binding),runId=run,resultsDirectory=target['testBuild']['resultsDirectory'],origin=target['testBuild']['fixtureOrigin'],
            nativePassiveAcquisitionVersion=1,phase=phase)))
        source['check']();exact(result,{'originalKeeperNativeAcquisitionVersion','ownerInstance','encoding','acquisitionJson'}|flags)
        need(type(result['originalKeeperNativeAcquisitionVersion']) is int and result['originalKeeperNativeAcquisitionVersion']==4
            and result['encoding']=='canonical-json-ascii' and type(result['acquisitionJson']) is str and result['acquisitionJson'].isascii()
            and len(result['acquisitionJson'])<=2048 and all(result[k] is False for k in flags));identifier(result['ownerInstance'])
        value=json_document(result['acquisitionJson']);exact(value,{'binding','runId','reference','ordinal','phase'})
        need(canonical(value).decode('ascii')==result['acquisitionJson'] and value['binding']==binding and value['runId']==run and value['phase']==phase)
        codec=OriginalFrameStore(self.adapter.state_path(selector).parent,binding,run,'primary',source['check'],lambda *_:need(False),
            namespace='lifecycle-passive-world',schema_prefix='iosLifecyclePassiveWorld')
        ref=value['reference'];codec.expand(ref);raw=[];started=time.monotonic()
        for offset in range(0,ref['bytes'],4096):
            source['check']();need(0<=time.monotonic()-started<5)
            chunk=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation='touch-native-acquisition-read',args=dict(
                binding=deepcopy(binding),runId=run,referenceJson=canonical(ref).decode('ascii'),offset=offset,nativePassiveAcquisitionVersion=1)))
            source['check']();need(0<=time.monotonic()-started<5)
            exact(chunk,{'originalKeeperNativeAcquisitionReadVersion','ownerInstance','encoding','originalJson'}|flags)
            need(type(chunk['originalKeeperNativeAcquisitionReadVersion']) is int and chunk['originalKeeperNativeAcquisitionReadVersion']==2
                and chunk['ownerInstance']==result['ownerInstance'] and chunk['encoding']=='canonical-json-ascii'
                and type(chunk['originalJson']) is str and chunk['originalJson'].isascii() and len(chunk['originalJson'])<12000
                and all(chunk[k] is False for k in flags))
            body=json_document(chunk['originalJson']);exact(body,{'reference','offset','contentBase64'})
            need(canonical(body).decode('ascii')==chunk['originalJson'] and body['reference']==ref and type(body['offset']) is int and body['offset']==offset
                and type(body['contentBase64']) is str and len(body['contentBase64'])<=5464)
            data=base64.b64decode(body['contentBase64'],validate=True);need(len(data)==min(4096,ref['bytes']-offset));raw.append(data)
        raw=b''.join(raw);need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'])
        body=decode(raw.decode('utf-8'),limit=1024*1024);need(canonical(body)==raw)
        exact(body,{'iosLifecyclePassiveWorldFrameVersion','kind','binding','runId','role','index','frame'})
        need(type(body['iosLifecyclePassiveWorldFrameVersion']) is int and body['iosLifecyclePassiveWorldFrameVersion']==1
            and body['kind']=='sources' and body['binding']==binding and body['runId']==run and body['role']=='primary'
            and type(body['index']) is int and body['index']==ref['index'])
        frame=passive_world_original(body['frame'],binding,run,result['ownerInstance']);need(frame['ordinal']==value['ordinal'] and frame['phase']==phase)
        source['check']();return dict(originalKeeperNativeAcquisitionVersion=4,ownerInstance=result['ownerInstance'],reference=deepcopy(ref),
            originalFrame=deepcopy(frame),**{k:False for k in flags})

    def production_child(self,selector,editors,attempt,*,configuration=None):
        from ios.adapters.lifecycle_touch_transport import admit
        # Dependency admission precedes candidate/SDK work. No target value
        # or caller-supplied factory may turn missing transport into support.
        admit(configuration)

    def child(self,selector,editors,attempt,session_factory):
        need(type(editors) is LifecycleEditors and type(attempt) is LifecycleWorldAttempt and callable(session_factory))
        editors.history.check();attempt.bound();need(attempt.history is editors.history)
        source=IOSScriptRuntime(self.adapter)._sources(selector)
        need(same(source['binding'],editors.binding))
        root=self.adapter.state_path(selector).parent;need(root==editors.history.store.path.parent)
        original=source['check'];lock=editors.history.lock
        def check():lock.assert_held();need(original() is not False);return True
        source['check']=check
        sources=IOSLifecycleSources(source,editors.run,epoch_ms=editors.sources.epoch_ms,monotonic=editors.sources.monotonic)
        # Retain the unchanged actual first-attempt owner; only the second
        # attempt's passive readers use this freshly admitted canonical scope.
        owner=LifecycleWorldHold(PrivateFeatureState(root/'ios-lifecycle-world-hold.json'),attempt,session_factory)
        owner.sources=sources;owner.reader=source['observer'].lifecycle_world(source['clock_source'])
        owner.geometry=source['observer'].geometry();owner.ui=NativeUI(source['client'],source['session'],check)
        return owner
