"""Original normal-login input; no acknowledgement is a login verdict.

The owner persists input intent and supplies its private controlled credentials.
Full Authentication additionally needs independent account/profile/UI witnesses,
source-bound restart, logout, fixture authority and observed cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import math
import re
import time
from adapters.native_account_origin import origin_text
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_ui import NativeUIError

VERSION=1
IDS=frozenset({'login.entry','login.page','login.username','login.password','login.submit','login.cancel'})
PAGE={'profile','domain','waiting','closing','error','accountInstance','credentialGeneration',
      'endpointSha256','nativePending','tokenPresent'}


def metadata_fields(identifier):
    need(type(identifier) is str and identifier in IDS)
    return {'inputReady'} | (PAGE if identifier=='login.page' else set())


def validate_metadata(row):
    identifier=row.get('id');fields=metadata_fields(identifier)
    exact(row,{'id','token','enabled','focused'}|fields)
    need(type(row['token']) is str and re.fullmatch('[0-9a-f]{32}',row['token'])
         and all(type(row[k]) is bool for k in ('enabled','focused','inputReady'))
         and (not row['inputReady'] or row['enabled']))
    if identifier=='login.page':
        need(row['inputReady'] is False and row['profile']=='phone-login-v1'
             and all(type(row[k]) is bool for k in ('domain','waiting','closing','nativePending','tokenPresent'))
             and type(row['error']) is str and row['error'] in ('none','invalid-credentials','other','unavailable')
             and type(row['accountInstance']) is str and re.fullmatch('[0-9a-f]{32}',row['accountInstance'])
             and integer(row['credentialGeneration'],1,2**53-1)
             and type(row['endpointSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['endpointSha256']))


class TokenLoginUI:
    def __init__(self,io,intent,run,origin,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (intent,monotonic,sleep))
             and type(run) is str and re.fullmatch('[0-9a-f]{32}',run))
        self.io,self.intent,self.run=io,intent,run
        origin_text(origin)
        self.endpoints={hashlib.sha256(v.encode()).hexdigest() for v in (origin,origin+'/')}
        self.monotonic,self.sleep=monotonic,sleep
        self.identity=self.account_instance=self.last_clock=None;self.account_generation=0

    @staticmethod
    def row(value,identifier):
        rows=[r for r in value['controls'] if r['id']==identifier]
        need(len(rows)<=1)
        return rows[0] if rows else None

    def now(self):
        value=self.monotonic()
        need(type(value) in (int,float) and math.isfinite(value)
             and (self.last_clock is None or value>=self.last_clock))
        self.last_clock=value;return value

    def capture(self):
        value=self.io.capture()
        need(type(value) is dict and type(value.get('loginControlsVersion')) is int and value['loginControlsVersion']==VERSION
             and value.get('ready') is True and type(value.get('controls')) is list and len(value['controls'])<=6)
        identity=(value.get('instance'),value.get('generation'))
        need(all(type(k) is str and re.fullmatch('[0-9a-f]{32}',k) for k in identity)
             and self.identity in (None,identity))
        ids=set();tokens=set()
        for row in value['controls']:
            need(type(row) is dict);validate_metadata(row)
            need(row['id'] not in ids and row['token'] not in tokens)
            ids.add(row['id']);tokens.add(row['token'])
        page=self.row(value,'login.page')
        if page:
            need(self.account_instance in (None,page['accountInstance'])
                 and page['credentialGeneration']>=self.account_generation
                 and page['endpointSha256'] in self.endpoints and page['error']!='unavailable')
            self.account_instance=page['accountInstance'];self.account_generation=page['credentialGeneration']
            for row in value['controls']:
                if row['id'] in {'login.username','login.password','login.submit'} and row['inputReady']:
                    need(not any(page[k] for k in ('domain','waiting','closing','nativePending','tokenPresent')))
                if row['id']=='login.cancel' and row['inputReady']:need(not page['domain'] and not page['closing'])
        else:need(ids<={'login.entry'})
        self.identity=identity;return value

    def wait(self,predicate,*,stable=0):
        started=self.now();since=None
        for _attempt in range(101):
            value=self.capture();now=self.now()
            if now-started>10:break
            if predicate(value):
                since=now if since is None else since
                if now-since>=stable:return value
            else:since=None
            if now-started>=10:break
            self.sleep(min(0.1,max(0,10-(now-started))))
        raise NativeUIError('Normal login view did not reach its observed state')

    def _input(self,identifier,action,*,text=None):
        value=self.capture();row=self.row(value,identifier)
        need(row is not None and row['enabled'] and row['inputReady'])
        page=self.row(value,'login.page')
        if identifier!='login.entry':need(page is not None and not page['domain'] and not page['closing'])
        if action in ('replace','submit'):need(row['focused'])
        # Intent contains native scope/control metadata only; never text.
        self.intent('login-'+action,value,identifier)
        self.io.input(identifier,action,token=row['token'],text=text)

    def open(self):
        value=self.capture()
        if self.row(value,'login.page') is None:self._input('login.entry','activate')
        return self.wait(lambda v:self.row(v,'login.page') is not None
            and not self.row(v,'login.page')['domain'] and not self.row(v,'login.page')['closing'])

    def fill(self,credentials):
        try:
            exact(credentials,{'username','password'})
            need(credentials['username']=='e2e-'+self.run
                 and all(type(v) is str and 0<len(v)<=4096 and all(32<=ord(c)<=126 for c in v) for v in credentials.values()))
            for identifier,key in (('login.username','username'),('login.password','password')):
                self._input(identifier,'activate')
                self.wait(lambda v:self.row(v,identifier) is not None and self.row(v,identifier)['focused'])
                self._input(identifier,'replace',text=credentials[key])
        except Exception:raise NativeUIError('Normal controlled login input failed') from None

    def submit(self):
        # Return delivery only. Native protected profile/UI/authority witnesses
        # must determine the outcome; never set principal/error/pending here.
        self._input('login.password','submit')

    def cancel(self):
        if self.row(self.capture(),'login.page') is not None:self._input('login.cancel','activate')
        return self.wait(lambda v:self.row(v,'login.page') is None,stable=0.3)
