// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QPointer>
#include <QThread>
#include <QRegularExpression>
#include <QJsonArray>
#include <QJsonDocument>
#include <QCryptographicHash>
#include <QUuid>
#include <AssetResourceRequest.h>
#include <MappingRequest.h>

namespace overte::e2e {
// Called on the actual ResourceRequest owner's thread. Private children are
// read only while that original parent's callback owns those members. Weak
// QPointers never prolong a request and null current fields never imply death.
class AssetsRequestLifetimes {
public:
    bool observe(AssetResourceRequest* source,const QString& run) {
        if(!admit(run) || _sequence==0 || !source || source->thread()!=QThread::currentThread()) {return false;}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        const auto parent=remember(source,"resource",QString(),source->getUrl().toString(),source->thread(),epoch);
        if(parent.isEmpty()) {return false;}
        if(auto request=source->_assetMappingRequest) {
            if(remember(request,"mapping",parent,request->featurePicoRequestedPath(),source->thread(),epoch).isEmpty()) {return false;}
        }
        if(auto request=source->_assetRequest) {
            if(remember(request,"asset",parent,request->getHash(),source->thread(),epoch).isEmpty()) {return false;}
        }
        return true;
    }
    QJsonObject snapshot(const QString& run) {
        if(!admit(run) || _sequence>=512) {return {};}
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if(epoch<=0 || epoch<_epoch) {_valid=false;return {};}_epoch=epoch;
        QJsonArray rows;
        for(auto& row:_rows) {
            const bool alive=!row.object.isNull();
            if(row.absent && alive) {_valid=false;return {};}
            if(!alive && !row.absent) {row.absent=epoch;}
            rows.append(QJsonObject{{"id",row.id},{"kind",row.kind},{"resourceId",row.parent},
                {"sourceSha256",row.sourceHash},{"firstObservedEpochMs",static_cast<double>(row.first)},
                {"firstObservedAbsentEpochMs",row.absent ? QJsonValue(static_cast<double>(row.absent)) : QJsonValue()},
                {"alive",alive},{"sameThreadAsResource",row.sameThread}});
        }
        QJsonObject result{{"assetsRequestLifetimesVersion",1},{"instance",_instance},{"runId",_run},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"sequence",static_cast<double>(++_sequence)},
            {"capturedEpochMs",static_cast<double>(epoch)},{"objects",rows}};
        if(QJsonDocument(result).toJson(QJsonDocument::Compact).size()>65536) {_valid=false;return {};}
        return result;
    }
private:
    bool admit(const QString& run) {
        if(!QCoreApplication::instance() || _thread.isNull() || QThread::currentThread()!=_thread.data()
                || !_valid || !QCoreApplication::arguments().contains("--testScript")
                || run==QString(32,'0') || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()) {return false;}
        if(_run.isEmpty()) {_run=run;}
        if(_run!=run) {_valid=false;return false;}
        return true;
    }
    QString remember(QObject* object,const QString& kind,const QString& parent,const QString& source,QThread* owner,qint64 epoch) {
        if(!_valid || !object || source.isEmpty() || source.size()>4096 || epoch<=0 || epoch<_epoch) {_valid=false;return {};}
        _epoch=epoch;
        const auto hash=QString::fromLatin1(QCryptographicHash::hash(source.toUtf8(),QCryptographicHash::Sha256).toHex());
        for(const auto& row:_rows) {
            if(row.object.data()==object) {
                if(row.kind!=kind || row.parent!=parent || row.sourceHash!=hash || row.absent) {_valid=false;return {};}
                return row.id;
            }
        }
        if(_rows.size()>=64) {_valid=false;return {};}
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _rows.append({id,kind,parent,hash,object,epoch,0,object->thread()==owner});
        return id;
    }
    struct Row {QString id,kind,parent,sourceHash;QPointer<QObject> object;qint64 first,absent;bool sameThread;};
    QPointer<QThread> _thread{QThread::currentThread()};
    QList<Row> _rows;QString _run,_instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 _sequence{0};qint64 _epoch{0};bool _valid{true};
};
}
#endif
