"""Independent original HTTPS receiver joins, never upload ACK projections."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import secrets
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,fresh,integer,need
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending
from overte_phone_snapshot_upload_source import source,require_retired,sha
from overte_phone_snapshot_source import nonce


def file(value):
    exact(value,{'name','device','inode','bytes','sha256'})
    need(type(value['name']) is str and re.fullmatch(r'snapshot-[0-9a-f]{32}-[0-9a-f]{32}\.(body|reply)',value['name']) and integer(value['device']) and integer(value['inode'],1) and integer(value['bytes'],0,32*1024*1024));sha(value['sha256'])


def validate(value,run,request,epoch,*,previous=None):
    exact(value,{'snapshotUploadServiceVersion','instance','runId','requestId','capturedEpochMs','domainId','origin','active','ticket','activations','inflight','held','failedResponses','foreignRequests','lateRequests','requests','uploads','stories'})
    import uuid
    need(type(value['snapshotUploadServiceVersion']) is int and value['snapshotUploadServiceVersion']==1 and nonce(value['instance']) and value['runId']==run and nonce(run) and value['requestId']==request and nonce(request) and integer(value['capturedEpochMs'],1) and type(value['active']) is bool and type(value['held']) is bool)
    fresh(value['capturedEpochMs'],epoch);need(str(uuid.UUID(value['domainId']))==value['domainId'] and uuid.UUID(value['domainId']).int!=0)
    origin=urlsplit(value['origin']);need(origin.scheme=='https' and origin.hostname and origin.port and not origin.username and not origin.password and not origin.path and not origin.query and not origin.fragment)
    for key in ('inflight','failedResponses','foreignRequests','lateRequests','uploads','stories'):need(integer(value[key],0,4096))
    need(value['failedResponses']==value['foreignRequests']==value['lateRequests']==0)
    need(type(value['activations']) is list and len(value['activations'])<=256 and type(value['requests']) is list and len(value['requests'])<=128 and (value['ticket'] is None or nonce(value['ticket'])))
    tickets=set();last=0
    for row in value['activations']:
        exact(row,{'ticket','verb','capturedEpochMs'});need(nonce(row['ticket']) and row['ticket'] not in tickets and type(row['verb']) is str and len(row['verb'])<=80 and integer(row['capturedEpochMs'],max(last,1),value['capturedEpochMs']));last=row['capturedEpochMs'];tickets.add(row['ticket'])
    need(value['ticket']==(value['activations'][-1]['ticket'] if value['activations'] else None))
    ids=set();sequence=0
    for row in value['requests']:
        exact(row,{'sequence','requestId','ticket','method','target','contentType','authenticated','startedEpochMs','completedEpochMs','body','image','response','state'})
        need(integer(row['sequence'],sequence+1) and nonce(row['requestId']) and row['requestId'] not in ids and row['ticket'] in tickets and row['method'] in ('GET','POST','DELETE') and type(row['authenticated']) is bool and type(row['target']) is str and len(row['target'])<=4096 and type(row['contentType']) is str and len(row['contentType'])<=256 and integer(row['startedEpochMs'],1,value['capturedEpochMs']) and integer(row['completedEpochMs'],0,value['capturedEpochMs']) and row['state'] in ('receiving','written','connection-closed','retired'))
        target=urlsplit(row['target']);need(not target.scheme and not target.netloc and not target.fragment and (target.path in ('/api/v1/snapshots','/api/v1/user_stories') or re.fullmatch('/api/v1/user_stories/[1-9][0-9]{0,14}',target.path)))
        if row['method']=='POST':need(row['authenticated'] and not target.query)
        ids.add(row['requestId']);sequence=row['sequence'];file(row['body'])
        need(row['body']['name']=='snapshot-'+run+'-'+row['requestId']+'.body')
        if row['image'] is not None:
            image=row['image'];exact(image,{'filename','mime','bytes','sha256'});need(type(image['filename']) is str and len(image['filename'])<=255 and image['mime'] in ('image/png','image/jpeg','image/webp','image/gif') and integer(image['bytes'],1,32*1024*1024));sha(image['sha256'])
        if row['response'] is not None:
            response=row['response'];exact(response,{'responseId','status','body','bodyBase64'});file(response['body']);need(response['body']['name']=='snapshot-'+run+'-'+row['requestId']+'.reply' and integer(response['status'],0,599) and type(response['bodyBase64']) is str and len(response['bodyBase64'])<=22000)
            try:original=base64.b64decode(response['bodyBase64'],validate=True)
            except (ValueError,TypeError):need(False)
            need(len(original)==response['body']['bytes'] and hashlib.sha256(original).hexdigest()==response['body']['sha256'])
            need((response['responseId'] is None and response['status']==0) or nonce(response['responseId']))
            need(integer(row['completedEpochMs'],row['startedEpochMs'],value['capturedEpochMs']))
        else:need(row['state']=='receiving' and row['completedEpochMs']==0)
    if not value['active']:need(value['inflight']==0 and not value['held'] and value['uploads']==value['stories']==0 and all(row['state']=='retired' for row in value['requests']))
    if previous is not None:
        validate(previous,run,previous['requestId'],previous['capturedEpochMs'])
        need(value['instance']==previous['instance'] and value['origin']==previous['origin'] and value['domainId']==previous['domainId'] and value['capturedEpochMs']>=previous['capturedEpochMs'] and value['requestId']!=previous['requestId'] and value['activations'][:len(previous['activations'])]==previous['activations'] and len(value['requests'])>=len(previous['requests']))
        for old,new in zip(previous['requests'],value['requests']):
            need(all(old[k]==new[k] for k in old if k not in ('image','response','completedEpochMs','state')))
            if old['response'] is not None:need(old['response']==new['response'] and old['image']==new['image'] and old['completedEpochMs']==new['completedEpochMs'])
            if old['state']=='retired':need(new['state']=='retired')
        if not previous['active']:need(not value['active'])
    return value


class SnapshotUploadFixtureReader(PhaseFixtureReader):
    def __init__(self,client,run,**kwargs):
        super().__init__(client,run,'snapshots',**kwargs);self.previous_upload=None
    def provider(self,previous=None):
        request=secrets.token_hex(16);value=self.client.request('/runs/'+self.run+'/snapshot-upload',snapshot_upload_nonce=request)
        validate(value,self.run,request,int(self.epoch_ms()),previous=self.previous_upload)
        if previous is not None:validate(value,self.run,request,int(self.epoch_ms()),previous=previous)
        need(value['origin']==self.client.url.removesuffix('/feature-fixture/v1'))
        self.previous_upload=deepcopy(value);return value
    def read(self,previous=None):
        first=super().read(previous);provider=self.provider();last=super().read()
        if first['ticket']!=last['ticket'] or provider['ticket']!=last['ticket'] or not provider['active']:raise PhasePending('Original Snapshot upload phase changed during acquisition')
        return dict(last,upload=provider)


def join(native,provider,job_id,*,ticket,image_bytes,image_sha256,path,success):
    """Join original native file/replies with independently retained TLS bytes.

    The caller independently acquires image bytes/hash/path from its existing
    original capture reader. No expected upload count or desired story ID enters.
    """
    source(native,native['capturedEpochMs']);validate(provider,provider['runId'],provider['requestId'],provider['capturedEpochMs'])
    need(nonce(job_id) and nonce(ticket) and type(success) is bool and integer(image_bytes,1,32*1024*1024));sha(image_sha256)
    jobs=[job for job in native['jobs'] if job['id']==job_id];need(len(jobs)==1);job=jobs[0]
    need(job['path']==path and job['file'] and job['file']['bytes']==image_bytes and job['file']['sha256']==image_sha256 and job['terminal']==('success' if success else 'error') and not job['cancelRequested'])
    requests=job['requests'];need(len(requests)==(2 if success else 1) and [row['stage'] for row in requests]==(['image','story'] if success else ['image']))
    originals=[];replies=[]
    for row in requests:
        need(row['url']==provider['origin']+('/api/v1/snapshots' if row['stage']=='image' else '/api/v1/user_stories') and row['finished'])
        candidates=[entry for entry in provider['requests'] if entry['ticket']==ticket and entry['method']=='POST' and entry['target']==urlsplit(row['url']).path and entry['response'] is not None and (entry['response']['responseId']==row['responseId'] if row['responseId'] else entry['response']['status']==0)]
        need(len(candidates)==1);entry=candidates[0];response=entry['response'];need(entry['state'] in ('written','connection-closed') and response['status']==row['status'] and response['body']['bytes']==row['replyBytes'] and response['body']['sha256']==row['replySha256'])
        if row['stage']=='image':
            if success:need(entry['image'] is not None and entry['image']['bytes']==image_bytes and entry['image']['sha256']==image_sha256 and job['file']['readBytes']==image_bytes and job['file']['readSha256']==image_sha256 and row['sentBytes']>=entry['body']['bytes'])
        else:need(entry['body']['bytes']==row['bodyBytes'] and entry['body']['sha256']==row['bodySha256'])
        originals.append(entry);raw=base64.b64decode(row['replyBase64'])
        replies.append(json.loads(raw) if raw else None)
    if not success:
        need(requests[0]['networkError']!=0 and (requests[0]['status']==0 or requests[0]['status']>=400));return dict(job=deepcopy(job),requests=deepcopy(originals),offline=requests[0]['status']==0)
    need(all(row['status']==200 and row['networkError']==0 for row in requests))
    from urllib.parse import parse_qsl
    directories=[entry for entry in provider['requests'] if entry['ticket']==ticket and entry['method']=='GET' and urlsplit(entry['target']).path=='/api/v1/user_stories' and entry['response'] is not None and entry['response']['status']==200 and entry['state']=='written' and entry['completedEpochMs']<=originals[0]['startedEpochMs']]
    need(any(dict(parse_qsl(urlsplit(entry['target']).query)).get('domain_id')==provider['domainId'] and json.loads(base64.b64decode(entry['response']['bodyBase64'])).get('total_entries')==1 for entry in directories))
    image=replies[0]['data'];story=replies[1]['user_story'];details=story['details']
    need(type(image['id']) is str and nonce(image['id']) and integer(story['id'],1,9007199254740991) and details['snapshot_id']==image['id'] and details['image_url']==image['image_url']==provider['origin']+'/snapshot-media/'+image['id'] and details['original_image_file_name']==image['original_image_file_name']==originals[0]['image']['filename'])
    return dict(job=deepcopy(job),requests=deepcopy(originals),snapshotId=image['id'],storyId=story['id'])
