"""Independent actor journal protocol, deliberately outside adapter operations.

The coordinator stores observed facts, never evaluates assertions. An actor's
publisher token is provisioned only to that independent process, not to the
runner or adapter. The runner can activate challenges and read its own run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import json
import secrets
import threading
import time
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .contract import exact, identifier, number, state, json_document
from .fixtures import context
from .scenarios import SCENARIOS

# These are raw secondary observations, not acknowledgments of requested input.
# Full checkpoint semantics and actor measurement sources are in the handoff.
WITNESS_KEYS = {
 'world-navigation': ['location', 'bookmark', 'bookmarkName', 'searchResults', 'error'],
 'authentication': ['principal', 'dialog', 'error', 'pending', 'protectedAccess', 'delayedGrantOutstanding'],
 'avatar-people': ['avatar', 'scale', 'wearable', 'bookmarked', 'connection'],
 'create': ['objects', 'editor', 'picker', 'error', 'canRez', 'selection', 'textured', 'voxelValue'],
 'emotes': ['animation', 'sit', 'override', 'poseProgress','restoredBeforeNominalEnd'],
 'world-web': ['text', 'page', 'bridgeMessages'],
 'tablet-web': ['text', 'page', 'bridgeMessages'],
 'graphics': ['resolution', 'renderScale', 'haze', 'hazePass', 'mirror', 'mirrorPass'],
 'audio': ['recording', 'preview', 'muted', 'recordedFrames', 'playedFrames',
           'bufferedFrames', 'phase', 'history', 'error'],
 'chat': ['draft', 'messages', 'localMessages', 'domainMessages', 'peerMessages', 'channel', 'mixerConnected', 'focused', 'keyboard', 'open'],
 'snapshots': ['open','pending','captureHistory','files','saved','uploads','shares','saveBackend','savePermission','saveSheet','shareSheet','error'],
 'scripts': ['running', 'effects', 'companions'],
 'assets': ['mappings', 'selected', 'bakeState', 'canWrite', 'sceneModel', 'companions'],
 'lifecycle-input': ['heldInputs', 'worldDisplacement', 'generation'],
}


def projection(area, value):
    return {key: value[key] for key in WITNESS_KEYS[area]}


class Journal:
    """Bounded in-memory coordinator; persistence is private runner evidence only."""
    def __init__(self, clock=None):
        self.clock = clock or (lambda: time.time() * 1000)
        self.runs = {}
        self.lock = threading.RLock()

    def register(self, area):
        if area not in SCENARIOS:
            raise ValueError('Unknown feature area')
        with self.lock:
            if len(self.runs) >= 32:
                raise ValueError('Owned fixture run limit reached')
            run = secrets.token_hex(16)
            self.runs[run] = dict(area=area, ticket=None, entries=[], sequence=0,
                                  activeEpochMs=self.clock(), stimulus=None, tickets=set())
            return run

    def activate(self, run, ticket, verb='baseline', inputs=None):
        identifier(ticket)
        with self.lock:
            row = self.runs[identifier(run)]
            # Once a ticket is retired, no delayed source may relabel it current.
            if ticket in row['tickets']:
                raise ValueError('Fixture challenge ticket was reused')
            from .scenarios import actions, expand
            from .contract import typed_equal
            inputs = {} if inputs is None else inputs
            if verb not in {'baseline', 'cleanup'}:
                allowed = actions(row['area']).get(verb, [])
                if not any(typed_equal(inputs, expand(candidate, context(run))) for candidate in allowed):
                    raise ValueError('Independent stimulus is outside the closed inventory')
            elif inputs != {}:
                raise ValueError('Baseline/cleanup stimulus accepts no inputs')
            if len(row['tickets']) >= 256:
                raise ValueError('Owned challenge limit reached')
            row['tickets'].add(ticket)
            row.update(ticket=ticket, activeEpochMs=self.clock(), stimulus=dict(verb=verb, inputs=inputs))

    def publish(self, run, value):
        exact(value, {'ticket', 'actor', 'actorSequence', 'capturedEpochMs', 'facts'}, 'independent actor sample')
        with self.lock:
            row = self.runs[identifier(run)]
            if value['ticket'] != row['ticket']:
                raise ValueError('Actor sample belongs to a retired challenge')
            if value['actor'] != 'owned-observer':
                raise ValueError('Unregistered independent actor')
            seq = value['actorSequence']
            if type(seq) is not int or seq <= 0 or (row['entries'] and seq <= row['entries'][-1]['actorSequence']):
                raise ValueError('Independent actor sequence did not advance')
            captured = number(value['capturedEpochMs'], 1)
            if not row['activeEpochMs'] <= captured <= self.clock() + 250 or self.clock() - captured > 1500:
                raise ValueError('Actor sample is stale or from the future')
            expected_keys = WITNESS_KEYS[row['area']]
            exact(value['facts'], expected_keys, 'independently measured facts')
            combined = {**SCENARIOS[row['area']]['baseline'], **value['facts']}
            state(row['area'], combined, run)
            row['sequence'] += 1
            row['entries'].append(dict(copy.deepcopy(value), sequence=row['sequence'], receivedEpochMs=self.clock()))
            row['entries'] = row['entries'][-512:]

    def active(self, run):
        with self.lock:
            row = self.runs[identifier(run)]
            return dict(schemaVersion=1, runId=run, area=row['area'], ticket=row['ticket'], stimulus=copy.deepcopy(row['stimulus']))

    def has_ticket(self, run, ticket):
        with self.lock:
            return identifier(ticket) in self.runs[identifier(run)]['tickets']

    def snapshot(self, run):
        with self.lock:
            row = self.runs[identifier(run)]
            return dict(schemaVersion=1, runId=run, area=row['area'], ticket=row['ticket'],
                        sampleEpochMs=self.clock(), entries=copy.deepcopy(row['entries']))

    def close(self, run):
        with self.lock:
            self.runs.pop(identifier(run), None)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Owned fixture control redirects are forbidden')


class Client:
    def __init__(self, url, reader_token,*,monotonic=time.monotonic,sleep=time.sleep):
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.path != '/feature-fixture/v1'
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or type(reader_token) is not str or len(reader_token) < 32 or not callable(monotonic) or not callable(sleep)):
            raise ValueError('Private feature fixture configuration is incomplete')
        self.url, self.token = url, reader_token
        self.monotonic,self.sleep=monotonic,sleep

    def request(self, path, value=None, method=None):
        raw = None if value is None else json.dumps(value).encode()
        request = Request(self.url + path, data=raw, method=method,
                          headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with build_opener(NoRedirect).open(request, timeout=5) as response:
                body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                raise ValueError('Feature fixture response exceeds the bounded limit')
            return json_document(body)
        except Exception as error:
            if hasattr(error, 'close'):
                error.close()
            # Do not print URLs, headers, account details or provider exceptions.
            raise ValueError('Owned feature fixture transport failed') from error

    def register(self, area):
        if getattr(self,'run',None) is not None and not getattr(self,'closed',False):
            raise ValueError('An existing owned fixture run must close first')
        if area=='authentication':
            from urllib.parse import urlsplit
            if urlsplit(self.url).scheme!='https':raise ValueError('Authentication requires the trusted HTTPS account fixture')
            provider=self.request('/account-provider')
            exact(provider,{'providerVersion','instance','transport','tlsVersion','internalErrors'},'account provider readiness')
            if (type(provider['providerVersion']) is not int or provider['providerVersion']!=2 or provider['transport']!='https'
                    or provider['tlsVersion'] not in ('TLSv1.2','TLSv1.3') or type(provider['internalErrors']) is not int
                    or provider['internalErrors']!=0):raise ValueError('Required account provider is unavailable')
            self.account_instance=identifier(provider['instance'])
            self.account_sequence=self.account_epoch=0
        result = self.request('/runs', {'area': area})
        exact(result, {'runId'}, 'feature fixture registration')
        self.run = identifier(result['runId'])
        self.area,self.closed=area,False
        return self.run, self.url + '/runs/' + self.run + '/'

    def activate(self, ticket, verb='baseline', inputs=None):
        self.request('/runs/' + self.run + '/active', {'ticket': ticket, 'verb': verb, 'inputs': inputs or {}})

    def observe(self):
        return self.request('/runs/' + self.run)

    def close(self):
        if getattr(self,'closed',False):return
        if self.area=='authentication':
            started=previous=number(self.monotonic())
            self.account_control('cleanup') # Exactly once; an uncertain mutation is never replayed here.
            for attempt in range(51):
                status=self.account_status()
                now=number(self.monotonic())
                if now<previous or now-started>=5:raise ValueError('Account fixture cleanup exceeded its bound')
                previous=now
                if (not status['accountExists'] and not status['armedHold'] and status['heldRequests']==0 and status['inflightRequests']==0
                        and status['accessTokens']==0 and status['refreshTokens']==0):break
                if attempt==50:raise ValueError('Account fixture cleanup is incomplete')
                self.sleep(.05)
        self.request('/runs/' + self.run, method='DELETE')
        if self.area=='authentication':
            now=number(self.monotonic())
            if now<previous or now-started>=5:raise ValueError('Account fixture cleanup exceeded its bound')
        self.closed=True

    def account_status(self):
        from .contract import number
        value=self.request('/runs/'+self.run+'/account/status')
        exact(value,{'providerVersion','instance','runId','capturedEpochMs','eventSequence','accountExists',
            'heldRequests','armedHold','inflightRequests','accessTokens','refreshTokens','grantsEnabled'},'account provider status')
        if (type(value['providerVersion']) is not int or value['providerVersion']!=2 or value['instance']!=self.account_instance
                or value['runId']!=self.run or any(type(value[k]) is not bool for k in ('accountExists','armedHold','grantsEnabled'))
                or any(type(value[k]) is not int or value[k]<0 for k in ('eventSequence','heldRequests','inflightRequests','accessTokens','refreshTokens'))
                or type(value['capturedEpochMs']) is not int or value['capturedEpochMs']<self.account_epoch
                or value['eventSequence']<self.account_sequence
                or value['heldRequests']>1 or value['inflightRequests']>16 or value['accessTokens']>64 or value['refreshTokens']>64):
            raise ValueError('Account fixture status is invalid')
        number(value['capturedEpochMs'],1)
        self.account_epoch,self.account_sequence=value['capturedEpochMs'],value['eventSequence']
        return value

    def account_control(self,operation):
        if self.area!='authentication' or self.closed or operation not in ('hold-next','release-delayed','revoke-issued','cleanup'):
            raise ValueError('Unknown or retired account control')
        self.request('/runs/'+self.run+'/account/control',{'operation':operation})

    def account_credentials(self,role):
        if self.area!='authentication' or role not in ('owned','invalid','delayed'):raise ValueError('Unknown owned account role')
        value=self.request('/runs/'+self.run+'/account/credentials/'+role)
        exact(value,{'username','password'},'private fixture credentials')
        if any(type(v) is not str or not 0<len(v)<=512 or any(ord(c)<32 for c in v) for v in value.values()):
            raise ValueError('Private fixture credentials are invalid')
        return value # Caller must keep these out of public adapter requests, logs and reports.
