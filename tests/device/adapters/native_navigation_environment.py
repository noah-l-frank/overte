"""Original selected/effective directory, passive account and login-field source."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
import uuid
from urllib.parse import urlsplit

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.native_account_observation import validate as account_packet, accept as account_continuation
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import nonce

VERSION = 1
FILE = 'feature-navigation-environment.json'
HEX = r'[0-9a-f]{32}'
DIGEST = r'[0-9a-f]{64}'
EMPTY = hashlib.sha256(b'').hexdigest()


def endpoint(value):
    # Original default directory has a /server prefix. Restoration must retain
    # that path; an origin-only authentication fixture validator is insufficient.
    need(type(value) is str and 0 < len(value) <= 1024 and value.isascii()
         and all(32 < ord(c) < 127 for c in value) and '@' not in value and '\\' not in value)
    parsed = urlsplit(value);port = parsed.port
    need(parsed.scheme == 'https' and parsed.hostname and parsed.username is None and parsed.password is None
         and not parsed.query and not parsed.fragment and '?' not in value and '#' not in value
         and not parsed.netloc.endswith(':') and parsed.netloc == parsed.netloc.lower()
         and (port is None or 1 <= port <= 65535) and parsed.geturl() == value)
    return value


def command(value):
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['action'] == 'feature-navigation-environment'
         and all(type(value[k]) is str and re.fullmatch(HEX, value[k]) for k in ('commandId', 'runId')))
    return value


def validate(value, request, pid, epoch):
    command(request)
    exact(value, {'navigationEnvironmentVersion', 'commandId', 'runId', 'instance', 'sequence', 'processId', 'capturedEpochMs',
                  'selectedSettingPresent', 'selectedServer', 'effectiveServer', 'environmentOverride', 'otherSettingsSha256', 'account', 'ui'})
    need(type(value['navigationEnvironmentVersion']) is int and value['navigationEnvironmentVersion'] == VERSION
         and value['commandId'] == request['commandId'] and value['runId'] == request['runId']
         and type(value['instance']) is str and re.fullmatch(HEX, value['instance'])
         and integer(value['sequence'], 1, 4096) and integer(pid, 1) and value['processId'] == pid and integer(value['processId'], 1)
         and type(value['selectedSettingPresent']) is bool and type(value['environmentOverride']) is bool
         and type(value['otherSettingsSha256']) is str and re.fullmatch(DIGEST, value['otherSettingsSha256']))
    fresh(value['capturedEpochMs'], epoch)
    endpoint(value['selectedServer']);endpoint(value['effectiveServer'])
    account_packet(value['account'], value['capturedEpochMs'])
    ui = value['ui']
    exact(ui, {'bridgeId', 'generation', 'sequence', 'elapsedMs', 'observedEpochMs', 'loginPageAlive', 'passwordEmpty', 'serverDraftSha256', 'serverFocused'})
    need(nonce(ui['bridgeId']) and nonce(ui['generation']) and integer(ui['sequence']) and integer(ui['elapsedMs'])
         and integer(ui['observedEpochMs'], 1) and 0 <= value['capturedEpochMs'] - ui['observedEpochMs'] <= 1500
         and type(ui['loginPageAlive']) is bool)
    need(type(ui['passwordEmpty']) is bool if ui['loginPageAlive'] else ui['passwordEmpty'] is None)
    if ui['serverDraftSha256'] is None:
        need(ui['serverFocused'] is None)
    else:
        need(type(ui['serverDraftSha256']) is str and re.fullmatch(DIGEST, ui['serverDraftSha256'])
             and type(ui['serverFocused']) is bool and ui['loginPageAlive'])
    return value


def continuation(previous, current):
    need(current['instance'] == previous['instance'] and current['processId'] == previous['processId']
         and current['sequence'] > previous['sequence'] and current['capturedEpochMs'] >= previous['capturedEpochMs']
         and current['ui']['bridgeId'] == previous['ui']['bridgeId']
         and all(current['ui'][k] >= previous['ui'][k] for k in ('sequence', 'elapsedMs', 'observedEpochMs')))
    account_continuation(previous['account']['observation'], current['account'])


def logged_out(value):
    account = value['account'];observation = account['observation']
    need(not account['loggedIn'] and account['principalSha256'] == EMPTY
         and not any(observation[k] for k in ('tokenPresent', 'refreshPresent', 'loginPending', 'refreshPending')))


class NativeNavigationEnvironment:
    def __init__(self, send, original, clock_ms, guard, pid, *, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(f) for f in (send, original, clock_ms, guard, monotonic, sleep)) and integer(pid, 1))
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, original, clock_ms, guard, pid
        self.monotonic, self.sleep = monotonic, sleep
        self.last = None;self.requests = set()

    def read(self, run):
        request = dict(schemaVersion=1, commandId=uuid.uuid4().hex, action='feature-navigation-environment', runId=run)
        try:
            command(request);need(len(self.requests) < 4096 and request['commandId'] not in self.requests)
            self.requests.add(request['commandId'])
            need(self.guard() is not False);started = previous = self.monotonic();need(number(started, 0, 1e15))
            self.send(deepcopy(request))
            for attempt in range(51):
                now = self.monotonic();need(number(now, 0, 1e15) and previous <= now and now - started < 5 and self.guard() is not False)
                previous = now;raw = self.original()
                try:
                    value = decode(raw) if raw else None
                except (ValueError, NativeUIError):
                    value = None
                if type(value) is dict and value.get('commandId') == request['commandId']:
                    validate(value, request, self.pid, self.clock_ms())
                    if self.last is not None:
                        continuation(self.last, value)
                    now = self.monotonic();need(number(now, 0, 1e15) and previous <= now and now - started < 5 and self.guard() is not False)
                    self.last = deepcopy(value);return value
                now = self.monotonic();need(number(now, 0, 1e15) and previous <= now);previous = now
                if now - started >= 5 or attempt == 50:
                    break
                self.sleep(min(.1, 5 - (now - started)))
        except Exception:
            raise NativeUIError('Original navigation environment source failed') from None
        raise NativeUIError('Original navigation environment source failed')
