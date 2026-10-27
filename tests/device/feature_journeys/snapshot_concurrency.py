"""Actual owned-domain policy projected into the normal Script GET protocol.

This is controlled fixture concurrency, not external metaverse registration.
No desired canShare/result/count, domain transition or policy setter exists.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import base64
from copy import deepcopy
from datetime import datetime
import hashlib
import re
import os
import threading
import uuid
from urllib.parse import parse_qsl
from adapters.native_feature_observation import need
from feature_journeys.snapshot_domain_client import SnapshotDomainClient
from feature_journeys.snapshot_upload_provider import encode


def query(raw):
    need(type(raw) is str and len(raw)<=1024 and raw.isascii());pairs=parse_qsl(raw,keep_blank_values=True,strict_parsing=True,max_num_fields=4)
    value=dict(pairs);need(len(pairs)==len(value)==4 and set(value)=={'now','include_actions','domain_id','restriction'} and value['include_actions']=='concurrency' and value['restriction']=='open,hifi'
        and re.fullmatch('[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',value['domain_id'])
        and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z',value['now']))
    datetime.fromisoformat(value['now'].replace('Z','+00:00'));return value


class SnapshotConcurrency:
    def __init__(self,uploads,domain_client):
        from feature_journeys.snapshot_upload_provider import SnapshotUploadProvider
        need(type(uploads) is SnapshotUploadProvider and type(domain_client) is SnapshotDomainClient)
        self.uploads,self.client=uploads,domain_client;self.lock=threading.RLock();self.requests={};self.responses={};self.originals={};self.sequence=0
    @contextmanager
    def response(self,raw_query,authorization):
        actual=query(raw_query)
        with self.lock,self.uploads.lock:
            run=self.uploads.resolve(authorization)
            if run is None:yield 401,b'{"status":"fail","error":"unauthorized"}',None,None;return
            scope=self.uploads.runs[run];need(scope['ticket'] is not None);rows=self.requests.setdefault(run,[]);need(len(rows)<64 and all(row['left'] for row in rows))
            response_id=uuid.uuid4().hex;row=dict(requestId=response_id,query=actual,querySha256=hashlib.sha256(raw_query.encode()).hexdigest(),ticket=scope['ticket'],
                domainReadNonce=uuid.uuid4().hex,source=None,entered=self.uploads.clock(),status=None,responseBytes=None,responseSha256=None,written=False,failed=False,left=None)
            rows.append(row)
            query_bytes=raw_query.encode('ascii')
            evidence=dict(requestId=response_id,prepared=None,written=None,original=None,
                requestQueryOriginal=dict(base64=base64.b64encode(query_bytes).decode(),bytes=len(query_bytes),sha256=hashlib.sha256(query_bytes).hexdigest()))
            self.responses[response_id]=evidence
            try:
                original=self.client.read(run,row['domainReadNonce']);row['source']=deepcopy(original)
                packet=original['packet'];count=int(packet['online'] and packet['domainId']==actual['domain_id'] and packet['restriction'] in ('open','hifi'))
                result=dict(status='success',total_entries=count,user_stories=[dict(action='concurrency',domain_id=packet['domainId'])] if count else [],
                    fixtureConcurrency=dict(controlled=True,externalRegistrationRequired=True,domainId=packet['domainId'],restriction=packet['restriction']))
                raw=encode(result);row.update(status=200,responseBytes=len(raw),responseSha256=hashlib.sha256(raw).hexdigest())
                evidence.update(prepared=self.uploads.clock(),original=dict(base64=base64.b64encode(raw).decode(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                def written(value):
                    need(not row['written'] and row['left'] is None and value==dict(status=200,responseId=response_id,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                    evidence['written']=self.uploads.clock();row['written']=True
                yield 200,raw,response_id,written
            except BaseException:row['failed']=True;raise
            finally:row['left']=self.uploads.clock()
    def snapshot(self,run):
        from feature_journeys.contract import identifier
        identifier(run)
        with self.lock:
            rows=[]
            for original in self.requests.get(run,[]):
                row=deepcopy(original)
                if row['source'] is not None:
                    import base64
                    row['source']['rawBase64']=base64.b64encode(row['source'].pop('raw')).decode()
                rows.append(row)
            return dict(snapshotConcurrencyVersion=1,runId=run,configuration=self.client.public(),requests=rows,controlledFixtureProjectionOnly=True,externalRegistrationRequired=True,resourceRetirementRequired=True)
    def original(self,run,nonce):
        from feature_journeys.contract import identifier
        identifier(run);identifier(nonce)
        with self.lock,self.uploads.lock:
            need(run in self.uploads.runs);key=(run,nonce)
            if key not in self.originals:
                need(len(self.originals)<64);scope=self.uploads.runs[run];snapshot=self.snapshot(run);self.sequence+=1
                packet=dict(snapshotConcurrencyOriginalVersion=1,runId=run,requestId=nonce,sequence=self.sequence,clock=self.uploads.clock(),
                    instance=self.uploads.instance,processId=os.getpid(),clockDomain='snapshot-backend-host',accountProvider=self.uploads.authenticate.provider.instance,accountRun=scope['accountRun'],
                    principalSha256=hashlib.sha256(scope['principal'].encode()).hexdigest(),created=scope['created'],ticket=scope['ticket'],snapshot=snapshot,
                    responses=[deepcopy(self.responses[row['requestId']]) for row in snapshot['requests'] if row['requestId'] in self.responses],
                    sourceJournalRetirementRequired=True,frontendResponseConsumptionRequired=True,wholeFeatureRequired=True)
                raw=encode(packet);need(len(raw)<=700*1024)
                self.originals[key]=dict(snapshotConcurrencyExportVersion=1,runId=run,requestId=nonce,
                    original=dict(base64=base64.b64encode(raw).decode(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
            return deepcopy(self.originals[key])
    def assert_quiet_locked(self,run):
        # Called with uploads.lock held after actual authority revocation.
        # Positive request writers hold that same lock for their full context;
        # acquiring our outer lock here would invert the request lock order.
        need(all(row['left'] is not None and (row['written'] or row['failed']) for row in self.requests.get(run,[])))
