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
#include <JointData.h>
#include <cstring>

namespace overte::e2e {
// Observes actual Rig copy/build boundaries, never an animation evaluator or
// wire receipt. The caller supplies the independently retained section source.
class RemoteJointPoseObservation {
public:
    static QString bits(const float& value) {
        static_assert(sizeof(float)==sizeof(quint32),"The observation requires float32");
        quint32 raw;std::memcpy(&raw,&value,sizeof(raw));return QString::number(raw,16).rightJustified(8,'0');
    }
    static QVariantList input(const JointData& value) {
        return {value.rotationIsDefaultPose ? QVariant() : QVariant(QVariantList{bits(value.rotation.x),bits(value.rotation.y),bits(value.rotation.z),bits(value.rotation.w)}),
            value.translationIsDefaultPose ? QVariant() : QVariant(QVariantList{bits(value.translation.x),bits(value.translation.y),bits(value.translation.z)}),
            value.rotationIsDefaultPose,value.translationIsDefaultPose};
    }
    void allowInputs(bool allowed) {if(!enabled()) {return;}QMutexLocker lock(&_mutex);_allowInputs=allowed;}
    bool inputsObserved() const {if(!enabled()) {return false;}QMutexLocker lock(&_mutex);return _captureInputs;}
    quint64 sequence() const {if(!enabled()) {return 0;}QMutexLocker lock(&_mutex);return _attempt;}
    bool pendingExternal() const {
        if(!enabled()) {return false;}QMutexLocker lock(&_mutex);
        return _valid && _copied && _copied==_attempt && _external!=_copied;
    }
    quint64 begin(int rig,int input,int skeleton) {
        if(!enabled()) {return 0;}QMutexLocker lock(&_mutex);
        if(_attempt>=9007199254740991ULL) {_valid=false;return 0;}
        ++_attempt;_captureInputs=_allowInputs && input>0 && input<=256 && input==skeleton;_rig=rig;_input=input;_skeleton=skeleton;_copied=_external=0;
        _begun=QDateTime::currentMSecsSinceEpoch();_copiedEpoch=_externalEpoch=0;
        _relative.clear();_absolute.clear();_rigInput.clear();return _attempt;
    }
    void copied(quint64 attempt,const QVariantList& relative,const QVariantMap& rigInput) {
        if(!enabled() || !attempt) {return;}QMutexLocker lock(&_mutex);
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if(!_valid || attempt!=_attempt || _copied || now<_begun) {_valid=false;return;}
        _copied=attempt;_copiedEpoch=now;_relative=relative;_rigInput=rigInput;
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
            quint64 before,const QVariantMap& received,const QVariantMap& interpolation) const {
        if(!enabled()) {return {};}QMutexLocker lock(&_mutex);
        const bool available=_valid && _attempt==before+1 && _copied==_attempt && _external==_attempt
            && !geometry.isEmpty() && _input>0 && _input<=256 && _input==_skeleton
            && _relative.size()==_input && _absolute.size()==_input
            && interpolation.value("available").toBool() && _rigInput.value("inputs").toList().size()==_input
            && _rigInput.value("decisions").toList().size()==_input;
        return {{"remoteJointPoseVersion",2},{"instance",_instance},{"copySequence",static_cast<qulonglong>(_attempt)},
            {"copiedSequence",static_cast<qulonglong>(_copied)},{"externalSequence",static_cast<qulonglong>(_external)},
            {"subjectSessionId",subject},{"avatarInstance",avatar},{"modelInstance",model},{"geometryInstance",geometry},{"rigId",_rig},
            {"available",available},{"inputJointCount",_input},{"skeletonJointCount",_skeleton},
            {"begunEpochMs",_begun},{"copiedEpochMs",_copiedEpoch},{"capturedEpochMs",_externalEpoch},
            {"relativeJoints",_relative},{"joints",_absolute},{"received",received},
            {"interpolation",interpolation},{"rigInput",_rigInput}};
    }
private:
    static bool enabled() {
#if defined(ANDROID_APP_PICO_INTERFACE)
        return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");
#else
        return false;
#endif
    }
    mutable QMutex _mutex;const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 _attempt{0},_copied{0},_external{0};int _rig{0},_input{0},_skeleton{-1};
    qint64 _begun{0},_copiedEpoch{0},_externalEpoch{0};bool _valid{true},_allowInputs{true},_captureInputs{true};QVariantList _relative,_absolute;QVariantMap _rigInput;
};
}
#endif
