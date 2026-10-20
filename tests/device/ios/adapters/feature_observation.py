"""Original native feature reads over the existing owned HTTP/AFC component.

This transport does not establish installed-code identity or advertise a feature
capability. Canonical physical binding independently establishes that join
before exposing these components; direct component use remains unbound.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
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
from ios.adapters.bundle_observation import NativeBundleObservation, FILE as BUNDLE_FILE, command as bundle_command
from adapters.private_login_input import command as private_input_command
from adapters.native_account_origin import (NativeAccountOrigin, OwnedAccountOrigin, FILE as ACCOUNT_ORIGIN_FILE,
    command as account_origin_command)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def post_request(request, timeout):
    try:
        return build_opener(NoRedirect()).open(request, timeout=timeout)
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
        elif command.get('action')=='feature-web-dom-observe':web_dom_command(command,ios=True)
        elif command.get('action')=='feature-pending-commit-owner':pending_owner_command(command,ios=True)
        elif command.get('action')=='ios-bundle-observe':bundle_command(command)
        elif command.get('action') == 'feature-account-probe':account_probe_command(command,ios=True)
        elif command.get('action') == 'feature-account-origin':account_origin_command(command,ios=True)
        elif command.get('action') == 'feature-world-render-storage':world_storage_command(command,ios=True)
        elif command.get('action') == 'feature-world-render-receipt':world_receipt_command(command,ios=True)
        payload = json.dumps(command).encode()
        if len(payload) > limit:
            raise NativeUIError("Native iOS feature command exceeds its transport bound")
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
        return NativeScriptObservation(self.send,
            lambda: self.original(remote=remote, limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms, self.guard, self.process['pid'], ios=True,
            monotonic=self.monotonic, sleep=self.sleep)

    def script_fixture_files(self):
        self.guard()
        remote = self.remote.rsplit('/', 1)[0] + '/' + SCRIPT_FIXTURE_FILE
        return NativeScriptFiles(self.send,
            lambda: self.original(remote=remote, limit=65536),
            self.epoch_ms, self.guard, self.process['pid'], ios=True,
            monotonic=self.monotonic, sleep=self.sleep)

    def installed_bundle(self):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+BUNDLE_FILE
        return NativeBundleObservation(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.guard,self.process['pid'],lambda:self.native_observer().read(0),monotonic=self.monotonic,sleep=self.sleep)

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

    def chat_view(self):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+CHAT_VIEW_FILE
        return NativeChatView(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)

    def chat_capture(self,owner,run):
        self.guard();remote=self.remote.rsplit('/',1)[0]+'/'+CHAT_FILE
        reader=NativeChatObservation(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],ios=True,monotonic=self.monotonic,sleep=self.sleep)
        return OwnedChatCapture(reader,owner,run)

    def account_origin(self,store,binding):
        self.guard()
        native=self.native_observer();actual=native.read(0,require_account=True)
        remote=self.remote.rsplit('/',1)[0]+'/'+ACCOUNT_ORIGIN_FILE
        source=NativeAccountOrigin(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],actual['instance'],ios=True,
            monotonic=self.monotonic,sleep=self.sleep)
        return OwnedAccountOrigin(source,store,binding,component_only=True)

    def account_probe(self,owner):
        self.guard()
        remote=self.remote.rsplit('/',1)[0]+'/'+ACCOUNT_PROBE_FILE
        probe=NativeAccountProbe(self.send,lambda:self.original(remote=remote,limit=NATIVE_FEATURE_LIMIT),
            self.epoch_ms,self.guard,self.process['pid'],intent=owner.intent,ios=True,
            monotonic=self.monotonic,sleep=self.sleep)
        return OwnedAccountProbe(probe,owner)

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
