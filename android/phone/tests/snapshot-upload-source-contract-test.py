#!/usr/bin/env python3
"""Compile original Snapshot upload entries; execute real private loopback TLS."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import ssl
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/self_tests')]
from feature_journeys.account_provider import AccountProvider
from feature_journeys.server import make_server
from feature_journeys.snapshot_upload_service import SnapshotUploadService
from test_snapshot_upload_service import png,DOMAIN
from urllib.parse import urlencode


def method(source,signature):
    start=source.index(signature);opening=source.index('{',start);depth=1;end=opening+1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build-dir',type=Path);args=parser.parse_args()
    build=(args.build_dir or Path('build')/('snapshot-upload-'+secrets.token_hex(8))).absolute()
    if not build.is_relative_to(ROOT/'build') or build.exists() or build.parent.resolve()!=build.parent:raise ValueError('A new build directory in this isolated checkout is required')
    build.mkdir(parents=True,mode=0o700)
    fake=build/'AccountFixture.h'
    fake.write_text('''#pragma once
#include <QChar>
#include <QObject>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkRequest>
#include <QHttpMultiPart>
#include <QPointer>
#include <QSharedPointer>
#include <QUuid>
#include <RequestCancellation.h>
template<class T> struct FixtureDependency { inline static QSharedPointer<T> object; };
struct DependencyManager { template<class T> static QSharedPointer<T>& value(){return FixtureDependency<T>::object;} template<class T> static QSharedPointer<T> get(){return value<T>();} };
namespace AccountManagerAuth { enum Type { None,Required,Optional,Credentials }; }
Q_DECLARE_METATYPE(AccountManagerAuth::Type)
class JSONCallbackParameters {
public:
    JSONCallbackParameters(QObject* receiver=nullptr,const QString& json={},const QString& error={},const QJsonObject& data={}):callbackReceiver(receiver),jsonCallbackMethod(json),errorCallbackMethod(error),callbackData(data){}
    bool isEmpty()const{return !callbackReceiver;}
    QObject* callbackReceiver;QString jsonCallbackMethod,errorCallbackMethod;QJsonObject callbackData;overte::network::RequestTicket requestTicket;
    QString phoneSnapshotUploadJob,phoneSnapshotUploadStage;
};
Q_DECLARE_METATYPE(JSONCallbackParameters)
class AccountManager:public QObject {
    Q_OBJECT
public:
    QUrl endpoint;QByteArray token;QUuid _sessionID;
    QNetworkRequest createRequest(const QString& path,AccountManagerAuth::Type){auto url=endpoint;url.setPath(path);QNetworkRequest request(url);request.setRawHeader("Authorization","Bearer "+token);request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,QNetworkRequest::ManualRedirectPolicy);return request;}
    Q_INVOKABLE void sendRequest(const QString&,AccountManagerAuth::Type,QNetworkAccessManager::Operation,const JSONCallbackParameters&={},const QByteArray&={},QHttpMultiPart*=nullptr,const QVariantMap&={});
signals:void authEndpointChanged();void logoutComplete();void usernameChanged();
};
class AddressManager { public:QString currentShareableAddress()const{return "hifi://owned/1,2,3";} };
'''.replace('const JSONCallbackParameters&={}','const JSONCallbackParameters& = {}').replace('const QByteArray&={}','const QByteArray& = {}').replace('QHttpMultiPart*=','QHttpMultiPart* = ').replace('const QVariantMap&={}','const QVariantMap& = {}'))
    (build/'AddressManager.h').write_text('#include "AccountFixture.h"\n')
    (build/'scripting').mkdir()
    (build/'scripting/WindowScriptingInterface.h').write_text('''#pragma once
#include <QObject>
#include <QString>
class WindowScriptingInterface:public QObject {Q_OBJECT
signals:void snapshotShared(bool,const QString&);
};
''')
    source=(ROOT/'android/phone/tests/snapshot-upload-source-contract.cpp').read_text()
    original=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
    for marker,body in {
        'ACCOUNT_SEND':method((ROOT/'libraries/networking/src/AccountManager.cpp').read_text(),'void AccountManager::sendRequest('),
        'SNAPSHOT_UPLOAD':method(original,'void Snapshot::uploadSnapshot('),
        'SNAPSHOT_CANCEL':method(original,'void Snapshot::cancelUpload('),
        'SNAPSHOT_CANCEL_ALL':method(original,'void Snapshot::cancelUploads('),
    }.items():source=source.replace('// @ORIGINAL_'+marker+'@',body)
    (build/'contract.cpp').write_text(source)
    moc='/usr/lib64/qt6/libexec/moc';includes=['-I'+str(build),'-I'+str(ROOT/'libraries/networking/src'),'-I'+str(ROOT/'interface/src/ui')]
    defines=['-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE']
    for input_path,output in ((fake,build/'account_moc.cpp'),(build/'scripting/WindowScriptingInterface.h',build/'window_moc.cpp'),(ROOT/'interface/src/ui/SnapshotUploader.h',build/'uploader_moc.cpp'),(build/'contract.cpp',build/'contract.moc')):
        subprocess.run([moc,*defines,*includes,str(input_path),'-o',str(output)],check=True,capture_output=True)
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Network'],text=True))
    subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror',*defines,*includes,str(build/'contract.cpp'),str(ROOT/'interface/src/ui/SnapshotUploader.cpp'),str(build/'account_moc.cpp'),str(build/'window_moc.cpp'),str(build/'uploader_moc.cpp'),'-o',str(build/'contract'),*flags],check=True)
    certificate,key=build/'ephemeral.crt',build/'ephemeral.key'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-sha256','-days','1','-nodes','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-keyout',str(key),'-out',str(certificate)],check=True,capture_output=True,timeout=10)
    key.chmod(0o600);certificate.chmod(0o600)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(certificate,key)
    image=build/'original.png';image.write_bytes(png());image.chmod(0o600)
    for mode,fault in (('success','normal'),('offline','offline'),('not-found','404'),('story-not-found','story-404'),('cancel','hold')):
        accounts=AccountProvider();root=build/('receiver-'+mode);root.mkdir(mode=0o700)
        server=make_server(secrets.token_hex(32),secrets.token_hex(32),account_provider=accounts,tls_context=context)
        errors=[]
        def handle_error(*_args):
            import traceback
            error=sys.exc_info()[1];errors.append((type(error).__name__,getattr(error,'errno',None),[(Path(frame.filename).name,frame.lineno,frame.name) for frame in traceback.extract_tb(error.__traceback__)]));server.internal_errors+=1
        server.handle_error=handle_error
        origin='https://localhost:'+str(server.server_port);service=SnapshotUploadService(accounts,DOMAIN,root,origin);server.snapshot_upload_service=service
        run=secrets.token_hex(16);service.provision(run);service.activate(run,secrets.token_hex(16),'upload');service.control(run,fault)
        credentials=service.credentials(run);_status,grant=accounts.grant(urlencode(dict(grant_type='password',scope='owner',**credentials)).encode())
        output=build/('observed-'+mode+'.json');configuration=build/('configuration-'+mode+'.json');configuration.write_text(json.dumps(dict(origin=origin,token=grant['access_token'],certificate=str(certificate),image=str(image),output=str(output),mode=mode)));configuration.chmod(0o600)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            if mode=='success':subprocess.run([str(build/'contract'),'--not-test',str(configuration)],check=True,timeout=3,env=dict(os.environ,QT_FORCE_STDERR_LOGGING='1'))
            subprocess.run([str(build/'contract'),'--testScript',str(configuration)],check=True,timeout=8,env=dict(os.environ,QT_FORCE_STDERR_LOGGING='1'))
            actual=json.loads(output.read_text());job=actual['jobs'][0]
            if job['file']['sha256']!=hashlib.sha256(image.read_bytes()).hexdigest():raise ValueError('Actual native input differs from original host file')
            if mode=='cancel':service.control(run,'release')
            deadline=time.monotonic()+2
            while service.runs[run]['inflight'] and time.monotonic()<deadline:time.sleep(.01)
            original=service.snapshot(run,secrets.token_hex(16))
            for request in job['requests']:
                matches=[row for row in original['requests'] if row['response'] is not None and row['response']['responseId']==request['responseId']]
                if mode=='success' and (len(matches)!=1 or matches[0]['response']['body']['sha256']!=request['replySha256']):raise ValueError('Actual native reply did not join independent TLS bytes')
            if mode=='success':
                if job['file']['readBytes']!=image.stat().st_size or job['file']['readSha256']!=job['file']['sha256'] or original['uploads']!=1 or original['stories']!=1:raise ValueError('Actual Qt multipart did not consume the original image')
                service.retire(run)
            if server.internal_errors:raise ValueError('Original TLS fixture failed internally: '+str(errors))
        finally:accounts.shutdown();server.shutdown();server.server_close();thread.join(3)
    print('Original Snapshot/AccountManager multipart, story, error and cancelled-reply contracts passed')


if __name__=='__main__':main()
