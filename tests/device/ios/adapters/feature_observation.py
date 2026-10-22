"""Original native feature reads over the existing owned HTTP/AFC component.

This transport does not establish installed-code identity or advertise a feature
capability. Canonical physical binding independently establishes that join
before exposing these components; direct component use remains unbound.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, HTTPRedirectHandler, build_opener
import uuid

from adapters.normal_create import avatar_entities
from adapters.normal_script_manager import DIAGNOSTIC_FILE, read_native_diagnostic
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import (NativeFeatureObservation,
    FILE as NATIVE_FEATURE_FILE, LIMIT as NATIVE_FEATURE_LIMIT)
from adapters.recorded_preview_evidence import (RecordedPreviewEvidence, FILE as RECORDED_PREVIEW_FILE,
    INPUT as PREVIEW_INPUT, SINK as PREVIEW_SINK, MAX_BYTES as PREVIEW_LIMIT)
from adapters.native_script_observation import NativeScriptObservation, FILE as SCRIPT_EXECUTION_FILE
from adapters.native_script_terminal import NativeScriptTerminal,FILE as SCRIPT_TERMINAL_FILE,LIMIT as SCRIPT_TERMINAL_LIMIT,command as script_terminal_command
from adapters.native_script_work import NativeScriptWork, FILE as SCRIPT_WORK_FILE, command as script_work_command
from ios.adapters.appium_adapter import AppiumAdapter, WebDriverRequestError
from adapters.native_script_files import NativeScriptFiles, FILE as SCRIPT_FIXTURE_FILE, command as script_files_command
from adapters.world_render_evidence import NativeWorldRenderCapture, FILE as WORLD_RENDER_FILE
from adapters.world_render_storage import NativeWorldRenderStorage, command as world_storage_command
from adapters.world_render_receipts import NativeWorldReceiptCleanup, FILE as WORLD_RECEIPT_FILE, command as world_receipt_command
from adapters.owned_world_render import OwnedWorldRenderCapture
from adapters.native_account_probe import (NativeAccountProbe, OwnedAccountProbe, FILE as ACCOUNT_PROBE_FILE,
    command as account_probe_command)
from adapters.native_chat_observation import NativeChatObservation, OwnedChatCapture, FILE as CHAT_FILE, command as chat_command
from adapters.native_chat_view import NativeChatView, FILE as CHAT_VIEW_FILE, command as chat_view_command
from adapters.native_web_dom import NativeWebDOMObservation, FILE as WEB_DOM_FILE, command as web_dom_command
from adapters.pending_commit_owner import NativePendingCommitOwner, FILE as PENDING_OWNER_FILE, command as pending_owner_command
from adapters.native_navigation_replies import NativeNavigationReplies, FILE as NAVIGATION_REPLIES_FILE, command as navigation_replies_command
from adapters.native_process_presence import NativeProcessPresence, FILE as PROCESS_PRESENCE_FILE, LIMIT as PROCESS_PRESENCE_LIMIT, command as process_presence_command
from ios.adapters.web_closures import IOSWebClosures, FILE as WEB_CLOSURES_FILE, LIMIT as WEB_CLOSURES_LIMIT, command as web_closures_command
from ios.adapters.tablet_web_sources import IOSTabletSources,FILE as TABLET_SOURCES_FILE,LIMIT as TABLET_SOURCES_LIMIT,command as tablet_sources_command
from ios.adapters.tablet_web_source import IOSTabletWebSource,FILE as TABLET_WEB_FILE,LIMIT as TABLET_WEB_LIMIT,command as tablet_web_command
from ios.adapters.tablet_web_closures import IOSTabletWebClosures,FILE as TABLET_CLOSURES_FILE,LIMIT as TABLET_CLOSURES_LIMIT,command as tablet_closures_command
from ios.adapters.tablet_web_dom import IOSTabletWebDOM,FILE as TABLET_WEB_DOM_FILE,LIMIT as TABLET_WEB_DOM_LIMIT,command as tablet_web_dom_command
from ios.adapters.world_web_source import IOSWorldWebSource,FILE as WORLD_WEB_FILE,LIMIT as WORLD_WEB_LIMIT,command as world_web_command
from ios.adapters.world_web_dom import IOSWorldWebDOM,FILE as WORLD_WEB_DOM_FILE,LIMIT as WORLD_WEB_DOM_LIMIT,command as world_web_dom_command
from ios.adapters.world_web_geometry import IOSWorldWebGeometry,FILE as WORLD_WEB_GEOMETRY_FILE,LIMIT as WORLD_WEB_GEOMETRY_LIMIT,command as world_web_geometry_command
from ios.adapters.world_web_work import IOSWorldWebWork,FILE as WORLD_WEB_WORK_FILE,LIMIT as WORLD_WEB_WORK_LIMIT,command as world_web_work_command
from ios.adapters.world_web_keys import IOSWorldWebKeys,FILE as WORLD_WEB_KEYS_FILE,LIMIT as WORLD_WEB_KEYS_LIMIT,command as world_web_keys_command
from ios.adapters.bundle_observation import NativeBundleObservation, FILE as BUNDLE_FILE, command as bundle_command
from ios.adapters.location_bookmarks import (IOSLocationBookmarks,FILE as BOOKMARKS_FILE,LIMIT as BOOKMARKS_LIMIT,
    command as bookmarks_command)
from ios.adapters.places_model import IOSPlacesModel,FILE as PLACES_MODEL_FILE,LIMIT as PLACES_MODEL_LIMIT,command as places_model_command
from ios.adapters.places_http import IOSPlacesHttp,FILE as PLACES_HTTP_FILE,LIMIT as PLACES_HTTP_LIMIT,command as places_http_command
from ios.adapters.navigation_dialogs import IOSNavigationDialogs,FILE as NAVIGATION_DIALOG_FILE,LIMIT as NAVIGATION_DIALOG_LIMIT,command as navigation_dialog_command
from ios.adapters.navigation_state import IOSNavigationState,FILE as NAVIGATION_STATE_FILE,LIMIT as NAVIGATION_STATE_LIMIT,command as navigation_state_command
from ios.adapters.scene_inventory import IOSSceneInventory,FILE as SCENE_INVENTORY_FILE,LIMIT as SCENE_INVENTORY_LIMIT,command as scene_inventory_command
from ios.adapters.avatar_social_http import IOSAvatarSocialHttp,FILE as AVATAR_SOCIAL_HTTP_FILE,LIMIT as AVATAR_SOCIAL_HTTP_LIMIT,command as avatar_social_http_command
from ios.adapters.people_model import IOSPeopleModel,FILE as PEOPLE_MODEL_FILE,LIMIT as PEOPLE_MODEL_LIMIT,command as people_model_command
from ios.adapters.create_work import IOSCreateWork,FILE as CREATE_WORK_FILE,LIMIT as CREATE_WORK_LIMIT,command as create_work_command
from ios.adapters.avatar_scripts import IOSAvatarScripts,FILE as AVATAR_SCRIPTS_FILE,LIMIT as AVATAR_SCRIPTS_LIMIT,command as avatar_scripts_command
from ios.adapters.avatar_entities import IOSAvatarEntities,FILE as AVATAR_ENTITIES_FILE,LIMIT as AVATAR_ENTITIES_LIMIT,command as avatar_entities_command
from ios.adapters.create_entities import IOSCreateEntities,FILE as CREATE_ENTITIES_FILE,LIMIT as CREATE_ENTITIES_LIMIT,command as create_entities_command
from ios.adapters.pointer_state import IOSPointerState,FILE as POINTER_STATE_FILE,LIMIT as POINTER_STATE_LIMIT,command as pointer_state_command
from ios.adapters.avatar_state import IOSAvatarState,FILE as AVATAR_STATE_FILE,LIMIT as AVATAR_STATE_LIMIT,command as avatar_state_command
from ios.adapters.avatar_renderers import IOSAvatarRenderers,FILE as AVATAR_RENDERERS_FILE,LIMIT as AVATAR_RENDERERS_LIMIT,command as avatar_renderers_command
from ios.adapters.emote_world import IOSEmoteWorld,FILE as EMOTE_WORLD_FILE,LIMIT as EMOTE_WORLD_LIMIT,command as emote_world_command
from ios.adapters.avatar_world import IOSAvatarWorld,FILE as AVATAR_WORLD_FILE,LIMIT as AVATAR_WORLD_LIMIT,command as avatar_world_command
from ios.adapters.avatar_inputs import IOSAvatarInputs,FILE as AVATAR_INPUTS_FILE,LIMIT as AVATAR_INPUTS_LIMIT,command as avatar_inputs_command
from ios.adapters.script_dialogs import IOSScriptDialogs,FILE as SCRIPT_DIALOGS_FILE,LIMIT as SCRIPT_DIALOGS_LIMIT,command as script_dialogs_command
from ios.adapters.create_state import IOSCreateState,FILE as CREATE_STATE_FILE,LIMIT as CREATE_STATE_LIMIT,command as create_state_command
from ios.adapters.create_files import IOSCreateFiles,FILE as CREATE_FILES_FILE,LIMIT as CREATE_FILES_LIMIT,command as create_files_command
from adapters.private_login_input import command as private_input_command
from adapters.native_account_origin import (NativeAccountOrigin, OwnedAccountOrigin, FILE as ACCOUNT_ORIGIN_FILE,
    command as account_origin_command)
from adapters.native_graphics_subject import (NativeGraphicsSubject, FILE as GRAPHICS_SUBJECT_FILE,
    LIMIT as GRAPHICS_SUBJECT_LIMIT, command as graphics_subject_command)
from adapters.native_scene_loads import NativeSceneLoads, FILE as SCENE_LOAD_FILE, command as scene_load_command
from adapters.native_completed_frame import NativeCompletedFrame, FILE as COMPLETED_FRAME_FILE, command as completed_frame_command
from adapters.native_vulkan_world_frame import (NativeVulkanWorldFrame,FILE as VULKAN_WORLD_FILE,
    LIMIT as VULKAN_WORLD_LIMIT,command as vulkan_world_command)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def post_request(request, timeout):
    from adapters.operation_transport_guard import check as final_transport_guard
    try:
        opener=build_opener(NoRedirect())
        final_transport_guard()
        return opener.open(request, timeout=timeout)
    except HTTPError as error:
        error.close()
        raise NativeUIError('Native iOS feature HTTP request failed') from None


class FeatureObservation:
    def __init__(self, client, session, target, observe_process, *,
                 monotonic=time.monotonic, sleep=time.sleep, epoch_ms=lambda: int(time.time() * 1000)):
        try:
            if (type(session) is not str or re.fullmatch('[A-Za-z0-9_.:-]{1,160}', session) is None
                    or target.get('platform') != 'ios' or target.get('physical') is not True
                    or target.get('probe') != {'kind': 'ios-documents'} or not callable(observe_process)):
                raise ValueError()
            bundle = target['appId']
            results = target['testBuild']['resultsDirectory']
            origin = target['testBuild']['fixtureOrigin']
            if (type(bundle) is not str or re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+', bundle) is None
                    or type(results) is not str or re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', results) is None
                    or len(results) > 128
                    or AppiumAdapter.normalized_http_origin(origin, 'native feature fixture') != origin):
                raise ValueError()
        except Exception:
            raise NativeUIError('Native iOS feature observation configuration is invalid') from None
        self.client, self.session, self.target = client, session, target
        self.remote = '@' + bundle + ':documents/' + results + '/' + DIAGNOSTIC_FILE
        self.origin, self.bundle = origin, bundle
        self.observe_process = observe_process
        self.monotonic, self.sleep, self.epoch_ms = monotonic, sleep, epoch_ms
        self.process = self.instance = None
        self.sequence = 0

    def guard(self):
        value = self.observe_process()
        if (type(value) is not dict or set(value) != {'bundleId', 'pid', 'foreground'}
                or value['bundleId'] != self.bundle or type(value['pid']) is not int or value['pid'] <= 0
                or value['foreground'] is not True or self.process is not None and value != self.process):
            raise NativeUIError('Native iOS feature observation lost its foreground process')
        self.process = dict(value)

    def original(self, *, remote=None, limit=65536):
        try:
            encoded = self.client.execute(self.session, 'mobile: pullFile', {'remotePath': remote or self.remote})
        except WebDriverRequestError as error:
            if error.status == 500:
                return ''  # The requested diagnostic may not have been created yet.
            raise
        if type(encoded) is not str or len(encoded) > 4 * ((limit + 2) // 3):
            raise NativeUIError('Native iOS feature diagnostic exceeds its transport bound')
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > limit:
            raise NativeUIError('Native iOS feature diagnostic exceeds its byte bound')
        return raw.decode('utf-8')

    def send(self, command):
        self.guard()
        limit = 4096
        if command.get("action") == "feature-script-files":
            script_files_command(command, ios=True)
            limit = 49152
        elif command.get('action')=='feature-private-login-input':private_input_command(command)
        elif command.get('action')=='feature-chat-observe':chat_command(command,ios=True)
        elif command.get('action')=='feature-chat-view-observe':chat_view_command(command,ios=True)
        elif command.get('action')=='feature-ios-web-closures':web_closures_command(command)
        elif command.get('action')=='feature-ios-tablet-sources':tablet_sources_command(command)
        elif command.get('action')=='feature-ios-tablet-web':tablet_web_command(command)
        elif command.get('action')=='feature-ios-tablet-web-closures':tablet_closures_command(command)
        elif command.get('action')=='feature-ios-tablet-web-dom':tablet_web_dom_command(command)
        elif command.get('action')=='feature-ios-world-web':world_web_command(command)
        elif command.get('action')=='feature-ios-world-web-dom':world_web_dom_command(command)
        elif command.get('action')=='feature-ios-world-web-geometry':world_web_geometry_command(command)
        elif command.get('action')=='feature-ios-world-web-work':world_web_work_command(command)
        elif command.get('action')=='feature-ios-world-web-keys':world_web_keys_command(command)
        elif command.get('action')=='feature-ios-location-bookmarks':bookmarks_command(command)
        elif command.get('action')=='feature-ios-places-model':places_model_command(command)
        elif command.get('action')=='feature-ios-places-http':places_http_command(command)
        elif command.get('action')=='feature-ios-navigation-dialogs':navigation_dialog_command(command)
        elif command.get('action')=='feature-ios-navigation-state':navigation_state_command(command)
        elif command.get('action')=='feature-ios-scene-inventory':scene_inventory_command(command)
        elif command.get('action')=='feature-ios-avatar-social-http':avatar_social_http_command(command)
        elif command.get('action')=='feature-ios-people-model':people_model_command(command)
        elif command.get('action')=='feature-ios-create-work':create_work_command(command)
        elif command.get('action') in ('feature-ios-snapshot-work','feature-ios-snapshot-exports','feature-ios-snapshot-captures','feature-ios-snapshot-inputs'):
            if command['action']=='feature-ios-snapshot-work':
                from ios.adapters.snapshot_work import command as snapshot_command
            elif command['action']=='feature-ios-snapshot-inputs':
                from ios.adapters.snapshot_inputs import command as snapshot_command
            elif command['action']=='feature-ios-snapshot-captures':
                from ios.adapters.snapshot_captures import command as snapshot_command
            else:
                from ios.adapters.snapshot_exports import command as snapshot_command
            snapshot_command(command)
        elif command.get('action')=='feature-ios-avatar-scripts':avatar_scripts_command(command)
        elif command.get('action')=='feature-ios-avatar-entities':avatar_entities_command(command)
        elif command.get('action')=='feature-ios-create-entities':create_entities_command(command)
        elif command.get('action')=='feature-ios-pointer-state':pointer_state_command(command)
        elif command.get('action')=='feature-ios-avatar-state':avatar_state_command(command)
        elif command.get('action')=='feature-ios-avatar-renderers':avatar_renderers_command(command)
        elif command.get('action')=='feature-ios-script-dialogs':script_dialogs_command(command)
        elif command.get('action')=='feature-ios-emote-world':emote_world_command(command)
        elif command.get('action')=='feature-ios-avatar-world':avatar_world_command(command)
        elif command.get('action')=='feature-ios-avatar-inputs':avatar_inputs_command(command)
        elif command.get('action')=='feature-script-terminal-observe':script_terminal_command(command,ios=True)
        elif command.get('action')=='feature-script-work-observe':script_work_command(command,ios=True)
        elif command.get('action')=='feature-ios-create-state':create_state_command(command)
        elif command.get('action')=='feature-ios-create-files':
            create_files_command(command);limit=131072
        elif command.get('action')=='feature-web-dom-observe':web_dom_command(command,ios=True)
        elif command.get('action')=='feature-pending-commit-owner':pending_owner_command(command,ios=True)
        elif command.get('action')=='feature-navigation-replies':navigation_replies_command(command,ios=True)
        elif command.get('action')=='feature-process-presence':process_presence_command(command,ios=True)
        elif command.get('action')=='feature-graphics-subject-observe':graphics_subject_command(command,ios=True)
        elif command.get('action')=='feature-scene-load-observe':scene_load_command(command,ios=True)
        elif command.get('action')=='feature-completed-frame':completed_frame_command(command)
        elif command.get('action')=='feature-vulkan-world-frame':vulkan_world_command(command)
        elif command.get('action')=='ios-bundle-observe':bundle_command(command)
        elif command.get('action') == 'feature-account-probe':account_probe_command(command,ios=True)
        elif command.get('action') == 'feature-account-origin':account_origin_command(command,ios=True)
        elif command.get('action') == 'feature-world-render-storage':world_storage_command(command,ios=True)
        elif command.get('action') == 'feature-world-render-receipt':world_receipt_command(command,ios=True)
        payload = json.dumps(command).encode()
        if len(payload) > limit:
            raise NativeUIError("Native iOS feature command exceeds its transport bound")
        before_send=getattr(self,'before_send',None)
        if before_send is not None and (not callable(before_send) or before_send() is False):
            raise NativeUIError('Native iOS feature transport guard refused delivery')
        with post_request(Request(self.origin + '/e2e-client-command.json', data=payload,
                method='POST', headers={'Content-Type': 'application/json'}), timeout=5) as response:
            content = response.read(limit + 1)
            def pairs(items):
                value = {}
                for key, item in items:
                    if key in value:
                        raise ValueError()
                    value[key] = item
                return value
            echo = json.loads(content, object_pairs_hook=pairs)
            if (response.status != 200 or len(content) > limit or echo != command
                    or type(echo) is not dict
                    or any(type(echo[key]) is not type(command[key]) for key in command)):
                raise ValueError()
        self.guard()

    def native_observer(self):
        self.guard()
        remote = self.remote.rsplit('/', 1)[0] + '/' + NATIVE_FEATURE_FILE
        return NativeFeatureObservation(self.send,
            lambda: self.original(remote=remote, limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms, self.guard, self.process['pid'], ios=True,
            monotonic=self.monotonic, sleep=self.sleep)

    def bound_native_observer(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+NATIVE_FEATURE_FILE
        original=lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT)
        if clock_source is None:
            # An independent nonce-bound original read. Host time is only the
            # legacy clock reader's local request bookkeeping, never freshness.
            clock_source=NativeFeatureObservation(self.send,original,lambda:int(time.time()*1000),self.guard,
                self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)
        if not isinstance(clock_source,NativeFeatureObservation) or not clock_source.ios or clock_source.pid!=self.process['pid']:
            raise NativeUIError('Original native clock source does not match this iOS process')
        def clock():
            packet=clock_source.read(clock_source.sequence)
            if reader.instance not in (None,packet['instance']):
                raise NativeUIError('Original native clocks changed their iOS source birth')
            reader.instance=packet['instance']
            return packet['capturedEpochMs']
        reader=NativeFeatureObservation(self.send,original,clock,self.guard,self.process['pid'],ios=True,
            monotonic=self.monotonic,sleep=self.sleep,native_clock_bound=True)
        return reader

    def geometry(self):
        from ios.adapters.native_geometry import OriginalGeometry
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/ios-ui-request-result.json'
        return OriginalGeometry(self.send,lambda:self.original(remote=remote,limit=65536),
            self.epoch_ms,self.guard,monotonic=self.monotonic,sleep=self.sleep)

    def recorded_preview_observer(self):
        self.guard()
        root = self.remote.rsplit('/', 1)[0] + '/'
        def original_bytes(name):
            if name not in (PREVIEW_INPUT, PREVIEW_SINK):
                raise NativeUIError('Original iOS preview filename is outside its closed inventory')
            self.guard()
            # A transfer error must propagate; a 500 response never means that
            # an original file is absent. Release uses a separate native query.
            encoded = self.client.execute(self.session, 'mobile: pullFile', {'remotePath': root + name})
            if type(encoded) is not str or len(encoded) > 4 * ((PREVIEW_LIMIT + 2) // 3):
                raise NativeUIError('Original iOS preview transfer exceeds its bound')
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > PREVIEW_LIMIT:
                raise NativeUIError('Original iOS preview bytes exceed their bound')
            self.guard()
            return raw
        return RecordedPreviewEvidence(self.send,
            lambda: self.original(remote=root + RECORDED_PREVIEW_FILE, limit=NATIVE_FEATURE_LIMIT),
            original_bytes, self.epoch_ms, self.guard, self.process['pid'], ios=True,
            monotonic=self.monotonic, sleep=self.sleep)

    def script_execution_observer(self):
        self.guard()
        remote = self.remote.rsplit('/', 1)[0] + '/' + SCRIPT_EXECUTION_FILE
        def clock(): return self.native_observer().read(0)['capturedEpochMs']
        return NativeScriptObservation(self.send,
            lambda: self.original(remote=remote, limit=NATIVE_FEATURE_LIMIT),
            clock, self.guard, self.process['pid'], ios=True,
            monotonic=self.monotonic, sleep=self.sleep)

    def script_fixture_files(self):
        self.guard()
        remote = self.remote.rsplit('/', 1)[0] + '/' + SCRIPT_FIXTURE_FILE
        def clock(): return self.native_observer().read(0)['capturedEpochMs']
        return NativeScriptFiles(self.send,
            lambda: self.original(remote=remote, limit=65536),
            clock, self.guard, self.process['pid'], ios=True,
            monotonic=self.monotonic, sleep=self.sleep)

    def installed_bundle(self):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+BUNDLE_FILE
        return NativeBundleObservation(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.guard,self.process['pid'],lambda:self.native_observer().read(0),monotonic=self.monotonic,sleep=self.sleep)

    def process_presence(self):
        self.guard(); remote = self.remote.rsplit('/', 1)[0] + '/' + PROCESS_PRESENCE_FILE
        def clock(): return self.native_observer().read(0)['capturedEpochMs']
        return NativeProcessPresence(self.send, lambda: self.original(remote=remote, limit=PROCESS_PRESENCE_LIMIT),
            clock, self.guard, self.process['pid'], ios=True, monotonic=self.monotonic, sleep=self.sleep)

    def location_bookmarks(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+BOOKMARKS_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSLocationBookmarks(self.send,lambda:self.original(remote=remote,limit=BOOKMARKS_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def places_model(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+PLACES_MODEL_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSPlacesModel(self.send,lambda:self.original(remote=remote,limit=PLACES_MODEL_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def scene_inventory(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+SCENE_INVENTORY_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSSceneInventory(self.send,lambda:self.original(remote=remote,limit=SCENE_INVENTORY_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def navigation_state(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+NAVIGATION_STATE_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSNavigationState(self.send,lambda:self.original(remote=remote,limit=NAVIGATION_STATE_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def avatar_social_http(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+AVATAR_SOCIAL_HTTP_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSAvatarSocialHttp(self.send,lambda:self.original(remote=remote,limit=AVATAR_SOCIAL_HTTP_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def people_model(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+PEOPLE_MODEL_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSPeopleModel(self.send,lambda:self.original(remote=remote,limit=PEOPLE_MODEL_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def create_work(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+CREATE_WORK_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSCreateWork(self.send,lambda:self.original(remote=remote,limit=CREATE_WORK_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def avatar_scripts(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+AVATAR_SCRIPTS_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSAvatarScripts(self.send,lambda:self.original(remote=remote,limit=AVATAR_SCRIPTS_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def avatar_entities(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+AVATAR_ENTITIES_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSAvatarEntities(self.send,lambda:self.original(remote=remote,limit=AVATAR_ENTITIES_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def create_entities(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+CREATE_ENTITIES_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSCreateEntities(self.send,lambda:self.original(remote=remote,limit=CREATE_ENTITIES_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def pointer_state(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+POINTER_STATE_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSPointerState(self.send,lambda:self.original(remote=remote,limit=POINTER_STATE_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def avatar_state(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+AVATAR_STATE_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSAvatarState(self.send,lambda:self.original(remote=remote,limit=AVATAR_STATE_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def script_work(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+SCRIPT_WORK_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return NativeScriptWork(self.send,lambda:self.original(remote=remote,limit=262144),
            clock,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)

    def script_terminal(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+SCRIPT_TERMINAL_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return NativeScriptTerminal(self.send,lambda:self.original(remote=remote,limit=SCRIPT_TERMINAL_LIMIT),
            clock,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)

    def script_dialogs(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+SCRIPT_DIALOGS_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSScriptDialogs(self.send,lambda:self.original(remote=remote,limit=SCRIPT_DIALOGS_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def emote_world(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+EMOTE_WORLD_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSEmoteWorld(self.send,lambda:self.original(remote=remote,limit=EMOTE_WORLD_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def avatar_world(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+AVATAR_WORLD_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSAvatarWorld(self.send,lambda:self.original(remote=remote,limit=AVATAR_WORLD_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def avatar_inputs(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+AVATAR_INPUTS_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSAvatarInputs(self.send,lambda:self.original(remote=remote,limit=AVATAR_INPUTS_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def avatar_renderers(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+AVATAR_RENDERERS_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSAvatarRenderers(self.send,lambda:self.original(remote=remote,limit=AVATAR_RENDERERS_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def create_state(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+CREATE_STATE_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSCreateState(self.send,lambda:self.original(remote=remote,limit=CREATE_STATE_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def create_files(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+CREATE_FILES_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSCreateFiles(self.send,lambda:self.original(remote=remote,limit=CREATE_FILES_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def navigation_dialogs(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+NAVIGATION_DIALOG_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSNavigationDialogs(self.send,lambda:self.original(remote=remote,limit=NAVIGATION_DIALOG_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def places_http(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+PLACES_HTTP_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSPlacesHttp(self.send,lambda:self.original(remote=remote,limit=PLACES_HTTP_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def navigation_replies(self):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+NAVIGATION_REPLIES_FILE
        def clock():return self.native_observer().read(0)['capturedEpochMs']
        return NativeNavigationReplies(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            clock,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)

    def pending_owner(self,intent=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+PENDING_OWNER_FILE
        def clock():return self.native_observer().read(0)['capturedEpochMs']
        return NativePendingCommitOwner(self.send,lambda:self.original(remote=remote,limit=32768),
            clock,self.guard,self.process['pid'],ios=True,intent=intent,monotonic=self.monotonic,sleep=self.sleep)

    def web_dom(self):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+WEB_DOM_FILE
        # A separately nonce-bound original native clock acquisition follows
        # the actual WK/DOM result. Host UTC is never a freshness substitute.
        def clock():return self.native_observer().read(0)['capturedEpochMs']
        return NativeWebDOMObservation(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            clock,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)

    def web_closures(self):
        self.guard(); remote=self.remote.rsplit('/',1)[0]+'/'+WEB_CLOSURES_FILE
        clock_source=self.native_observer()
        def clock(): return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSWebClosures(self.send,lambda:self.original(remote=remote,limit=WEB_CLOSURES_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def tablet_sources(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+TABLET_SOURCES_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSTabletSources(self.send,lambda:self.original(remote=remote,limit=TABLET_SOURCES_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def tablet_web(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+TABLET_WEB_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSTabletWebSource(self.send,lambda:self.original(remote=remote,limit=TABLET_WEB_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def tablet_web_closures(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+TABLET_CLOSURES_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSTabletWebClosures(self.send,lambda:self.original(remote=remote,limit=TABLET_CLOSURES_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def snapshot_inputs(self,clock_source=None):
        from ios.adapters.snapshot_inputs import IOSSnapshotInputs,FILE,LIMIT
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSSnapshotInputs(self.send,lambda:self.original(remote=remote,limit=LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def tablet_web_dom(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+TABLET_WEB_DOM_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSTabletWebDOM(self.send,lambda:self.original(remote=remote,limit=TABLET_WEB_DOM_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def world_web(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+WORLD_WEB_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSWorldWebSource(self.send,lambda:self.original(remote=remote,limit=WORLD_WEB_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def world_web_dom(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+WORLD_WEB_DOM_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSWorldWebDOM(self.send,lambda:self.original(remote=remote,limit=WORLD_WEB_DOM_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def world_web_work(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+WORLD_WEB_WORK_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSWorldWebWork(self.send,lambda:self.original(remote=remote,limit=WORLD_WEB_WORK_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)


    def world_web_geometry(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+WORLD_WEB_GEOMETRY_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSWorldWebGeometry(self.send,lambda:self.original(remote=remote,limit=WORLD_WEB_GEOMETRY_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)


    def world_web_keys(self,clock_source=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+WORLD_WEB_KEYS_FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSWorldWebKeys(self.send,lambda:self.original(remote=remote,limit=WORLD_WEB_KEYS_LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)



    def snapshot_exports(self,clock_source=None):
        from ios.adapters.snapshot_exports import IOSSnapshotExports,FILE,LIMIT
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSSnapshotExports(self.send,lambda:self.original(remote=remote,limit=LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def snapshot_work(self,clock_source=None):
        from ios.adapters.snapshot_work import IOSSnapshotWork,FILE,LIMIT
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSSnapshotWork(self.send,lambda:self.original(remote=remote,limit=LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def snapshot_captures(self,clock_source=None):
        from ios.adapters.snapshot_captures import IOSSnapshotCaptures,FILE,LIMIT
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+FILE
        if clock_source is None:clock_source=self.native_observer()
        def clock():return clock_source.read(clock_source.sequence)['capturedEpochMs']
        return IOSSnapshotCaptures(self.send,lambda:self.original(remote=remote,limit=LIMIT),
            clock,self.guard,self.process['pid'],monotonic=self.monotonic,sleep=self.sleep)

    def chat_view(self):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+CHAT_VIEW_FILE
        return NativeChatView(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)

    def chat_capture(self,owner,run):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+CHAT_FILE
        reader=NativeChatObservation(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)
        return OwnedChatCapture(reader,owner,run)

    def account_origin(self,store,binding,*,component_only=True):
        self.guard()
        native=self.native_observer();actual=native.read(0,require_account=True)
        remote=self.remote.rsplit('/',1)[0]+'/'+ACCOUNT_ORIGIN_FILE
        source=NativeAccountOrigin(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],actual['instance'],ios=True,
            monotonic=self.monotonic,sleep=self.sleep)
        result=OwnedAccountOrigin(source,store,binding,component_only=component_only)
        result.native_admission=deepcopy(actual)
        return result

    def account_probe(self,owner):
        self.guard()
        remote=self.remote.rsplit('/',1)[0]+'/'+ACCOUNT_PROBE_FILE
        probe=NativeAccountProbe(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],intent=owner.intent,ios=True,
            monotonic=self.monotonic,sleep=self.sleep)
        return OwnedAccountProbe(probe,owner)

    def completed_frame(self,intent):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+COMPLETED_FRAME_FILE
        return NativeCompletedFrame(self.send,lambda:self.original(remote=remote,limit=65536),
            self.epoch_ms,self.guard,self.process['pid'],intent,monotonic=self.monotonic,sleep=self.sleep)

    def vulkan_world_frame(self,intent,receipt=None):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+VULKAN_WORLD_FILE
        return NativeVulkanWorldFrame(self.send,lambda:self.original(remote=remote,limit=VULKAN_WORLD_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],intent,receipt=receipt,monotonic=self.monotonic,sleep=self.sleep)

    def scene_loads(self):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+SCENE_LOAD_FILE
        return NativeSceneLoads(self.send,lambda:self.original(remote=remote,limit=262144),
            self.epoch_ms,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)

    def graphics_subject(self):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+GRAPHICS_SUBJECT_FILE
        return NativeGraphicsSubject(self.send,lambda:self.original(remote=remote,limit=GRAPHICS_SUBJECT_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],ios=True,native_clock_bound=True,
            monotonic=self.monotonic,sleep=self.sleep)

    def world_render_capture(self,owner):
        self.guard()
        root=self.remote.rsplit('/',1)[0]+'/'
        def storage_file(name):
            if type(name) is not str or not re.fullmatch(r'world-render-storage-[0-9a-f]{32}\.json',name):
                raise NativeUIError('Original iOS world receipt is outside its closed inventory')
            return self.original(remote=root+name,limit=100000)
        options=dict(ios=True,monotonic=self.monotonic,sleep=self.sleep)
        storage=NativeWorldRenderStorage(self.send,storage_file,self.epoch_ms,self.guard,self.process['pid'],
            receipt_intent=owner.receipt_intent,**options)
        capture=NativeWorldRenderCapture(self.send,
            lambda:self.original(remote=root+WORLD_RENDER_FILE,limit=NATIVE_FEATURE_LIMIT),
            storage,self.epoch_ms,self.guard,self.process['pid'],intent=owner.intent,**options)
        receipts=NativeWorldReceiptCleanup(self.send,
            lambda:self.original(remote=root+WORLD_RECEIPT_FILE,limit=4096),
            self.epoch_ms,self.guard,self.process['pid'],owner.owned,lambda:storage.instance,**options)
        return OwnedWorldRenderCapture(capture,storage,owner,receipts)

    def read(self, after_sequence, *, include_avatar_entities=False):
        try:
            if type(after_sequence) is not int or after_sequence < self.sequence or type(include_avatar_entities) is not bool:
                raise ValueError()
            self.guard()
            request = 'ios-' + uuid.uuid4().hex
            command = dict(schemaVersion=1, commandId=request, action='normal-feature-observe',
                           includeAvatarEntities=include_avatar_entities)
            self.send(command)
            value, _epoch = read_native_diagnostic(self.original, self.epoch_ms, self.guard,
                after_sequence, expected_request=request, monotonic=self.monotonic, sleep=self.sleep)
            if self.instance is not None and value['instance'] != self.instance:
                raise ValueError()
            if include_avatar_entities:
                avatar_entities(value)
            elif {'avatarEntities', 'entitiesComplete'} & set(value):
                raise ValueError()
            self.guard()
            self.instance, self.sequence = value['instance'], value['sampleSequence']
            return value
        except Exception:
            raise NativeUIError('Native iOS feature observation failed') from None
