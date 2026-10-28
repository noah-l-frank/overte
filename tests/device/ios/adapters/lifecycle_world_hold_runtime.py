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
