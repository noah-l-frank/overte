// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QUuid>
#include <QVariantMap>

namespace overte::e2e {
// Observes actual Rig copy/build boundaries, never an animation evaluator or
// wire receipt. The caller supplies the independently retained section source.
class RemoteJointPoseObservation {
public:
    quint64 sequence() const {if(!enabled()) {return 0;}QMutexLocker lock(&_mutex);return _attempt;}
    bool pendingExternal() const {
        if(!enabled()) {return false;}QMutexLocker lock(&_mutex);
        return _valid && _copied && _copied==_attempt && _external!=_copied;
    }
    quint64 begin(int rig,int input,int skeleton) {
        if(!enabled()) {return 0;}QMutexLocker lock(&_mutex);
        if(_attempt>=9007199254740991ULL) {_valid=false;return 0;}
        ++_attempt;_rig=rig;_input=input;_skeleton=skeleton;_copied=_external=0;
        _begun=QDateTime::currentMSecsSinceEpoch();_copiedEpoch=_externalEpoch=0;
        _relative.clear();_absolute.clear();return _attempt;
    }
    void copied(quint64 attempt,const QVariantList& relative) {
        if(!enabled() || !attempt) {return;}QMutexLocker lock(&_mutex);
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if(!_valid || attempt!=_attempt || _copied || now<_begun) {_valid=false;return;}
        _copied=attempt;_copiedEpoch=now;_relative=relative;
    }
    void external(const QVariantList& relative,const QVariantList& absolute) {
        if(!enabled()) {return;}QMutexLocker lock(&_mutex);
        // Rebuilding an old copy cannot retime or republish it as a new copy.
        if(!_valid || !_copied || _copied!=_attempt || _external==_copied) {return;}
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if(now<_copiedEpoch || relative!=_relative) {_valid=false;return;}
        _external=_copied;_externalEpoch=now;_absolute=absolute;
    }
    QVariantMap snapshot(const QString& subject,const QString& avatar,const QString& model,const QString& geometry,
            quint64 before,const QVariantMap& received) const {
        if(!enabled()) {return {};}QMutexLocker lock(&_mutex);
        const bool available=_valid && _attempt==before+1 && _copied==_attempt && _external==_attempt
            && !geometry.isEmpty() && _input>0 && _input<=256 && _input==_skeleton
            && _relative.size()==_input && _absolute.size()==_input;
        return {{"remoteJointPoseVersion",1},{"instance",_instance},{"copySequence",static_cast<qulonglong>(_attempt)},
            {"copiedSequence",static_cast<qulonglong>(_copied)},{"externalSequence",static_cast<qulonglong>(_external)},
            {"subjectSessionId",subject},{"avatarInstance",avatar},{"modelInstance",model},{"geometryInstance",geometry},{"rigId",_rig},
            {"available",available},{"inputJointCount",_input},{"skeletonJointCount",_skeleton},
            {"begunEpochMs",_begun},{"copiedEpochMs",_copiedEpoch},{"capturedEpochMs",_externalEpoch},
            {"relativeJoints",_relative},{"joints",_absolute},{"received",received}};
    }
private:
    static bool enabled() {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    mutable QMutex _mutex;const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 _attempt{0},_copied{0},_external{0};int _rig{0},_input{0},_skeleton{-1};
    qint64 _begun{0},_copiedEpoch{0},_externalEpoch{0};bool _valid{true};QVariantList _relative,_absolute;
};
}
#endif
