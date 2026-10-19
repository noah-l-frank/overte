"""Original native feature reads over the existing owned HTTP/AFC component.

This transport does not establish installed-code identity or advertise a feature
capability. The canonical bound adapter remains blocked until that join exists.
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
from ios.adapters.appium_adapter import AppiumAdapter, WebDriverRequestError


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
        payload = json.dumps(command).encode()
        with post_request(Request(self.origin + '/e2e-client-command.json', data=payload,
                method='POST', headers={'Content-Type': 'application/json'}), timeout=5) as response:
            content = response.read(4097)
            def pairs(items):
                value = {}
                for key, item in items:
                    if key in value:
                        raise ValueError()
                    value[key] = item
                return value
            echo = json.loads(content, object_pairs_hook=pairs)
            if (response.status != 200 or len(content) > 4096 or echo != command
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
