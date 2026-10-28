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


class IOSLifecycleWorldHoldRuntime:
    def __init__(self,adapter):self.adapter=adapter
    def native_original_acquisition(self,selector,run):
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
        result=client.execute(session,'mobile: overteOriginalKeeperOperation',dict(operation='touch-native-acquire',
            args=dict(binding=deepcopy(binding),runId=run,resultsDirectory=target['testBuild']['resultsDirectory'],
                origin=target['testBuild']['fixtureOrigin'])))
        source['check']()
        flags={'nativeAcquisitionBound','installedCandidateBound','nativeMotionGuardAvailable','nativeTouchSupport','resourceRetirementEstablished'}
        exact(result,{'originalKeeperNativeAcquisitionVersion','ownerInstance','encoding','acquisitionJson'}|flags)
        need(type(result['originalKeeperNativeAcquisitionVersion']) is int and result['originalKeeperNativeAcquisitionVersion']==1
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
        frame=body['frame'];exact(frame,{'originalKeeperNativeAcquisitionFrameVersion','originals','clockJoin','reads'})
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
