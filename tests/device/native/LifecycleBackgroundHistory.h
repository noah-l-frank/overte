// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QGuiApplication>
#include <QJsonObject>
#include <QPointer>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QTimer>
#include <QUuid>
#include <QVariantMap>
#include <cmath>
#include <functional>

namespace overte::e2e {
// Passive bounded original GUI history. The actual owning TabletBridge supplies
// the unchanged LifecycleUiObservation/Keyboard source; no expected state or
// editor/keyboard mutation can enter a request. Foreground host guards stay put.
class LifecycleBackgroundHistory : public QObject {
public:
    using Source=std::function<QVariantMap(const QString&)>;
    LifecycleBackgroundHistory(QObject* owner,Source source) : QObject(owner),_source(std::move(source)) {
        _clock.start();
        auto app=qobject_cast<QGuiApplication*>(QCoreApplication::instance());
        if (!app || app->thread()!=thread()) { _valid=false;return; }
        connect(&_timer,&QTimer::timeout,this,[this] { append("timer"); });
        connect(app,&QGuiApplication::applicationStateChanged,this,[this](Qt::ApplicationState state) {
            if (!_active) { return; }
            // A signal argument cannot substitute for the actual Qt state.
            if (state!=QGuiApplication::applicationState()) { fail();return; }
            ++_signals;append("application-state");
        });
    }

