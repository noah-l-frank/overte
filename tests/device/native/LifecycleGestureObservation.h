// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "PrivatePreviewFiles.h"
#include "../../../android/vr/pico/apps/picoInterface/openxr/e2e_input/E2eInputConstants.h"
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QUrl>
#include <QVariantMap>
#include <QStringList>
#include <cmath>
#include <memory>
#if defined(Q_OS_UNIX)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace overte::e2e {
inline QString gestureResultsDirectory() {
    const auto app=QCoreApplication::instance();
    if (!app || QThread::currentThread()!=app->thread()) { return {}; }
    const auto args=app->arguments();const auto script=args.indexOf("--testScript"),results=args.indexOf("--testResultsLocation");
    if (script<0 || script+1>=args.size() || results<0 || results+1>=args.size()) { return {}; }
    const auto path=QDir(args[results+1]).absolutePath();
    const QUrl url(args[script+1]);
    const auto scriptPath=url.isLocalFile() && !url.hasQuery() && !url.hasFragment() ? url.toLocalFile()
        : QDir::isAbsolutePath(args[script+1]) ? args[script+1] : QString();
    const QFileInfo file(scriptPath);
    if (scriptPath.isEmpty() || !previewDirectory(path) || file.isSymLink() || !file.isFile()
            || file.fileName()!="overte_e2e_probe.js" || file.canonicalFilePath()!=file.absoluteFilePath()
            || file.absolutePath()!=path || file.size()<=0 || file.size()>4*1024*1024
            || file.permissions() & (QFile::ReadGroup|QFile::WriteGroup|QFile::ExeGroup|QFile::ReadOther|QFile::WriteOther|QFile::ExeOther)) { return {}; }
    return path;
}
inline bool lifecycleGestureCommand(const QVariantMap& value) {
    const auto json=QJsonObject::fromVariantMap(value);const auto keys=json.keys();
    return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId"}
        && json.value("schemaVersion")==QJsonValue(1) && json.value("action")==QJsonValue("feature-lifecycle-gesture-observe")
        && json.value("commandId").isString() && json.value("runId").isString()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(json.value("commandId").toString()).hasMatch()
        && QRegularExpression("\\A[0-9a-f]{32}\\z").match(json.value("runId").toString()).hasMatch();
}

// Only the actual Pico plugin's left_thumbstick AxisMap publication calls
// consume(). Query commands carry no input, gesture, expected count or result.
class LifecycleGestureObservation {
public:
    explicit LifecycleGestureObservation(QObject* owner) : _owner(owner) { _clock.start(); }
    void consume(bool actionActive,double x,double y,double mappedX,double mappedY,bool mappedValid,
                 bool changedSinceLastSync,qint64 lastChangeTimeNs) {
        if (!enabled()) { return; }
        if (!finite(x) || !finite(y) || !finite(mappedX) || !finite(mappedY) || _frame>=9007199254740991ULL) { _valid=false;return; }
        const bool before=_known;
        const auto old=_current;
        _current={{"actionActive",actionActive},{"raw",QVariantList{x,y}},{"mapped",QVariantList{mappedX,mappedY}},
            {"mappedValid",mappedValid},{"changedSinceLastSync",changedSinceLastSync},{"lastChangeTimeNs",QString::number(lastChangeTimeNs)}};
        if (!frame()) { return; }
        _known=actionActive && mappedValid && std::abs(mappedX-x)<=1e-6 && std::abs(mappedY+y)<=1e-6;
        if (!_known) {
            if (before || _events.isEmpty()) { append("unavailable",_active,"action-not-published"); }
            return;
        }
        const bool nonzero=std::abs(x)>=.01 || std::abs(y)>=.01;
        if (nonzero && _active.isEmpty()) {
            _active=nonce();append("started",_active,before ? "axis-transition" : "first-observed-active");
        } else if (nonzero && !before) { append("resumed",_active,"action-published"); }
        else if (nonzero && old.value("raw")!=_current.value("raw")) { append("changed",_active,"axis-change"); }
        else if (!nonzero && (!_active.isEmpty() || !before || _events.isEmpty())) {
            append("neutral",_active,before ? "axis-transition" : "action-published");_active.clear();
        }
    }
    void unavailable(const QString& cause) {
        if (!enabled() || !_frame || !_known) { return; }
        if (cause!="focus-out" && cause!="deactivated" && cause!="display-inactive" && cause!="not-registered"
                && cause!="no-session" && cause!="init-failed" && cause!="sync-failed" && cause!="vector-query-failed") { _valid=false;return; }
        _known=false;if (frame()) { append("unavailable",_active,cause); }
        // Never clear an original active gesture merely because its source
        // stopped. Only a later real published neutral sample can close it.
    }
    QVariantMap snapshot(const QVariantMap& command) {
        if (!enabled() || !lifecycleGestureCommand(command) || !_frame || _queries.size()>=4096
                || _queries.contains(command.value("commandId").toString()) || _sequence>=9007199254740991ULL) { return {}; }
        _queries.insert(command.value("commandId").toString());
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<_lastEpoch || _clock.elapsed()<_lastElapsed) { _valid=false;return {}; }
        return {{"gestureObservationVersion",1},{"commandId",command.value("commandId")},{"runId",command.value("runId")},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",epoch},
            {"source",QVariantMap{{"backend","pico-openxr-left-thumbstick-publication"},{"createdEpochMs",_created},
                {"frameSequence",static_cast<qulonglong>(_frame)},{"frameEpochMs",_lastEpoch},{"frameElapsedMs",_lastElapsed},
                {"known",_known},{"current",_current},{"activeGesture",_active},{"events",_events}}}};
    }
