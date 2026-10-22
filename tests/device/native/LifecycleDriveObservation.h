// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QUrl>
#include <QVariantMap>
#include <glm/glm.hpp>
#include <glm/gtc/quaternion.hpp>
#include <array>
#include <cmath>

namespace overte::e2e {
inline bool lifecycleDriveCommand(const QVariantMap& value) {
    const auto command=QJsonObject::fromVariantMap(value);const auto keys=command.keys();
    return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId"}
        && command.value("schemaVersion")==QJsonValue(1)
        && command.value("action")==QJsonValue("feature-lifecycle-drive-observe")
        && command.value("commandId").isString() && command.value("runId").isString()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(command.value("commandId").toString()).hasMatch()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(command.value("runId").toString()).hasMatch();
}

struct LifecycleDrivePose { bool valid{false};glm::vec3 position{0.0f};glm::quat rotation{1.0f,0.0f,0.0f,0.0f}; };
struct LifecycleDriveSample {
    std::array<float,12> drive{},raw{};std::array<bool,12> disabled{};
    glm::vec3 feet{0.0f},body{0.0f},velocity{0.0f},actionMotor{0.0f},scriptedMotor{0.0f},thrust{0.0f};
    glm::quat orientation{1.0f,0.0f,0.0f,0.0f};glm::mat4 sensorToWorld{1.0f};
    std::array<LifecycleDrivePose,3> tracking{};
    QString sceneUrl;float scale{0.0f},scriptedMotorTimescale{0.0f};
    int controllerState{-1};
    bool physicsReady{false},seated{false},stuck{false},advancedMovement{false};
    bool actionEnabled{false},scriptedEnabled{false},pushing{false},braking{false},beingPushed{false};
};

// Read-only native serializer. The sole product caller fills every value from
// the original MyAvatar/controller frame; no command can supply sample values.
class LifecycleDriveObservation {
public:
    QVariantMap observe(const LifecycleDriveSample& sample) {
        if (!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
                || !QCoreApplication::arguments().contains("--testScript") || !_valid
                || _sequence>=9007199254740991ULL) { return {}; }
        _good=true;
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<=0 || epoch<_lastEpoch) { _valid=false;return {}; }
        if (sample.controllerState<0 || sample.controllerState>4 || sample.sceneUrl.size()>2048
                || !QUrl(sample.sceneUrl).isValid() || QUrl(sample.sceneUrl).scheme().isEmpty()) { return {}; }
        QVariantList drive,raw,disabled,matrix;
        for (int index=0;index<12;++index) {
            drive.append(real(sample.drive[index],-1e6,1e6));raw.append(real(sample.raw[index],-1e6,1e6));
            disabled.append(sample.disabled[index]);
        }
        for (int column=0;column<4;++column) { for (int row=0;row<4;++row) {
            matrix.append(real(sample.sensorToWorld[column][row],-1e8,1e8));
        } }
        QVariantMap tracking;
        const std::array<QString,3> roles{"head","leftHand","rightHand"};
        for (int index=0;index<3;++index) {
            const auto& pose=sample.tracking[index];
            tracking.insert(roles[index],QVariantMap{{"valid",pose.valid},{"position",vec(pose.position)},
                {"rotation",quat(pose.rotation)}});
        }
        QVariantMap source{{"sceneUrl",sample.sceneUrl},{"feetPosition",vec(sample.feet)},
            {"bodyPosition",vec(sample.body)},{"orientation",quat(sample.orientation)},
            {"modelScale",real(sample.scale,0.001,1000)},{"sensorToWorld",matrix},
            {"driveKeys",drive},{"rawDriveKeys",raw},{"disabledDriveKeys",disabled},
            {"physics",QVariantMap{{"ready",sample.physicsReady},{"state",sample.controllerState},
                {"seated",sample.seated},{"stuck",sample.stuck},{"linearVelocity",vec(sample.velocity)}}},
            {"motors",QVariantMap{{"advancedMovement",sample.advancedMovement},{"actionEnabled",sample.actionEnabled},
                {"scriptedEnabled",sample.scriptedEnabled},{"actionVelocity",vec(sample.actionMotor)},
                {"scriptedVelocity",vec(sample.scriptedMotor)},{"scriptedTimescale",real(sample.scriptedMotorTimescale,0,1e8)},
                {"thrust",vec(sample.thrust)},{"pushing",sample.pushing},{"braking",sample.braking},{"beingPushed",sample.beingPushed}}},
            {"tracking",tracking}};
        if (!_good) { return {}; }
        _lastEpoch=epoch;
        return {{"lifecycleDriveVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",epoch},{"source",source}};
    }
private:
    double real(double value,double low,double high) { if (!std::isfinite(value) || value<low || value>high) { _good=false; }return value; }
    QVariantList vec(const glm::vec3& value) { return {real(value.x,-1e8,1e8),real(value.y,-1e8,1e8),real(value.z,-1e8,1e8)}; }
    QVariantList quat(const glm::quat& value) {
        const double norm=glm::dot(value,value);
        if (!std::isfinite(norm) || std::abs(norm-1.0)>0.01) { _good=false; }
        return {real(value.x,-1,1),real(value.y,-1,1),real(value.z,-1,1),real(value.w,-1,1)};
    }
    const QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    quint64 _sequence{0};qint64 _lastEpoch{0};bool _valid{true},_good{true};
};
} // namespace overte::e2e
#endif
