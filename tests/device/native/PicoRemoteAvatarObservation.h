// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonObject>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <memory>

namespace overte::e2e {
// Created at the original API entry before first queue admission. The same
// object crosses every dispatch; no queued callback can renew its clock.
struct PicoRemoteAvatarRequest {
    static QElapsedTimer begin() {QElapsedTimer value;value.start();return value;}
    explicit PicoRemoteAvatarRequest(const QVariantMap& value):age(begin()),requested(QDateTime::currentMSecsSinceEpoch()),command(value) {}
    bool fresh() const {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        return requested>0 && now>=requested && now-requested<1500 && age.isValid() && age.elapsed()>=0 && age.elapsed()<1500;
    }
    const QElapsedTimer age;const qint64 requested;const QVariantMap command;
};
// Passive original subject identity. No Avatar, Model or geometry is retained
// strongly across calls, loaded, rendered, replaced or repaired by this owner.
class PicoRemoteAvatarObservation {
public:
    // Opt-in stream4 shares this native arena; it cannot reset a legacy run.
    bool streamEligible() const { return enabled() && _valid && _run.isEmpty() && _requests.isEmpty() && _published.isEmpty() && !_bound; }
    void refuseStreamConflict() { _valid=false; }
    static bool command(const QVariantMap& value) {
        const auto json=QJsonObject::fromVariantMap(value);
        const auto subject=value.value("subjectSessionId").toString();
        return value.keys()==QStringList{"action","commandId","runId","schemaVersion","subjectSessionId"}
            && json.value("schemaVersion").isDouble() && json.value("schemaVersion").toDouble()==1
            && value.value("action")==QVariant("feature-pico-remote-avatar-observe")
            && json.value("commandId").isString() && id(value.value("commandId").toString())
            && json.value("runId").isString() && id(value.value("runId").toString())
            && json.value("subjectSessionId").isString() && !QUuid(subject).isNull()
            && QUuid(subject).toString(QUuid::WithoutBraces)==subject;
    }
    bool admit(const QVariantMap& value) {
        if(!enabled() || !_valid || !command(value) || _requests.size()>=512
                || _requests.contains(value.value("commandId").toString())) {return false;}
        const auto run=value.value("runId").toString(),subject=value.value("subjectSessionId").toString();
        if(!_run.isEmpty() && (_run!=run || _subject!=subject)) {_valid=false;return false;}
        _run=run;_subject=subject;_requests.insert(value.value("commandId").toString());return true;
    }
    template<class AvatarType,class ModelType>
    bool originals(QObject* nodes,QObject* manager,const std::shared_ptr<AvatarType>& avatar,const std::shared_ptr<ModelType>& model) {
        if(!enabled() || !_valid || !nodes || !manager || !avatar || !model) {return false;}
        const std::shared_ptr<void> subject=avatar, skeleton=model;
        if(_bound) {
            if(!_nodes || !_manager || _nodes!=nodes || _manager!=manager
                    || _avatar.lock()!=subject || _model.lock()!=skeleton) {_valid=false;return false;}
        } else {_nodes=nodes;_manager=manager;_avatar=subject;_model=skeleton;_bound=true;}
        return true;
    }
    QVariantMap publish(const QVariantMap& request,const QString& instance,qint64 requested,const QVariantMap& source) {
        const auto now=QDateTime::currentMSecsSinceEpoch();
        const auto id=request.value("commandId").toString();
        if(!enabled() || !_valid || !command(request) || !_requests.contains(id) || _published.contains(id)
                || requested<=0 || now<requested || now-requested>=1500 || now<_epoch || source.isEmpty()) {return {};}
        _epoch=now;_published.insert(id);
        return {{"schemaVersion",1},{"requestId",id},{"instance",instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",requested},{"capturedEpochMs",now},{"source",source}};
    }
private:
    static bool id(const QString& value) {return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch();}
    bool enabled() const {return QCoreApplication::instance() && QThread::currentThread()==_thread
        && QCoreApplication::arguments().contains("--testScript");}
    QThread* _thread{QThread::currentThread()};QPointer<QObject> _nodes,_manager;
    std::weak_ptr<void> _avatar,_model;QString _run,_subject;QSet<QString> _requests,_published;
    bool _valid{true},_bound{false};qint64 _epoch{0};quint64 _sequence{0};
};
}
#endif