private:
    bool enabled() const { return _valid && _owner && QCoreApplication::instance() && _owner->thread()==QThread::currentThread()
        && QThread::currentThread()==QCoreApplication::instance()->thread() && !gestureResultsDirectory().isEmpty(); }
    static bool finite(double value) { return std::isfinite(value) && value>=-1 && value<=1; }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    bool frame() {
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (epoch<=0 || epoch<_lastEpoch || elapsed<_lastElapsed || _frame>=9007199254740991ULL) { _valid=false;return false; }
        _lastEpoch=epoch;_lastElapsed=elapsed;++_frame;return true;
    }
#if defined(Q_OS_UNIX)
    static bool stableStatus(const struct stat& before,const struct stat& after) {
        // The layer publishes a mode0600 temporary through rename. An original
        // descriptor and its current pathname must still name the same complete
        // file, including nanosecond metadata; reject in-place writes as well.
        bool times=false;
#if defined(Q_OS_DARWIN)
        times=before.st_mtimespec.tv_sec==after.st_mtimespec.tv_sec && before.st_mtimespec.tv_nsec==after.st_mtimespec.tv_nsec
            && before.st_ctimespec.tv_sec==after.st_ctimespec.tv_sec && before.st_ctimespec.tv_nsec==after.st_ctimespec.tv_nsec;
#else
        times=before.st_mtim.tv_sec==after.st_mtim.tv_sec && before.st_mtim.tv_nsec==after.st_mtim.tv_nsec
            && before.st_ctim.tv_sec==after.st_ctim.tv_sec && before.st_ctim.tv_nsec==after.st_ctim.tv_nsec;
#endif
        return times && S_ISREG(before.st_mode) && S_ISREG(after.st_mode) && before.st_mode==after.st_mode
            && (after.st_mode&0777)==0600 && before.st_uid==after.st_uid && after.st_uid==::geteuid()
            && before.st_gid==after.st_gid && before.st_nlink==1 && after.st_nlink==1
            && before.st_dev==after.st_dev && before.st_ino==after.st_ino && before.st_size==after.st_size;
    }
    friend struct LifecycleGestureHostBoundary;
