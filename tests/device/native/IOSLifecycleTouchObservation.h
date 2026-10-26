// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NativeReadBracket.h"
#include <QMap>
#include <QPointer>
#include <QPointingDevice>
#include <QTouchEvent>
#include <algorithm>

namespace overte::e2e {
// Values copied from ordinary Application touch dispatch. This observer never
// captures, accepts, redirects, retains or synthesizes a Qt input event.
class IOSLifecycleTouchObservation {
public:
    static IOSLifecycleTouchObservation& shared() { static IOSLifecycleTouchObservation value;return value; }
    class Route {
    public:
        explicit Route(const QTouchEvent* event):_event(event) {}
        ~Route() { shared().record(_event,_route); }
        void routed(const QString& route) { _route=route; }
    private:
        const QTouchEvent* _event;QString _route {"unresolved"};
    };
    QVariantMap snapshot() {
        if (!main() || !QCoreApplication::arguments().contains("--testScript")) {return {};}
        const auto before=clock();
        if (!_installed) {_installed=true;_birth=before;}
        QVariantList devices,active;
        for (const auto& row:_devices) {devices.append(QVariantMap{{"id",row.id},{"alive",!row.object.isNull()}});}
        for (const auto& id:_active) {active.append(id);}
        return {{"iosLifecycleTouchVersion",1},{"instance",_instance},{"clockDomain","native-main-lifecycle-touch"},
            {"clockBefore",before},{"clockAfter",clock()},{"installed",_installed},{"birth",_birth},
            {"complete",_failure.isEmpty()},{"failure",_failure.isEmpty()?QVariant():QVariant(_failure)},
            {"events",_events},{"devices",devices},{"active",active}};
    }
private:
    struct Device {QPointer<QObject> object;QString id;};
    IOSLifecycleTouchObservation() {_timer.start();}
    bool main() const {const auto app=QCoreApplication::instance();return app && QThread::currentThread()==app->thread();}
    QVariantMap clock() const {return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
        {"monotonicMs",static_cast<double>(_timer.elapsed())}};}
    void fail(const QString& reason) {if (_failure.isEmpty()) {_failure=reason;}}
    QString device(const QPointingDevice* object) {
        if (!object) {fail("missing-device");return {};}
        for (const auto& row:_devices) {if (row.object.data()==object) {return row.id;}}
        if (_devices.size()>=8) {fail("device-capacity");return {};}
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        _devices.append({const_cast<QPointingDevice*>(object),id});return id;
    }
    void record(const QTouchEvent* event,const QString& route) {
        if (!_installed || !main() || !event || !_failure.isEmpty()) {return;}
        const auto type=event->type();
        if (type!=QEvent::TouchBegin && type!=QEvent::TouchUpdate && type!=QEvent::TouchEnd && type!=QEvent::TouchCancel) {return;}
        if (route!="ui" && route!="captured" && route!="world") {fail("unresolved-route");return;}
        if (_events.size()>=128 || event->points().isEmpty() || event->points().size()>16) {fail("event-capacity");return;}
        const auto stamp=clock();
        const auto floor=_events.isEmpty()?_birth:_events.last().toMap().value("clock").toMap();
        if (stamp.value("epochMs").toLongLong()<floor.value("epochMs").toLongLong()
                || stamp.value("monotonicMs").toLongLong()<floor.value("monotonicMs").toLongLong()) {fail("clock-rollback");return;}
        const auto deviceId=device(event->pointingDevice());if (deviceId.isEmpty()) {return;}
        QVariantList points;
        for (const auto& point:event->points()) {
            const auto key=deviceId+"/"+QString::number(point.id());
            QString phase;
            if (type==QEvent::TouchCancel) {phase="cancelled";}
            else if (point.state()==QEventPoint::State::Pressed) {phase="pressed";}
            else if (point.state()==QEventPoint::State::Released) {phase="released";}
            else if (point.state()==QEventPoint::State::Updated) {phase="updated";}
            else if (point.state()==QEventPoint::State::Stationary) {phase="stationary";}
            else {fail("point-state");return;}
            if (phase=="pressed") {
                if (_active.contains(key)) {fail("duplicate-contact");return;}
                _active.insert(key,QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'));
            } else if (!_active.contains(key)) {fail("unknown-contact");return;}
            const auto id=_active.value(key);
            points.append(QVariantMap{{"id",id},{"nativeId",point.id()},{"phase",phase},
                {"position",QVariantList{point.position().x(),point.position().y()}}});
            if (phase=="released" || phase=="cancelled") {_active.remove(key);}
        }
        if ((type==QEvent::TouchEnd || type==QEvent::TouchCancel)
                && std::any_of(_active.keyBegin(),_active.keyEnd(),[&](const QString& key) {return key.startsWith(deviceId+"/");})) {
            fail("unfinished-terminal");return;
        }
        _events.append(QVariantMap{{"sequence",_events.size()+1},{"clock",stamp},{"device",deviceId},
            {"eventTimestampMs",static_cast<double>(event->timestamp())},{"route",route},
            {"kind",type==QEvent::TouchBegin?"begin":type==QEvent::TouchUpdate?"update":type==QEvent::TouchEnd?"end":"cancel"},
            {"points",points}});
    }
    QElapsedTimer _timer;QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    bool _installed {false};QString _failure;QVariantMap _birth;
    QList<Device> _devices;QMap<QString,QString> _active;QVariantList _events;
};
}
#endif
