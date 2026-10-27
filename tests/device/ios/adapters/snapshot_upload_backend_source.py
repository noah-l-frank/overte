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