#endif
    QVariantMap stream() const {
        // Original private layer output was written at the actual intercepted
        // OpenXR query. Read its descriptor identity; never grant/ack input here.
#if defined(Q_OS_UNIX)
        const auto directory=gestureResultsDirectory()+"/openxr-input";
        if (!previewDirectory(directory)) { return {}; }
        const auto path=QFile::encodeName(directory+"/status.json");
        const int descriptor=::open(path.constData(),O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
        if (descriptor<0) { return {}; }
        struct stat before{},after{};QByteArray raw;
        bool valid=::fstat(descriptor,&before)==0 && S_ISREG(before.st_mode) && before.st_nlink==1
            && before.st_uid==::geteuid() && (before.st_mode&0777)==0600 && before.st_size>0 && before.st_size<=16384;
        if (valid) {
            raw.resize(static_cast<int>(before.st_size));qint64 offset{0};
            while (offset<raw.size()) { const auto count=::read(descriptor,raw.data()+offset,raw.size()-offset);if(count<=0){valid=false;break;}offset+=count; }
            valid=valid && ::fstat(descriptor,&after)==0 && stableStatus(before,after);
            struct stat current{};valid=valid && ::lstat(path.constData(),&current)==0 && stableStatus(before,current);
        }
        ::close(descriptor);if (!valid) { return {}; }
        QJsonParseError error;const auto document=QJsonDocument::fromJson(raw,&error);
        if (error.error!=QJsonParseError::NoError || !document.isObject()) { return {}; }
        const auto value=document.object();
        using namespace overte::e2e::openxr;
        auto integer=[](const QJsonValue& number,double low,double high) {return number.isDouble() && std::isfinite(number.toDouble())
            && number.toDouble()>=low && number.toDouble()<=high && std::floor(number.toDouble())==number.toDouble();};
        if (value.value("schemaVersion")!=QJsonValue(1) || value.value("buildMarker")!=QJsonValue(QLatin1String(BUILD_MARKER))
                || value.value("consumer")!=QJsonValue(QLatin1String(LAYER_NAME)) || value.value("profileId")!=QJsonValue(QLatin1String(PROFILE_ID))
                || value.value("bindingProfileSha256")!=QJsonValue(QLatin1String(PROFILE_SHA256))
                || !integer(value.value("acceptedSequence"),1,4294967295.0)
                || !integer(value.value("updatedEpochMs"),1,9007199254740991.0)
                || value.value("updatedEpochMs").toDouble()>_lastEpoch+250
                || !value.value("acceptedNonce").isString()
                || !QRegularExpression("\\A[0-9a-f]{32,128}\\z").match(value.value("acceptedNonce").toString()).hasMatch()
                || !value.value("activeCommandId").isString() || !value.value("state").isString() || !value.value("detail").isString()) { return {}; }
        // Preserve the exact original native status as a private event proof.
        // It may be unavailable/neutral or another stream; only the host owner
        // can join it to its durable original envelope and actual axis history.
        return {{"raw",QString::fromUtf8(raw)},{"sha256",QString::fromLatin1(QCryptographicHash::hash(raw,QCryptographicHash::Sha256).toHex())}};
#else
        return {};
#endif
    }
    void append(const QString& kind,const QString& gesture,const QString& cause) {
        if (_events.size()>=512) { _valid=false;return; }
        _events.append(QVariantMap{{"id",nonce()},{"eventSequence",_events.size()+1},{"kind",kind},{"gestureId",gesture},{"cause",cause},
            {"frameSequence",static_cast<qulonglong>(_frame)},{"occurredEpochMs",_lastEpoch},{"elapsedMs",_lastElapsed},
            {"sample",_current},{"stream",stream()}});
    }
    QPointer<QObject> _owner;
    const QString _instance{nonce()};const qint64 _created{QDateTime::currentMSecsSinceEpoch()};
    QElapsedTimer _clock;quint64 _frame{0},_sequence{0};qint64 _lastEpoch{0},_lastElapsed{0};
    bool _known{false},_valid{true};QString _active;QVariantMap _current;QVariantList _events;QSet<QString> _queries;
};
struct LifecycleGestureProvider { QPointer<QObject> owner;std::weak_ptr<LifecycleGestureObservation> source; };
inline const char* lifecycleGestureProperty() { return "_overteE2ELifecycleGestureProviderV1"; }
} // namespace overte::e2e
Q_DECLARE_METATYPE(overte::e2e::LifecycleGestureProvider)
namespace overte::e2e {
inline bool installLifecycleGesture(QObject* owner,const std::shared_ptr<LifecycleGestureObservation>& source) {
    auto app=QCoreApplication::instance();
    if (!app || !owner || !source || owner->thread()!=app->thread() || QThread::currentThread()!=app->thread()
            || gestureResultsDirectory().isEmpty()) { return false; }
    const auto previous=app->property(lifecycleGestureProperty());
    if (previous.isValid()) {
        if (previous.userType()!=qMetaTypeId<LifecycleGestureProvider>()) { return false; }
        const auto old=previous.value<LifecycleGestureProvider>();
        if (old.owner && (old.owner!=owner || old.source.lock()!=source)) { return false; }
    }
    app->setProperty(lifecycleGestureProperty(),QVariant::fromValue(LifecycleGestureProvider{owner,source}));return true;
}
}
#endif
