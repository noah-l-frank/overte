"""Passive policy of one actual owned domain; no permission/control method.

Only bounded GET /id and GET /settings.json exist here. Raw settings can contain
private fields: retain their hash/length and the two public policy bits only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import ipaddress
import json
import re
import secrets
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request,build_opener
from adapters.native_feature_observation import need,number
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from fixture.create_rez_authority import NoRedirect,process

PATH='/v1/snapshot-domain-policy'


class SnapshotDomainPolicy:
    def __init__(self,origin,owned_domain,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        url=urlsplit(origin)
        need(url.scheme=='http' and url.hostname is not None and ipaddress.ip_address(url.hostname).is_loopback and url.port is not None
            and not url.path and not url.username and not url.password and not url.query and not url.fragment and all(callable(value) for value in (owned_domain,epoch_ms,monotonic)))
        self.origin,self.owned_domain,self.epoch_ms,self.monotonic=origin,owned_domain,epoch_ms,monotonic
        self.binding=deepcopy(process(owned_domain()));self.instance=secrets.token_hex(16);self.sequence=0;self.last_epoch=0;self.last_mono=0.;self.lock=threading.RLock();self.queries={};self.bindings={}
    def guard(self):need(same(process(self.owned_domain()),self.binding))
    def clock(self):
        epoch,mono=self.epoch_ms(),self.monotonic();need(type(epoch) is int and epoch>=max(1,self.last_epoch) and number(mono,self.last_mono,1e15))
        self.last_epoch,self.last_mono=epoch,mono;return dict(epochMs=epoch,monotonicMs=mono*1000)
    def get(self,path,limit):
        need(path in ('/id','/settings.json'));self.guard();request=Request(self.origin+path,method='GET')
        with build_opener(NoRedirect()).open(request,timeout=2) as response:
            raw=response.read(limit+1);need(response.status==200 and type(raw) is bytes and len(raw)<=limit)
        self.guard();return raw
    def read(self,run,nonce):
        identifier(run);identifier(nonce)
        with self.lock:
            self.guard();key=(run,nonce)
            if key in self.queries:return deepcopy(self.queries[key])
            need(len(self.queries)<64 and (run in self.bindings or len(self.bindings)<16));before=self.clock()
            raw_id=self.get('/id',128)
            try:actual=raw_id.decode('ascii').strip().strip('{}')
            except UnicodeError:need(False)
            need(actual==self.binding['domainId']);raw=self.get('/settings.json',1024*1024)
            def pairs(entries):
                result={}
                for key,value in entries:need(key not in result);result[key]=value
                return result
            try:value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _value:need(False))
            except (UnicodeError,ValueError):need(False)
            need(type(value) is dict and type(value.get('values')) is dict and type(value['values'].get('security')) is dict)
            rows=value['values']['security'].get('standard_permissions');need(type(rows) is list and len(rows)==4);permissions={}
            for row in rows:
                need(type(row) is dict and row.get('permissions_id') in ('anonymous','friends','localhost','logged-in') and row['permissions_id'] not in permissions and type(row.get('id_can_connect')) is bool)
                permissions[row['permissions_id']]=row['id_can_connect']
            restriction='open' if permissions['anonymous'] else 'hifi' if permissions['logged-in'] else 'acl'
            self.guard();after=self.clock();need(all(0<=after[key]-before[key]<5000 for key in before) and abs(after['epochMs']-before['epochMs']-(after['monotonicMs']-before['monotonicMs']))<=250)
            if run in self.bindings:need(same(self.bindings[run],self.binding))
            else:self.bindings[run]=deepcopy(self.binding)
            self.sequence+=1;packet=dict(snapshotDomainPolicyVersion=1,instance=self.instance,sequence=self.sequence,runId=run,requestId=nonce,binding=deepcopy(self.binding),
                clockDomain='owned-domain-policy-host',clockBefore=before,clockAfter=after,domainId=actual,online=True,
                standardConnect=dict(anonymous=permissions['anonymous'],loggedIn=permissions['logged-in']),restriction=restriction,
                idOriginal=dict(bytes=len(raw_id),sha256=hashlib.sha256(raw_id).hexdigest()),settingsOriginal=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),
                externalRegistrationRequired=True,controlledFixtureProjectionOnly=True,resourceRetirementRequired=True)
            self.queries[key]=deepcopy(packet);return packet


def serve(handler):
    tokens=handler.headers.get_all('X-Overte-Snapshot-Domain-Reader',[]);expected=handler.snapshot_domain_reader_token
    if type(expected) is not str or len(tokens)!=1 or not tokens[0].isascii() or not 32<=len(tokens[0])<=128:
        handler.send_error(404);return
    import hmac
    if not hmac.compare_digest(tokens[0],expected) or handler.snapshot_domain_policy is None:handler.send_error(404);return
    try:
        runs=handler.headers.get_all('X-Overte-Snapshot-Run',[]);nonces=handler.headers.get_all('X-Overte-Snapshot-Read',[]);lengths=handler.headers.get_all('Content-Length',[])
        need(len(runs)==len(nonces)==1 and lengths in ([],['0']) and not handler.headers.get('Transfer-Encoding') and not handler.headers.get('Content-Encoding'))
        packet=handler.snapshot_domain_policy(identifier(runs[0]),identifier(nonces[0]));raw=json.dumps(packet,separators=(',',':'),sort_keys=True,allow_nan=False).encode()
        need(len(raw)<=16384);handler.send_response(200);handler.send_header('Content-Type','application/json');handler.send_header('Content-Length',str(len(raw)));handler.send_header('Cache-Control','no-store');handler.end_headers();handler.wfile.write(raw)
    except (ValueError,UnicodeError):handler.send_error(400,'invalid Snapshot domain observation')
    except (OSError,RuntimeError):handler.send_error(503,'owned Snapshot domain observation is unavailable')
