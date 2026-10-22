// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QUuid>
#include <QVariantMap>

namespace overte::e2e {
// Original poses copied to the renderer-facing external pose set. Remote
// SkeletonModel uses received joints and deliberately does not run AnimGraph.
class FeatureExternalPoseObservation {
public:
    template<typename Poses> void copied(int rigId,const Poses& poses) {
        if (!QCoreApplication::instance() || !QCoreApplication::arguments().contains("--testScript")) { return; }
        QMutexLocker lock(&_mutex);const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (!_valid || epoch<=0 || epoch<_epoch || rigId<=0 || poses.size()>256 || _sequence>=1000000000) {
            _valid=false;return;
        }
        QVariantList joints;
        for (const auto& pose:poses) {
            const auto& q=pose.rot();const auto& p=pose.trans();
            joints.append(QVariant(QVariantList{q.x,q.y,q.z,q.w,p.x,p.y,p.z}));
        }
        _epoch=epoch;
        _original={{"externalPoseVersion",1},{"instance",_instance},{"rigId",rigId},
            {"capturedEpochMs",static_cast<double>(epoch)},{"evaluationSequence",static_cast<double>(++_sequence)},
            {"totalJoints",static_cast<int>(poses.size())},{"joints",joints}};
    }
    QVariantMap snapshot() const {
        QMutexLocker lock(&_mutex);
        return _valid ? _original : QVariantMap();
    }
private:
    mutable QMutex _mutex;
    const QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QVariantMap _original;
    quint64 _sequence {0};qint64 _epoch {0};bool _valid {true};
};
} // namespace overte::e2e
#endif