    QVariantMap request(const QVariantMap& command) {
        if (!gui() || !validCommand(command)) { return {}; }
        const auto id=command.value("commandId").toString(),operation=command.value("operation").toString();
        if (id==_lastId) { return command==_lastCommand ? _lastReply : QVariantMap(); }
        if (_seen.contains(id) || (_seen.size()>=512 && operation!="release")) { return {}; }
        const auto run=command.value("runId").toString();
        if (!_run.isEmpty() && run!=_run) { return {}; }
        if (operation!="observe" && (command.value("ownerInstance").toString()!=_instance
                || command.value("intentSequence").toULongLong()!=_intent+1)) { return {}; }
        if (_seen.size()<512) { _seen.insert(id); }
        _lastId=id;_lastCommand=command;_lastReply.clear();
        bool performed{false};
        if (operation!="observe") { ++_intent; }
        if (operation=="arm" && !_armed && _valid) {
            _armed=true;_run=run;_armCommand=id;_armElapsed=_clock.elapsed();_armedEpoch=QDateTime::currentMSecsSinceEpoch();
            _active=true;append("arm");
            if (_valid && !_frames.isEmpty()) { _timer.start(250);performed=true; }
        } else if (operation=="release" && _armed && !_released) {
            if (_active) { append("release"); }
            _timer.stop();_active=false;_released=true;_releaseCommand=id;performed=true;
        } else if (operation=="observe" && _active) { append("query"); }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<=0 || epoch<_lastEpoch || _sequence>=9007199254740991ULL) { fail();return {}; }
        _lastEpoch=epoch;
        _lastReply={{"lifecycleBackgroundVersion",1},{"commandId",id},{"runId",run},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",epoch},
            {"lastIntentSequence",static_cast<qulonglong>(_intent)},{"performed",performed},
            {"available",_valid && !_expired},{"active",_active},{"timerActive",_timer.isActive()},{"released",_released},{"expired",_expired},
            {"ownerRunId",_run},{"originalId",_original.value("id").toString()},{"armedEpochMs",_armedEpoch},
            {"armCommandId",_armCommand},{"releaseCommandId",_releaseCommand},{"frames",_frames}};
        return _lastReply;
    }

private:
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool identifier(const QString& value) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(value).hasMatch(); }
    static bool integer(const QJsonValue& value,double minimum=0) {
        return value.isDouble() && std::isfinite(value.toDouble()) && value.toDouble()>=minimum
            && value.toDouble()<=9007199254740991.0 && std::floor(value.toDouble())==value.toDouble();
    }
    static bool validCommand(const QVariantMap& command) {
        const auto value=QJsonObject::fromVariantMap(command);const auto operation=value.value("operation").toString();
        QSet<QString> keys{"schemaVersion","commandId","action","operation","runId"};
        if (operation!="observe") { keys.unite({"ownerInstance","intentSequence"}); }
        const auto actual=value.keys();
        if (QSet<QString>(actual.begin(),actual.end())!=keys || value.value("schemaVersion")!=QJsonValue(1)
                || value.value("action")!=QJsonValue("feature-lifecycle-background")
                || (operation!="observe" && operation!="arm" && operation!="release")
                || !identifier(value.value("commandId").toString()) || !identifier(value.value("runId").toString())) { return false; }
        return operation=="observe" || (identifier(value.value("ownerInstance").toString()) && integer(value.value("intentSequence"),1));
    }
    bool gui() const {
        auto app=QCoreApplication::instance();
        return app && app->thread()==thread() && QThread::currentThread()==thread()
            && QCoreApplication::arguments().contains("--testScript");
    }
    void fail() { _valid=false;_active=false;_timer.stop(); }
    static QString state() {
        switch (QGuiApplication::applicationState()) {
            case Qt::ApplicationActive:return "active";
            case Qt::ApplicationInactive:return "inactive";
            case Qt::ApplicationHidden:return "hidden";
            case Qt::ApplicationSuspended:return "suspended";
        }
        return {};
    }
    void append(const QString& cause) {
        if (!_active) { return; }
        if (!gui() || !_source || !_valid || _frames.size()>=96 || _clock.elapsed()<_armElapsed) { fail();return; }
        if (_clock.elapsed()-_armElapsed>20000) { _expired=true;_active=false;_timer.stop();return; }
        const auto original=_source(_run),source=original.value("source").toMap(),keyboard=source.value("keyboard").toMap();
        if (_clock.elapsed()-_armElapsed>20000) { _expired=true;_active=false;_timer.stop();return; }
        const auto epoch=QDateTime::currentMSecsSinceEpoch();const auto native=QJsonObject::fromVariantMap(original);
        if (original.isEmpty() || source.value("complete")!=QVariant(true) || epoch<=0 || epoch<_lastEpoch
                || native.value("lifecycleUiVersion")!=QJsonValue(1) || !identifier(original.value("instance").toString())
                || original.value("runId")!=_run || original.value("processId").toLongLong()!=QCoreApplication::applicationPid()
                || !integer(native.value("sequence"),1) || !integer(native.value("capturedEpochMs"),1)
                || epoch-original.value("capturedEpochMs").toLongLong()<0 || epoch-original.value("capturedEpochMs").toLongLong()>1500) { fail();return; }
        const auto current=source.value("current").toString();QVariantMap editor;int focused{0};
        for (const auto& value:source.value("editors").toList()) {
            const auto row=value.toMap();if (row.value("focused").toBool()) { ++focused; }
            if ((_original.isEmpty() && row.value("id")==current) || (!_original.isEmpty() && row.value("id")==_original.value("id"))) { editor=row; }
        }
        if (editor.isEmpty() || editor.value("kind")!="chat" || !identifier(editor.value("id").toString())) { fail();return; }
        const auto k=QJsonObject::fromVariantMap(keyboard);int pressed{0};const auto keys=keyboard.value("keys").toList();
        for (const auto& value:keys) {
            const auto key=QJsonObject::fromVariantMap(value.toMap());
            if (!key.value("pressed").isBool()) { fail();return; } if (key.value("pressed").toBool()) { ++pressed; }
        }
        if (keyboard.value("available")!=QVariant(true) || keyboard.value("backend")!="native-vr-entity-keyboard"
                || !identifier(keyboard.value("instance").toString()) || !integer(k.value("sequence"),1) || keys.size()>1021
                || !k.value("visible").isBool() || !k.value("created").isBool() || !k.value("enabled").isBool() || !k.value("raised").isBool()) { fail();return; }
        if (_original.isEmpty()) {
            if (state()!="active" || current!=editor.value("id").toString() || !editor.value("visible").toBool()) { fail();return; }
            _original=editor;
        } else {
            for (const auto& key:{"id","kind","fieldId","pageId","contextId","windowId","loaderId","firstObservedEpochMs"}) {
                if (editor.value(key)!=_original.value(key)) { fail();return; }
            }
        }
        const auto elapsed=_clock.elapsed();
        _frames.append(QVariantMap{{"frameId",nonce()},{"sequence",_frames.size()+1},{"capturedEpochMs",epoch},
            {"elapsedMs",elapsed},{"cause",cause},{"applicationState",state()},{"signalSequence",static_cast<qulonglong>(_signals)},
            {"uiInstance",original.value("instance")},{"uiSequence",original.value("sequence")},
            {"uiCapturedEpochMs",original.value("capturedEpochMs")},{"tabletShown",source.value("tabletShown")},
            {"onHomeScreen",source.value("onHomeScreen")},{"currentId",current},{"focusedEditors",focused},{"editor",editor},
            {"keyboard",QVariantMap{{"instance",keyboard.value("instance")},{"sequence",keyboard.value("sequence")},
                {"created",keyboard.value("created")},{"enabled",keyboard.value("enabled")},{"visible",keyboard.value("visible")},
                {"raised",keyboard.value("raised")},{"keyCount",keys.size()},{"pressedKeys",pressed}}}});
        _lastEpoch=epoch;
    }
    Source _source;QTimer _timer;QElapsedTimer _clock;QVariantList _frames;QVariantMap _original;
    const QString _instance{nonce()};QString _run,_lastId,_armCommand,_releaseCommand;QVariantMap _lastCommand,_lastReply;QSet<QString> _seen;
    quint64 _intent{0},_sequence{0},_signals{0};qint64 _lastEpoch{0},_armElapsed{0},_armedEpoch{0};
    bool _valid{true},_active{false},_armed{false},_released{false},_expired{false};
};
} // namespace overte::e2e
#endif
