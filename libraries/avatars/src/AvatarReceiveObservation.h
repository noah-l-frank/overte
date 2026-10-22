// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QVariant>
#include <QUuid>
#include <JointData.h>
#include <cmath>
#include <algorithm>

namespace overte::e2e {
// Passive actual AvatarMixer delivery. Local replicas/test inputs cannot enter
// this source: a sourced network context and successful parser tail must meet.
class AvatarReceiveObservation {
public:
    static AvatarReceiveObservation& instance() { static AvatarReceiveObservation value;return value; }
    static QString identity(const QUuid& uuid) {
        return QString::fromLatin1(QCryptographicHash::hash(uuid.toRfc4122(),QCryptographicHash::Sha256).toHex());
    }
    class NetworkScope {
    public:
        NetworkScope(const QUuid& avatar,const QUuid& mixer,bool sourcedMixer) : _old(context()) {
            context()=enabled() && sourcedMixer && !avatar.isNull() && !mixer.isNull()
                ? QVariantMap{{"avatar",avatar},{"mixer",mixer}} : QVariantMap();
        }
        ~NetworkScope() { context()=_old; }
        NetworkScope(const NetworkScope&)=delete;
        NetworkScope& operator=(const NetworkScope&)=delete;
    private: QVariantMap _old;
    };
    void parsed(const QUuid& avatar,const QByteArray& record,int consumed,bool carriesJoints,
            const QVector<JointData>& joints,const QString& advertisedModel,float targetScale) {
        const auto origin=context();
        if (!enabled() || origin.isEmpty() || origin.value("avatar").toUuid()!=avatar) { return; }
        QMutexLocker lock(&_mutex);
        if (consumed<=0 || consumed>record.size() || joints.size()>256 || _sequence>=1000000000
                || advertisedModel.size()>4096 || !std::isfinite(targetScale) || targetScale<=0) { _complete=false;return; }
        QVariantList rows;
        const int count=std::min<int>(32,joints.size());
        for (int sample=0;sample<count;++sample) {
            const int index=sample*joints.size()/count;const auto& joint=joints[index];
            QVariant rotation,translation;
            if (!joint.rotationIsDefaultPose) {
                const auto& q=joint.rotation;
                if (!std::isfinite(q.x) || !std::isfinite(q.y) || !std::isfinite(q.z) || !std::isfinite(q.w)) { _complete=false;return; }
                rotation=QVariantList{q.x,q.y,q.z,q.w};
            }
            if (!joint.translationIsDefaultPose) {
                const auto& p=joint.translation;
                if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z)) { _complete=false;return; }
                translation=QVariantList{p.x,p.y,p.z};
            }
            rows.append(QVariantMap{{"index",index},{"rotation",rotation},{"translation",translation}});
        }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (!_records.isEmpty() && epoch<_records.last().toMap().value("capturedEpochMs").toLongLong()) { _complete=false;return; }
        _records.append(QVariantMap{{"receiveSequence",static_cast<qulonglong>(++_sequence)},
            {"capturedEpochMs",epoch},{"avatarSha256",identity(avatar)},
            {"mixerSha256",identity(origin.value("mixer").toUuid())},
            {"recordSha256",QString::fromLatin1(QCryptographicHash::hash(record.left(consumed),QCryptographicHash::Sha256).toHex())},
            {"recordBytes",consumed},{"carriesJoints",carriesJoints},{"jointCount",joints.size()},
            {"joints",rows},{"advertisedModelUrl",advertisedModel},{"targetScale",targetScale}});
        if (_records.size()>32) { _records.removeFirst();++_dropped; }
    }
    QVariantMap snapshot(const QUuid& actualSelf) {
        if (!enabled() || actualSelf.isNull()) { return {}; }
        QMutexLocker lock(&_mutex);
        return {{"avatarReceiveVersion",1},{"instance",_instance},{"processId",QCoreApplication::applicationPid()},
            {"selfSha256",identity(actualSelf)},{"complete",_complete},{"receiveSequence",static_cast<qulonglong>(_sequence)},
            {"droppedRecords",static_cast<qulonglong>(_dropped)},{"records",_records}};
    }
private:
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    static QVariantMap& context() { static thread_local QVariantMap value;return value; }
    QMutex _mutex;bool _complete {true};quint64 _sequence {0},_dropped {0};QVariantList _records;
    QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
};
} // namespace overte::e2e
#endif
