// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include "PicoRemoteAvatarStreamFile.h"
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QList>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QTimer>
#include <QUuid>
#include <atomic>
#include <cmath>
#include <memory>

namespace overte::e2e {
struct PicoRemoteAvatarStreamRequest {
    static QElapsedTimer begin() { QElapsedTimer result;result.start();return result; }
    explicit PicoRemoteAvatarStreamRequest(const QVariantMap& value):age(begin()),requested(QDateTime::currentMSecsSinceEpoch()),command(value) {}
    bool fresh() const { const auto now=QDateTime::currentMSecsSinceEpoch();return age.isValid() && age.elapsed()>=0
        && age.elapsed()<1500 && requested>0 && now>=requested && now-requested<1500; }
    const QElapsedTimer age;const qint64 requested;const QVariantMap command;
};

// The original ARM's elapsed clock is copied, never restarted after dispatch.
// Its remaining duration ends at ORIGINAL role epoch+120000, not ARM+120000.
struct PicoRemoteAvatarStreamGate {
    PicoRemoteAvatarStreamGate(const PicoRemoteAvatarStreamRequest& arm,qint64 original,qint64 end):
        age(arm.age),armEpoch(arm.requested),originalEpoch(original),deadline(end),pid(::getpid()) {}
    bool withinPolicy() const { const auto now=QDateTime::currentMSecsSinceEpoch();return ::getpid()==pid
        && age.isValid() && age.elapsed()>=0 && age.elapsed()<deadline-armEpoch
        && now>=originalEpoch && now>=armEpoch && now<deadline; }
    bool fresh() const { const auto now=QDateTime::currentMSecsSinceEpoch();return active.load() && withinPolicy()
        && (armCompleted.load() || (age.elapsed()<1500 && now-armEpoch<1500)); }
    const QElapsedTimer age;const qint64 armEpoch,originalEpoch,deadline;const pid_t pid;
    std::atomic_bool active{true},armCompleted{false};
};

struct PicoRemoteAvatarStreamWindow {
    explicit PicoRemoteAvatarStreamWindow(std::shared_ptr<PicoRemoteAvatarStreamGate> owner):
        age(PicoRemoteAvatarStreamRequest::begin()),requested(QDateTime::currentMSecsSinceEpoch()),gate(std::move(owner)) {}
    bool fresh() const { const auto now=QDateTime::currentMSecsSinceEpoch();return gate && gate->fresh()
        && age.isValid() && age.elapsed()>=0 && age.elapsed()<1500 && now>=requested && now-requested<1500; }
    const QElapsedTimer age;const qint64 requested;const std::shared_ptr<PicoRemoteAvatarStreamGate> gate;
};

class PicoRemoteAvatarStream : public std::enable_shared_from_this<PicoRemoteAvatarStream> {
public:
    using Snapshot=std::function<QVariantMap(const std::shared_ptr<PicoRemoteAvatarStreamWindow>&)>;
    using Quiet=std::function<bool()>;
    static bool keys(const QVariantMap& value,QStringList expected) { expected.sort();return value.keys()==expected; }
    static bool hex(const QString& value,int size=32) { return QRegularExpression("\\A[0-9a-f]{"+QString::number(size)+"}\\z").match(value).hasMatch(); }
    static bool whole(const QJsonValue& value,qint64 low,qint64 high) {
        return value.isDouble() && std::isfinite(value.toDouble()) && value.toDouble()>=low
            && value.toDouble()<=high && std::floor(value.toDouble())==value.toDouble();
    }
    static bool command(const QVariantMap& value) {
        const auto json=QJsonObject::fromVariantMap(value);const auto operation=value.value("operation").toString();
        if (!whole(json.value("schemaVersion"),1,1) || value.value("action")!=QVariant("feature-pico-remote-avatar-stream-control")
                || !hex(value.value("commandId").toString()) || !hex(value.value("runId").toString())) { return false; }
        if (operation=="arm") {
            const auto subject=value.value("subjectSessionId").toString();
            return keys(value,{"schemaVersion","commandId","action","operation","runId","subjectSessionId","ownerPolicy"})
                && json.value("ownerPolicy").isString() && !QUuid(subject).isNull()
                && QUuid(subject).toString(QUuid::WithoutBraces)==subject;
        }
        return (operation=="stop" || operation=="drain")
            && keys(value,{"schemaVersion","commandId","action","operation","runId","streamId","armCommandId","policySha256"})
            && hex(value.value("streamId").toString()) && hex(value.value("armCommandId").toString())
            && hex(value.value("policySha256").toString(),64);
    }
    bool used() const { return _used; }
    bool active() const { return _gate && _gate->active.load(); }
    bool confirmArm(const std::shared_ptr<PicoRemoteAvatarStreamRequest>& request) {
        if (!context() || _failed || !request || request!=_armRequest || !request->fresh() || !_gate || !_gate->fresh()) { fail();return false; }
        _gate->armCompleted.store(true);return true;
    }
    void refuseExpiredControl() { fail(); }
    QVariantMap control(const std::shared_ptr<PicoRemoteAvatarStreamRequest>& request,QObject* dispatcher,
            const QString& root,Snapshot snapshot,Quiet quiet) {
        if (!context() || !request || !request->fresh()) { return {}; }
        const auto& value=request->command;const auto id=value.value("commandId").toString();
        const bool arm=value.value("operation")==QVariant("arm");const bool firstArm=arm && !_used;
        if (arm) { if (_used) { fail();return {}; }_used=true; }
        if (!command(value)) { if (arm || _used) { fail(); }return {}; }
        if (_controls.size()>=32 || _controls.contains(id)) { fail();return {}; }
        _controls.insert(id);const auto operation=value.value("operation").toString();
        if (operation=="arm") {
            if (!firstArm || !dispatcher || !snapshot || !quiet) { fail();return {}; }
            _arm=id;_run=value.value("runId").toString();_subject=value.value("subjectSessionId").toString();
            _dispatcher=dispatcher;_snapshot=std::move(snapshot);_quiet=std::move(quiet);
            _policyBytes=value.value("ownerPolicy").toString().toUtf8();
            if (!policy(_policyBytes)) { fail();return reply(request); }
            _policySha=QCryptographicHash::hash(_policyBytes,QCryptographicHash::Sha256).toHex();
            _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
            _gate=std::make_shared<PicoRemoteAvatarStreamGate>(*request,_policy.value("originalNativeEpochMs").toLongLong(),
                _policy.value("deadlineNativeEpochMs").toLongLong());
            _armRequest=request;_initial=true;
            _file=std::make_unique<PicoRemoteAvatarStreamFile>(root,[this] { return permit(); });
            if (!_file->ready() || !request->fresh() || !_gate->fresh()) { fail();return reply(request); }
            _initial=false;_timer=new QTimer(dispatcher);_timer->setInterval(500);_timer->setTimerType(Qt::PreciseTimer);
            _deadlineTimer=new QTimer(dispatcher);_deadlineTimer->setSingleShot(true);_deadlineTimer->setTimerType(Qt::PreciseTimer);
            const std::weak_ptr<PicoRemoteAvatarStream> weak=shared_from_this();
            _connection=QObject::connect(_timer,&QTimer::timeout,dispatcher,[weak] { if (auto owner=weak.lock()) { owner->tick(); } });
            _deadlineConnection=QObject::connect(_deadlineTimer,&QTimer::timeout,dispatcher,[weak] { if (auto owner=weak.lock()) { owner->fail(); } });
            const auto remaining=_gate->deadline-_gate->armEpoch-_gate->age.elapsed();
            if (remaining<=0 || remaining>120000) { fail();return reply(request); }
            _deadlineTimer->start(static_cast<int>(remaining));tick();
            if (!_failed && !_stopped && _timer && _published>0 && _file) {
                // Historical original proof comes ONLY from the actual first
                // native write/readback and held Publisher OFDs, never from
                // a pending gather, expected path or a Host-returned sample.
                _armOriginal=_file->originalProof();
                if (_armOriginal.isEmpty()) { fail(); }
                else { _armOriginal.insert("sampleSequence",_published);_timer->start(); }
            }
        } else {
            if (!_used || value.value("runId")!=_run || value.value("streamId")!=_instance
                    || value.value("armCommandId")!=_arm || value.value("policySha256").toByteArray()!=_policySha) { fail();return {}; }
            if (!_gate || !_gate->withinPolicy()) { fail();return reply(request); }
            if (operation=="stop") { stop(); }
            else {
                if (!_stopped || _inTick || _timer || _deadlineTimer || pendingTimers()!=0
                        || !_quiet || !_quiet() || !_file || !_file->close()) { fail(); }
                else { _drained=true; }
            }
        }
        if (!request->fresh() || (_gate && !_gate->withinPolicy())) { fail();return {}; }return reply(request);
    }
    // Native arena refusal is sticky even when the conflicting legacy caller
    // does not accept its error. It cannot create a second producer/window.
    void refuseMixed() { if (_used) { fail(); } }
    void stop() {
        if (_gate) { _gate->active.store(false); }
        if (_timer) { _timer->stop();QObject::disconnect(_connection);_retiring.append(_timer);_timer->deleteLater();_timer=nullptr; }
        if (_deadlineTimer) { _deadlineTimer->stop();QObject::disconnect(_deadlineConnection);_retiring.append(_deadlineTimer);_deadlineTimer->deleteLater();_deadlineTimer=nullptr; }
        _stopped=true;
    }
    ~PicoRemoteAvatarStream() { stop(); }
private:
    bool context() const { return ::getpid()==_pid && QCoreApplication::instance()==_application
        && QThread::currentThread()==_thread && _application && _thread==_application->thread()
        && QCoreApplication::arguments().contains("--testScript"); }
    bool policy(const QByteArray& bytes) {
        if (bytes.isEmpty() || bytes.size()>8192 || bytes.contains('\0')) { return false; }
        const auto document=QJsonDocument::fromJson(bytes);
        if (!document.isObject()) { return false; }
        const auto json=document.object();_policy=json.toVariantMap();
        if (!keys(_policy,{"picoRemoteAvatarStreamPolicyVersion","runId","parentScopeSha256","parentBaselineSha256",
                "parentHostProcessIdentity","role","processId","originalNativeEpochMs","deadlineNativeEpochMs",
                "originalHostStartedMonotonic","originalHostDeadlineMonotonic","nativeFrameLimit","sampleIntervalMs"})
                || !whole(json.value("picoRemoteAvatarStreamPolicyVersion"),1,1)
                || _policy.value("runId")!=_run || !hex(_policy.value("runId").toString())
                || !hex(_policy.value("parentScopeSha256").toString(),64) || !hex(_policy.value("parentBaselineSha256").toString(),64)
                || !QRegularExpression("\\A[1-9][0-9]*:[1-9][0-9]*:[0-9a-f-]{36}\\z").match(_policy.value("parentHostProcessIdentity").toString()).hasMatch()
                || !QStringList{"primary","actor"}.contains(_policy.value("role").toString())
                || !whole(json.value("processId"),QCoreApplication::applicationPid(),QCoreApplication::applicationPid())
                || !whole(json.value("originalNativeEpochMs"),1,1000000000000000LL)
                || !whole(json.value("deadlineNativeEpochMs"),1,1000000000000000LL)
                || !whole(json.value("nativeFrameLimit"),256,256) || !whole(json.value("sampleIntervalMs"),500,500)
                || !json.value("originalHostStartedMonotonic").isString() || !json.value("originalHostDeadlineMonotonic").isString()) { return false; }
        bool a=false,b=false;const auto start=_policy.value("originalHostStartedMonotonic").toString().toDouble(&a);
        const auto end=_policy.value("originalHostDeadlineMonotonic").toString().toDouble(&b);
        const auto epoch=_policy.value("originalNativeEpochMs").toLongLong(),deadline=_policy.value("deadlineNativeEpochMs").toLongLong();
        // Re-encode this CLOSED ASCII policy explicitly. Qt's floating-point
        // JSON formatter must not choose a different epoch notation. Exact
        // equality also rejects duplicate keys/aliases and unadmitted fields.
        QByteArray canonical="{";bool first=true;
        for (auto it=_policy.cbegin();it!=_policy.cend();++it) {
            if (!first) { canonical+=','; }first=false;canonical+='"'+it.key().toUtf8()+"\":";
            const auto field=json.value(it.key());
            if (field.isString()) {
                const auto text=field.toString();
                if (!QRegularExpression("\\A[0-9A-Za-z:.+\\-]+\\z").match(text).hasMatch()) { return false; }
                canonical+='"'+text.toUtf8()+'"';
            } else if (field.isDouble()) { canonical+=QByteArray::number(static_cast<qlonglong>(field.toDouble())); }
            else { return false; }
        }
        canonical+='}';
        return canonical==bytes && a && b && std::isfinite(start) && std::isfinite(end) && start>=0 && end>start && end-start<=120.000001
            && epoch<=QDateTime::currentMSecsSinceEpoch() && deadline>QDateTime::currentMSecsSinceEpoch()
            && deadline>epoch && deadline-epoch<=120000;
    }
    bool permit() const { return context() && !_failed && _gate && _gate->fresh()
        && ((_initial && _armRequest && _armRequest->fresh()) || (_window && _window->fresh())); }
    int pendingTimers() const { int count=0;for (const auto& timer:_retiring) { if (timer) { ++count; } }return count; }
    void fail() { _failed=true;stop(); }
    void tick() {
        if (!context() || _failed || _stopped || !_gate || !_gate->fresh() || _inTick || _issued>=256 || !_dispatcher) { fail();return; }
        const auto elapsed=_gate->age.elapsed();
        if (elapsed<_nextSample) { return; } // Never catch up by emitting rapid samples.
        _nextSample=elapsed+500;
        const auto now=QDateTime::currentMSecsSinceEpoch();
        if (now<_epoch) { fail();return; }_epoch=now;_inTick=true;++_issued;
        _window=std::make_shared<PicoRemoteAvatarStreamWindow>(_gate);
        const auto source=_snapshot(_window);
        if (!_gate->active.load()) { _inTick=false;return; }
        if (source.isEmpty() || !_window->fresh()) { _inTick=false;fail();return; }
        const QVariantMap frame{{"schemaVersion",1},{"picoRemoteAvatarStreamFrameVersion",4},{"streamId",_instance},
            {"sampleSequence",static_cast<qulonglong>(_issued)},{"processId",QCoreApplication::applicationPid()},
            {"requestedEpochMs",_window->requested},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"ownerPolicySha256",QString::fromLatin1(_policySha)},{"source",source}};
        const auto bytes=QJsonDocument::fromVariant(frame).toJson(QJsonDocument::Compact);
        const bool written=_window->fresh() && _file && _file->publish(bytes);_inTick=false;
        if (!written) { fail();return; }_published=_issued;
        // Final readback/fsync consumes the SAME native window. A physically
        // written late frame stays owned, but cannot leave a live producer.
        if (!_window->fresh()) { fail(); }
    }
    QVariantMap reply(const std::shared_ptr<PicoRemoteAvatarStreamRequest>& request) const {
        return {{"schemaVersion",1},{"picoRemoteAvatarStreamControlVersion",4},{"requestId",request->command.value("commandId")},
            {"available",!_failed},{"processId",QCoreApplication::applicationPid()},{"requestedEpochMs",request->requested},
            {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"runId",_run},{"streamId",_instance},{"armCommandId",_arm},
            {"ownerPolicySha256",QString::fromLatin1(_policySha)},{"nativeFrameLimit",256},{"sampleIntervalMs",500},
            {"issuedFrames",_issued},{"publishedFrames",_published},{"timerActive",bool(_timer && _timer->isActive())},
            {"deadlineTimerActive",bool(_deadlineTimer && _deadlineTimer->isActive())},{"controlCount",_controls.size()},
            {"pendingTimerObjects",pendingTimers()},{"nativeQueueQuiet",bool(_quiet && _quiet())},
            {"inFlightTick",_inTick},{"stopped",_stopped},{"drained",_drained},{"pendingWrite",bool(_file && _file->writing())},
            {"armOriginal",_armOriginal}};
    }
    const pid_t _pid{::getpid()};QCoreApplication* const _application{QCoreApplication::instance()};QThread* const _thread{QThread::currentThread()};
    QPointer<QObject> _dispatcher;QPointer<QTimer> _timer,_deadlineTimer;QMetaObject::Connection _connection,_deadlineConnection;
    QList<QPointer<QTimer>> _retiring;
    QSet<QString> _controls;QString _run,_subject,_arm,_instance;QByteArray _policyBytes,_policySha;QVariantMap _policy,_armOriginal;
    Snapshot _snapshot;Quiet _quiet;std::shared_ptr<PicoRemoteAvatarStreamRequest> _armRequest;
    std::shared_ptr<PicoRemoteAvatarStreamGate> _gate;std::shared_ptr<PicoRemoteAvatarStreamWindow> _window;
    std::unique_ptr<PicoRemoteAvatarStreamFile> _file;bool _used{false},_failed{false},_initial{false},_inTick{false},_stopped{false},_drained{false};
    int _issued{0},_published{0};qint64 _epoch{0},_nextSample{0};
};
}
#endif
