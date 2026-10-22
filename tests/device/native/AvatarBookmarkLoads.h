// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QPointer>
#include <QRegularExpression>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <memory>
#include <cmath>
namespace overte::e2e {
// GUI-affine passive metadata for the original contextless Qt connection.
// The collector owns no Avatar, connection or capture. An expired marker only
// proves destruction of that original shared capture; it is not a claim that
// every other capture, QObject, model resource or queued callback has retired.
class AvatarBookmarkLoads {
public:
    struct Capture;
private:
    struct Row {
        QMutex mutex;QString id,nameSha256,urlSha256,avatarInstance,sessionId;QPointer<QObject> sender;QThread* affinity{nullptr};
        qint64 createdEpochMs{0},enteredEpochMs{0},returnedEpochMs{0};
        double scale{0};int entities{0},dispatches{0},active{0};
        bool connectionObserved{false},connected{false},disconnectObserved{false},disconnected{false},completed{false},ownerThreadOnly{true};
        std::weak_ptr<Capture> capture;
    };
public:
    struct Capture {std::shared_ptr<Row> row;};
    using Token=std::shared_ptr<Capture>;
    class Dispatch {
    public:
        explicit Dispatch(const Token& token):_token(token) {
            if(_token) {auto& row=*_token->row;QMutexLocker lock(&row.mutex);++row.active;++row.dispatches;
                row.ownerThreadOnly=row.ownerThreadOnly && QThread::currentThread()==row.affinity;row.enteredEpochMs=QDateTime::currentMSecsSinceEpoch();}
        }
        Dispatch(const Dispatch&)=delete;Dispatch&operator=(const Dispatch&)=delete;
        ~Dispatch(){if(_token) {auto& row=*_token->row;QMutexLocker lock(&row.mutex);--row.active;row.returnedEpochMs=QDateTime::currentMSecsSinceEpoch();}}
        void disconnected(bool result){if(_token) {QMutexLocker lock(&_token->row->mutex);_token->row->disconnectObserved=true;_token->row->disconnected=result;}}
        void completed(){if(_token) {QMutexLocker lock(&_token->row->mutex);_token->row->completed=true;}}
    private:Token _token;
    };
    Token begin(QObject* owner,QObject* sender,const QString& name,const QString& url,double scale,int entities,const QString& avatarInstance,const QString& sessionId) {
        if(!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")) {return {};}
        if(!owner || !sender || owner->thread()!=QThread::currentThread() || sender->thread()!=QThread::currentThread()
                || (_owner && _owner!=owner) || _rows.size()>=128 || name.size()>2048 || url.size()>8192
                || !std::isfinite(scale) || entities<0 || entities>128 || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(avatarInstance).hasMatch()
                || QUuid(sessionId).isNull() || QUuid(sessionId).toString(QUuid::WithoutBraces)!=sessionId) {_overflow=true;return {};}
        if(!_owner) {_owner=owner;}
        auto row=std::make_shared<Row>();row->id=QUuid::createUuid().toString(QUuid::Id128);
        const auto hash=[](const QString& value){return QString::fromLatin1(QCryptographicHash::hash(value.toUtf8(),QCryptographicHash::Sha256).toHex());};
        row->nameSha256=hash(name);row->urlSha256=hash(url);row->avatarInstance=avatarInstance;row->sessionId=sessionId;
        row->sender=sender;row->affinity=owner->thread();row->scale=scale;row->entities=entities;
        row->createdEpochMs=QDateTime::currentMSecsSinceEpoch();auto token=std::make_shared<Capture>();token->row=row;row->capture=token;_rows.push_back(row);return token;
    }
    void connected(const Token& token,bool result){if(token) {QMutexLocker lock(&token->row->mutex);token->row->connectionObserved=true;token->row->connected=result;}}
    QVariantMap snapshot(QObject* owner) const {
        if(!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript") || !owner
                || owner->thread()!=QThread::currentThread() || (_owner && _owner!=owner) || _overflow) {return {};}
        QVariantList rows;
        for(const auto& row:_rows) {
            QMutexLocker lock(&row->mutex);
            rows.append(QVariantMap{{"id",row->id},{"nameSha256",row->nameSha256},{"urlSha256",row->urlSha256},
                {"avatarInstance",row->avatarInstance},{"sessionId",row->sessionId},
                {"createdEpochMs",row->createdEpochMs},{"enteredEpochMs",row->enteredEpochMs},{"returnedEpochMs",row->returnedEpochMs},
                {"bookmarkScale",row->scale},{"bookmarkEntities",row->entities},{"senderAlive",!row->sender.isNull()},{"captureAlive",!row->capture.expired()},
                {"connectionObserved",row->connectionObserved},{"connected",row->connected},{"disconnectObserved",row->disconnectObserved},
                {"disconnected",row->disconnected},{"dispatches",row->dispatches},{"active",row->active},{"completed",row->completed},{"ownerThreadOnly",row->ownerThreadOnly}});
        }
        return {{"avatarBookmarkLoadsVersion",1},{"instance",_instance},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"rows",rows}};
    }
private:
    QString _instance{QUuid::createUuid().toString(QUuid::Id128)};QPointer<QObject> _owner;
    QList<std::shared_ptr<Row>> _rows;bool _overflow{false};
};
}
#endif
