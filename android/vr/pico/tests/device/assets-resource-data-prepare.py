"""Original generic Resource data handoff, with explicit uncached scheduling seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT,HERE,original


def prepare(stage,environment,prefix):
    stage=Path(stage);header=(ROOT/'libraries/networking/src/ResourceCache.h').read_text()
    declaration=header[header.index('class Resource : public QObject {'):header.index('\nuint qHash(const QPointer<QObject>&',header.index('class Resource : public QObject {'))]
    (stage/'AssetsResource.h').write_text('''#pragma once
#include <functional>
#include <limits>
#include <QObject>
#include <QNetworkReply>
#include <QTimer>
#include <QHash>
#include <QSharedPointer>
#include <QWeakPointer>
#include <QPointer>
#include <QUrl>
#include "ResourceRequest.h"
#include "assets-resource-cache-host.h"
uint qHash(const QPointer<QObject>& value,uint seed=0);
'''+declaration)
    source=(ROOT/'libraries/networking/src/ResourceCache.cpp').read_text()
    signatures=('Resource::Resource(const QUrl&', 'Resource::~Resource(', 'void Resource::init(',
        'void Resource::ensureLoading(', 'void Resource::setLoadPriorityOperator(', 'float Resource::getLoadPriority(',
        'void Resource::refresh(', 'void Resource::allReferencesCleared(', 'void Resource::attemptRequest(',
        'void Resource::finishedLoading(', 'void Resource::setSize(', 'void Resource::reinsert(',
        'void Resource::makeRequest(', 'void Resource::handleDownloadProgress(', 'void Resource::handleReplyFinished(',
        'bool Resource::handleFailedRequest(', 'uint qHash(const QPointer<QObject>&')
    blocks={signature:original(source,signature) for signature in signatures}
    static=next(line for line in source.splitlines() if line=='static int requestID = 0;')
    (stage/'AssetsResourceDataOriginals.inc').write_text(static+'\n'+'\n'.join(blocks.values()))
    provenance={name:hashlib.sha256(body.encode()).hexdigest() for name,body in blocks.items()}
    provenance['resource-declaration']=hashlib.sha256(declaration.encode()).hexdigest();provenance['request-counter']=hashlib.sha256(static.encode()).hexdigest()
    observer=(ROOT/'libraries/shared/src/ResourceRequestObserver.cpp').read_text();body=original(observer,'void ResourceRequestObserver::update(')
    (stage/'AssetsResourceObserverOriginal.inc').write_text(body);provenance['original-resource-request-observer']=hashlib.sha256(body.encode()).hexdigest()
    (stage/'resource-data-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    outputs=[]
    for name in ('AssetsResource','AssetsResourceObserver'):
        if name=='AssetsResourceObserver':
            (stage/(name+'.h')).write_text('''#pragma once
#include <QObject>
#include <QUrl>
#include <QVariantMap>
class ResourceRequestObserver:public QObject {
 Q_OBJECT
public:void update(const QUrl&,qint64=-1,const QString& = "");
signals:void resourceRequestEvent(QVariantMap result);
};
''')
        output=stage/(name+'-moc.cpp')
        subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-I'+str(stage),str(stage/(name+'.h')),'-o',str(output)],check=True,timeout=20,env=environment);outputs.append(str(output))
    application=(ROOT/'interface/src/Application.cpp').read_text()
    registration=next(line.strip() for line in application.splitlines() if 'qRegisterMetaType<uint64_t>("uint64_t");' in line)
    (stage/'AssetsResourceDataRegistration.inc').write_text(registration+'\n')
    provenance['original-uint64-type-registration']=hashlib.sha256(registration.encode()).hexdigest()
    (stage/'resource-data-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    return ['-DASSETS_ORIGINAL_RESOURCE_DATA',*outputs]
