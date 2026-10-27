"""Original backend query bytes and exact native/captured-body correlation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.script_feature.history import canonical,same
from feature_journeys.contract import identifier
from feature_journeys.snapshot_upload_protocol import PRIVATE_PNG,IMAGE_LIMIT
from ios.adapters import snapshot_uploads as native

SOURCE_LIMIT=700*1024
PART=512*1024


def sha(value):return native.sha(value)
def clock(value):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and number(value['monotonicMs'],0,1e15));return value
def after(a,b):clock(a);clock(b);need(all(a[key]>=b[key] for key in a))
def origin(url):
    need(type(url) is str and len(url)<=4096 and not any(ord(c)<=32 or ord(c)==127 for c in url));value=urlsplit(url)
    need(value.scheme=='https' and value.hostname is not None and not value.username and not value.password and not value.query and not value.fragment)
    return value.scheme,value.hostname,value.port or 443
def rows(value,key,maximum):
    need(type(value) is list and len(value)<=maximum);result={}
    for row in value:need(type(row) is dict and key in row and type(row[key]) is str and row[key] not in result);result[row[key]]=row
    return result
def file(value,run):
    exact(value,{'filename','bytes','sha256'});need(type(value['filename']) is str and PRIVATE_PNG.fullmatch(value['filename']) and value['filename'].startswith('parity-'+run[:16]+'-') and integer(value['bytes'],9,IMAGE_LIMIT));sha(value['sha256'])


def source(value):
    exact(value,{'snapshotUploadBackendVersion','instance','sequence','runId','requestId','processId','clockDomain','clock','ticket','created','fenced','fenceClock',
        'accountProvider','accountRun','principalSha256','uploads','stories','requests','history','sourceJournalRetirementRequired','transportProcessProofRequired','wholeFeatureRequired'})
    need(type(value['snapshotUploadBackendVersion']) is int and value['snapshotUploadBackendVersion']==1 and integer(value['sequence'],1) and integer(value['processId'],1)
        and value['clockDomain']=='snapshot-backend-host' and value['sourceJournalRetirementRequired'] is value['transportProcessProofRequired'] is value['wholeFeatureRequired'] is True and type(value['fenced']) is bool)
    for key in ('instance','runId','requestId','accountProvider','accountRun'):identifier(value[key])
    if value['ticket'] is not None:identifier(value['ticket'])
    sha(value['principalSha256']);need(value['principalSha256']==hashlib.sha256(('e2e-'+value['accountRun']).encode()).hexdigest());after(value['clock'],value['created'])
    if value['fenced']:after(value['fenceClock'],value['created']);after(value['clock'],value['fenceClock'])
    else:need(value['fenceClock'] is None)
    uploads=rows(value['uploads'],'instance',16);stories=rows(value['stories'],'id',16);requests=rows(value['requests'],'instance',256)
    for key,row in requests.items():
        identifier(key);exact(row,{'instance','method','path','bodyBytes','bodySha256','ticket','entered','prepared','written','writeFailed','left','status','responseBytes','responseSha256'})
        identifier(row['ticket']);need(row['method'] in ('POST','GET','DELETE') and type(row['path']) is str and len(row['path'])<=4096 and integer(row['bodyBytes'],0,IMAGE_LIMIT+8192)
            and type(row['written']) is type(row['writeFailed']) is bool)
        sha(row['bodySha256']);after(row['entered'],value['created']);after(value['clock'],row['entered'])
        if row['prepared'] is not None:
            after(row['prepared'],row['entered']);after(value['clock'],row['prepared']);need(integer(row['status'],100,599) and integer(row['responseBytes'],0,IMAGE_LIMIT+8192));sha(row['responseSha256'])
        else:need(row['status'] is row['responseBytes'] is row['responseSha256'] is None and not row['written'])
        if row['left'] is not None:after(row['left'],row['entered']);after(value['clock'],row['left'])
    for key,row in uploads.items():
        identifier(key);exact(row,{'instance','file','request','reply','retired'});file(row['file'],value['runId']);need(row['request'] in requests)
        request=requests[row['request']];need(request['method']=='POST' and request['path']=='/api/v1/snapshots')
        reply=row['reply'];exact(reply,{'id','thumbnail_url','image_url','original_image_file_name'});need(reply['id']==key and reply['original_image_file_name']==row['file']['filename'])
        need(reply['thumbnail_url']==reply['image_url'] and urlsplit(reply['image_url']).path=='/api/v1/snapshots/'+key+'/image');origin(reply['image_url'])
        if row['retired'] is not None:after(row['retired'],request['entered']);after(value['clock'],row['retired']);need(value['fenced'])
    for key,row in stories.items():
        exact(row,{'id','upload','request','original','deleted','retired'});need(type(key) is str and re.fullmatch('[1-9][0-9]{0,9}',key) and row['upload'] in uploads and row['request'] in requests)
        request=requests[row['request']];need(request['method']=='POST' and request['path']=='/api/v1/user_stories')
        original=row['original'];exact(original,{'id','details','thumbnail_url','place_name','path','action','audience'})
        upload=uploads[row['upload']];reply=upload['reply'];need(type(original['id']) is int and str(original['id'])==key and original['action']=='snapshot' and original['audience']=='for_url'
            and original['thumbnail_url']==reply['thumbnail_url'] and original['details']==dict(image_url=reply['image_url'],snapshot_id=upload['instance'],original_image_file_name=upload['file']['filename']))
        need(all(type(original[key]) is str and len(original[key])<=8192 for key in ('place_name','path')))
        for field in ('deleted','retired'):
            if row[field] is not None:after(row[field],request['entered']);after(value['clock'],row[field])
        if row['retired'] is not None:need(value['fenced'])
    need(type(value['history']) is list and len(value['history'])<=2048);previous_clock=value['created'];previous_sequence=0
    fields={'request-entered':{'request','method','path','bodyBytes','bodySha256'},'response-prepared':{'request','status','bytes','sha256'},'response-written':{'request'},'request-failed':{'request'},'request-left':{'request'},
        'upload-stored':{'upload','request','file'},'story-stored':{'story','upload','request'},'story-deleted':{'story','request'},'authority-fenced':{'accountOriginal'},'fixture-story-retired':{'story'},'fixture-upload-retired':{'upload','file'}}
    for event in value['history']:
        exact(event,{'sequence','clock','ticket','kind','detail'});need(event['kind'] in fields and integer(event['sequence'],previous_sequence+1,value['sequence']-1));identifier(event['ticket'])
        after(event['clock'],previous_clock);after(value['clock'],event['clock']);previous_clock=event['clock'];previous_sequence=event['sequence'];detail=event['detail'];exact(detail,fields[event['kind']])
        for key,table in (('request',requests),('upload',uploads),('story',stories)):
            if key in detail:need(detail[key] in table)
    def events(kind,key,identity):return [event for event in value['history'] if event['kind']==kind and event['detail'].get(key)==identity]
    for identity,row in requests.items():
        entered=events('request-entered','request',identity);need(len(entered)==1 and all(entered[0]['detail'][key]==row[key] for key in ('method','path','bodyBytes','bodySha256')))
        for kind,observed in (('response-prepared',row['prepared'] is not None),('response-written',row['written']),('request-failed',row['writeFailed']),('request-left',row['left'] is not None)):
            found=events(kind,'request',identity);need(len(found)==int(observed))
            if found and kind=='response-prepared':need(found[0]['detail']==dict(request=identity,status=row['status'],bytes=row['responseBytes'],sha256=row['responseSha256']))
    for identity,row in uploads.items():
        stored=events('upload-stored','upload',identity);need(len(stored)==1 and stored[0]['detail']==dict(upload=identity,request=row['request'],file=row['file']))
        need(len(events('fixture-upload-retired','upload',identity))==int(row['retired'] is not None))
    for identity,row in stories.items():
        stored=events('story-stored','story',identity);need(len(stored)==1 and stored[0]['detail']==dict(story=identity,upload=row['upload'],request=row['request']))
        need(len(events('story-deleted','story',identity))==int(row['deleted'] is not None) and len(events('fixture-story-retired','story',identity))==int(row['retired'] is not None))
    fences=[event for event in value['history'] if event['kind']=='authority-fenced'];need(len(fences)==int(value['fenced']))
    if fences:
        account=fences[0]['detail']['accountOriginal'];exact(account,{'providerVersion','instance','runId','capturedEpochMs','eventSequence','accountExists','grantsEnabled','heldRequests','armedHold','inflightRequests','accessTokens','refreshTokens'})
        need(type(account['providerVersion']) is int and account['providerVersion']==2 and account['instance']==value['accountProvider'] and account['runId']==value['accountRun']
            and type(account['accountExists']) is bool and account['grantsEnabled'] is account['armedHold'] is False
            and all(type(account[key]) is int and account[key]==0 for key in ('heldRequests','inflightRequests','accessTokens','refreshTokens')))
    return value


def accept(previous,value):
    source(value)
    if previous is None:return value
    source(previous);need(all(same(previous[key],value[key]) for key in ('instance','runId','processId','clockDomain','created','accountProvider','accountRun','principalSha256'))
        and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'] and (not previous['fenced'] or value['fenced']))
    after(value['clock'],previous['clock']);need(len(value['history'])>=len(previous['history']) and same(value['history'][:len(previous['history'])],previous['history']))
    for name,key,mutable in (('uploads','instance',{'retired'}),('stories','id',{'deleted','retired'}),('requests','instance',{'prepared','written','writeFailed','left','status','responseBytes','responseSha256'})):
        older={row[key]:row for row in previous[name]};newer={row[key]:row for row in value[name]};need(set(older)<=set(newer))
        for identity,row in older.items():
            current=newer[identity];need(all(same(item,current[field]) for field,item in row.items() if field not in mutable))
            for field in mutable:
                if row[field] is not None and row[field] is not False:need(same(row[field],current[field]))
    if previous['fenced']:need(same(previous['fenceClock'],value['fenceClock']))
    return value


def export(value,query):
    exact(value,{'snapshotUploadBackendExportVersion','kind','runId','requestId','original'});need(type(value['snapshotUploadBackendExportVersion']) is int and value['snapshotUploadBackendExportVersion']==1
        and all(value[key]==query[key] for key in ('kind','runId','requestId')) and query['kind'] in ('source','body'))
    original=value['original'];exact(original,{'base64','bytes','sha256'});need(integer(original['bytes'],2,SOURCE_LIMIT if query['kind']=='source' else 750*1024) and type(original['base64']) is str and len(original['base64'])<=4*((original['bytes']+2)//3))
    try:raw=base64.b64decode(original['base64'],validate=True)
    except (TypeError,ValueError):need(False)
    need(len(raw)==original['bytes'] and base64.b64encode(raw).decode()==original['base64'] and hashlib.sha256(raw).hexdigest()==sha(original['sha256']))
    try:packet=decode(raw.decode('utf-8'),limit=750*1024)
    except (UnicodeError,ValueError,TypeError):need(False)
    need(type(packet) is dict and canonical(packet)==raw and packet.get('runId')==query['runId'] and packet.get('requestId')==query['requestId'])
    if query['kind']=='source':source(packet)
    else:
        exact(packet,{'snapshotUploadBackendBodyVersion','instance','processId','clockDomain','runId','requestId','ticket','upload','offset','totalBytes','sha256','partSha256','eof','clockBefore','clockAfter','data','readerClosed','sourceJournalRetirementRequired'})
        need(type(packet['snapshotUploadBackendBodyVersion']) is int and packet['snapshotUploadBackendBodyVersion']==1 and packet['readerClosed'] is packet['sourceJournalRetirementRequired'] is True and integer(packet['processId'],1)
            and packet['clockDomain']=='snapshot-backend-host' and packet['upload']==query['upload'] and packet['offset']==query['offset'] and integer(packet['offset'],0,IMAGE_LIMIT)
            and packet['offset']%PART==0 and integer(packet['totalBytes'],9,IMAGE_LIMIT) and packet['offset']<packet['totalBytes'] and type(packet['eof']) is bool)
        for key in ('instance','ticket','upload'):identifier(packet[key])
        after(packet['clockAfter'],packet['clockBefore']);sha(packet['sha256'])
        elapsed={key:packet['clockAfter'][key]-packet['clockBefore'][key] for key in ('epochMs','monotonicMs')};need(all(value<1500 for value in elapsed.values()) and abs(elapsed['epochMs']-elapsed['monotonicMs'])<=250)
        try:part=base64.b64decode(packet['data'],validate=True)
        except (TypeError,ValueError):need(False)
        need(base64.b64encode(part).decode()==packet['data'] and len(part)==min(PART,packet['totalBytes']-packet['offset']) and sha(packet['partSha256'])==hashlib.sha256(part).hexdigest()
            and packet['eof']==(packet['offset']+len(part)==packet['totalBytes']))
    return packet


def joined(value,native_packet,identifier_value,file_fact,fixture_url):
    source(value);native.original(native_packet);need(native.decision(native_packet,identifier_value)['status']=='success')
    requests={row['instance']:row for row in value['requests']};upload_requests=[row for row in native_packet['source']['requests'] if row['upload']==identifier_value and row['stage']=='upload'];need(len(upload_requests)==1)
    upload_responses=[row for row in native_packet['source']['events'] if row['upload']==identifier_value and row['kind']=='response-original' and row['detail']['reply']==upload_requests[0]['reply']];need(len(upload_responses)==1)
    actual=upload_responses[0]['detail']
    scoped=[row for row in value['uploads'] if row['file']==dict(filename=file_fact['name'],bytes=file_fact['size'],sha256=file_fact['sha256'])
        and requests[row['request']]['responseBytes']==actual['byteCount'] and requests[row['request']]['responseSha256']==actual['sha256']]
    need(len(scoped)==1);upload=scoped[0];stories=[row for row in value['stories'] if row['upload']==upload['instance']];need(len(stories)==1);story=stories[0]
    need(origin(upload['reply']['image_url'])==origin(fixture_url));endpoint=origin(fixture_url)
    for stage,backend in (('upload',requests[upload['request']]),('story',requests[story['request']])):
        sent=[row for row in native_packet['source']['requests'] if row['upload']==identifier_value and row['stage']==stage];need(len(sent)==1)
        responses=[row for row in native_packet['source']['events'] if row['upload']==identifier_value and row['kind']=='response-original' and row['detail']['reply']==sent[0]['reply']]
        created=[row for row in native_packet['source']['events'] if row['upload']==identifier_value and row['kind']=='reply-created' and row['detail']['request']==sent[0]['instance']]
        need(len(responses)==len(created)==1 and backend['written'] and backend['left'] is not None and backend['status']==200
            and backend['responseBytes']==responses[0]['detail']['byteCount'] and backend['responseSha256']==responses[0]['detail']['sha256'])
        network=created[0]['detail'];need(network['scheme']==endpoint[0] and network['port']==endpoint[2] and network['hostSha256']==hashlib.sha256(endpoint[1].encode()).hexdigest() and network['authorizationPresent'])
    return deepcopy(dict(upload=upload,story=story))


def concurrency_bytes(value,limit):
    exact(value,{'base64','bytes','sha256'});need(integer(value['bytes'],1,limit) and type(value['base64']) is str and len(value['base64'])<=4*((value['bytes']+2)//3))
    try:raw=base64.b64decode(value['base64'],validate=True)
    except (TypeError,ValueError):need(False)
    need(len(raw)==value['bytes'] and base64.b64encode(raw).decode()==value['base64'] and hashlib.sha256(raw).hexdigest()==sha(value['sha256']));return raw


def concurrency_export(value,query,domain):
    from feature_journeys.snapshot_concurrency import query as actual_query
    from feature_journeys.snapshot_domain_client import public_configuration,public_packet
    public_configuration(domain);exact(value,{'snapshotConcurrencyExportVersion','runId','requestId','original'})
    need(type(value['snapshotConcurrencyExportVersion']) is int and value['snapshotConcurrencyExportVersion']==1 and query['kind']=='preflight'
        and all(value[key]==query[key] for key in ('runId','requestId')))
    raw=concurrency_bytes(value['original'],SOURCE_LIMIT);packet=decode(raw.decode('utf-8'),limit=SOURCE_LIMIT);need(canonical(packet)==raw)
    exact(packet,{'snapshotConcurrencyOriginalVersion','runId','requestId','sequence','clock','instance','processId','clockDomain','accountProvider','accountRun','principalSha256','created','ticket','snapshot','responses',
        'sourceJournalRetirementRequired','frontendResponseConsumptionRequired','wholeFeatureRequired'})
    need(type(packet['snapshotConcurrencyOriginalVersion']) is int and packet['snapshotConcurrencyOriginalVersion']==1 and integer(packet['sequence'],1) and integer(packet['processId'],1)
        and packet['clockDomain']=='snapshot-backend-host' and packet['sourceJournalRetirementRequired'] is packet['frontendResponseConsumptionRequired'] is packet['wholeFeatureRequired'] is True
        and all(packet[key]==query[key] for key in ('runId','requestId')))
    for key in ('instance','accountProvider','accountRun','ticket'):identifier(packet[key])
    need(sha(packet['principalSha256'])==hashlib.sha256(('e2e-'+packet['accountRun']).encode()).hexdigest());after(packet['clock'],packet['created'])
    snapshot=packet['snapshot'];exact(snapshot,{'snapshotConcurrencyVersion','runId','configuration','requests','controlledFixtureProjectionOnly','externalRegistrationRequired','resourceRetirementRequired'})
    need(type(snapshot['snapshotConcurrencyVersion']) is int and snapshot['snapshotConcurrencyVersion']==1 and snapshot['runId']==packet['runId'] and same(snapshot['configuration'],domain)
        and snapshot['controlledFixtureProjectionOnly'] is snapshot['externalRegistrationRequired'] is snapshot['resourceRetirementRequired'] is True)
    requests=rows(snapshot['requests'],'requestId',64);responses=rows(packet['responses'],'requestId',64);need(set(responses)==set(requests));previous=packet['created']
    for identity,row in requests.items():
        identifier(identity);exact(row,{'requestId','query','querySha256','ticket','domainReadNonce','source','entered','status','responseBytes','responseSha256','written','failed','left'})
        identifier(row['ticket']);identifier(row['domainReadNonce']);sha(row['querySha256']);after(row['entered'],previous);after(packet['clock'],row['entered'])
        need(type(row['written']) is type(row['failed']) is bool)
        if row['left'] is not None:after(row['left'],row['entered']);after(packet['clock'],row['left']);previous=row['left']
        if row['source'] is not None:
            original=row['source'];exact(original,{'packet','rawBase64','hostBefore','hostAfter','configuration'});need(same(original['configuration'],domain))
            need(type(original['rawBase64']) is str and len(original['rawBase64'])<=22000)
            try:source_raw=base64.b64decode(original['rawBase64'],validate=True)
            except (TypeError,ValueError):need(False)
            need(len(source_raw)<=16384 and base64.b64encode(source_raw).decode()==original['rawBase64'] and canonical(original['packet'])==source_raw)
            policy=public_packet(original['packet'],domain,packet['runId'],row['domainReadNonce']);before,ending=original['hostBefore'],original['hostAfter']
            after(ending,before);elapsed={key:ending[key]-before[key] for key in before};need(all(item<5000 for item in elapsed.values()) and abs(elapsed['epochMs']-elapsed['monotonicMs'])<=250)
            need(before['epochMs']-250<=policy['clockBefore']['epochMs']<=policy['clockAfter']['epochMs']<=ending['epochMs']+250 and ending['epochMs']-policy['clockAfter']['epochMs']<=1500
                and row['entered']['epochMs']-250<=before['epochMs'] and ending['epochMs']<=packet['clock']['epochMs']+250)
        evidence=responses[identity];exact(evidence,{'requestId','prepared','written','requestQueryOriginal','original'})
        query_raw=concurrency_bytes(evidence['requestQueryOriginal'],1024);need(evidence['requestQueryOriginal']['sha256']==row['querySha256'] and same(actual_query(query_raw.decode('ascii')),row['query']))
        if evidence['original'] is None:
            need(evidence['prepared'] is evidence['written'] is row['status'] is row['responseBytes'] is row['responseSha256'] is None and not row['written']);continue
        reply_raw=concurrency_bytes(evidence['original'],16384);need(row['status']==200 and row['source'] is not None
            and (row['responseBytes'],row['responseSha256'])==(evidence['original']['bytes'],evidence['original']['sha256']))
        reply=decode(reply_raw.decode('utf-8'),limit=16384);need(canonical(reply)==reply_raw)
        policy=row['source']['packet'];count=int(policy['online'] and policy['domainId']==row['query']['domain_id'] and policy['restriction'] in ('open','hifi'))
        need(same(reply,dict(status='success',total_entries=count,user_stories=[dict(action='concurrency',domain_id=policy['domainId'])] if count else [],
            fixtureConcurrency=dict(controlled=True,externalRegistrationRequired=True,domainId=policy['domainId'],restriction=policy['restriction']))))
        after(evidence['prepared'],row['entered']);after(packet['clock'],evidence['prepared'])
        need(row['source']['hostAfter']['epochMs']<=evidence['prepared']['epochMs']+250)
        if evidence['written'] is None:need(not row['written'])
        else:
            need(row['written']);after(evidence['written'],evidence['prepared']);after(packet['clock'],evidence['written'])
            if row['left'] is not None:after(row['left'],evidence['written'])
    return packet


def concurrency_joined(packet,backend,joined,ticket):
    need(all(same(packet[key],backend[key]) for key in ('instance','processId','clockDomain','accountProvider','accountRun','principalSha256','created')))
    sent=next(row for row in backend['requests'] if row['instance']==joined['upload']['request']);eligible=[]
    for row in packet['snapshot']['requests']:
        if row['ticket']!=ticket or row['status']!=200 or not row['written'] or row['failed'] or row['left'] is None or row['source'] is None:continue
        if row['source']['packet']['restriction'] not in ('open','hifi') or row['query']['domain_id']!=row['source']['packet']['domainId']:continue
        # These two events share the actual backend clock domain. Native job
        # clocks and frontend consumption remain independent obligations.
        if all(row['left'][key]<=sent['entered'][key] for key in row['left']):eligible.append(row)
    need(len(eligible)==1);row=eligible[0];reply=next(value for value in packet['responses'] if value['requestId']==row['requestId'])
    return dict(requestId=row['requestId'],ticket=ticket,querySha256=row['querySha256'],responseSha256=reply['original']['sha256'],
        domainId=row['source']['packet']['domainId'],restriction=row['source']['packet']['restriction'],backendWritten=reply['written'],backendLeft=row['left'],
        frontendResponseConsumptionRequired=True,externalMetaverseRegistrationRequired=True)


def concurrency_accept(previous,value):
    if previous is not None:
        need(all(same(value[key],previous[key]) for key in ('instance','processId','clockDomain','accountProvider','accountRun','principalSha256','created'))
            and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']);after(value['clock'],previous['clock'])
        for key in ('requests',):
            old=previous['snapshot'][key];new=value['snapshot'][key];need(len(new)>=len(old) and same(new[:len(old)],old))
        old=previous['responses'];new=value['responses'];need(len(new)>=len(old) and same(new[:len(old)],old))
    return value
