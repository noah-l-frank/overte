// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/LifecycleGestureObservation.h"
#include <QCoreApplication>
#include <cassert>
#include <map>
#include <tuple>
#include <vector>
#include "libraries/controllers/src/controllers/AxisValue.h"

using namespace overte::e2e;
using StandardAxisChannel=int;
using controller::AxisValue;
constexpr int LX=0,LY=1,RX=2,RY=3,LEFT_TRACKPAD_X=4,LEFT_TRACKPAD_Y=5,RIGHT_TRACKPAD_X=6,RIGHT_TRACKPAD_Y=7;
struct NativeActionState {
    bool isActive{false},changedSinceLastSync{true};qint64 lastChangeTime{12345};
    struct {float x{0},y{0};} currentState;
};
struct ActionBoundary { NativeActionState state;NativeActionState getVector2f() const {return state;} };
struct LogBoundary {template<class T>LogBoundary& operator<<(const T&){return *this;}};
#define qCInfo(category) LogBoundary()
void publish(const std::shared_ptr<LifecycleGestureObservation>& _featureGesture,float y,bool active=true) {
    std::map<StandardAxisChannel,AxisValue> _axisStateMap;
    std::map<std::string,std::shared_ptr<ActionBoundary>> _actions;
    for (const auto& name:{"left_thumbstick","left_trackpad","right_thumbstick","right_trackpad"})
        _actions[name]=std::make_shared<ActionBoundary>();
    _actions["left_thumbstick"]->state.isActive=active;_actions["left_thumbstick"]->state.currentState.y=y;
    unsigned _trackedControllers{2};
#include "original-pico-gesture-axis.inc"
}
QVariantMap request() {return {{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
    {"runId",QString(32,'a')},{"action","feature-lifecycle-gesture-observe"}};}
QVariantMap snapshot(const std::shared_ptr<LifecycleGestureObservation>& source) {
    auto result=source->snapshot(request());assert(!result.isEmpty());return result["source"].toMap();
}
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);auto owner=new QObject;
    auto source=std::make_shared<LifecycleGestureObservation>(owner);
    if (gestureResultsDirectory().isEmpty()) {publish(source,.8f);assert(source->snapshot(request()).isEmpty());delete owner;return 0;}
    assert(installLifecycleGesture(owner,source));assert(source->snapshot(request()).isEmpty());
    auto invalid=request();invalid["expected"]=2;assert(!lifecycleGestureCommand(invalid));
    invalid.remove("expected");invalid["schemaVersion"]=true;assert(!lifecycleGestureCommand(invalid));
    publish(source,0);auto baseline=snapshot(source);assert(baseline["known"].toBool());
    assert(baseline["activeGesture"].toString().isEmpty());assert(baseline["events"].toList().size()==1);
    publish(source,.8f);auto started=snapshot(source);auto events=started["events"].toList();assert(events.size()==2);
    const auto start=events.last().toMap();const auto id=started["activeGesture"];
    assert(start["kind"]=="started" && start["gestureId"]==id && !id.toString().isEmpty());
    const auto proof=start["stream"].toMap();assert(!proof.isEmpty());
    QFile status(gestureResultsDirectory()+"/openxr-input/status.json");assert(status.open(QIODevice::ReadOnly));
    assert(proof["raw"].toString().toUtf8()==status.readAll());status.close();
    publish(source,.8f);assert(snapshot(source)["events"].toList().size()==2); // Keepalive is not another gesture.
    source->unavailable("focus-out");auto unknown=snapshot(source);
    assert(!unknown["known"].toBool() && unknown["activeGesture"]==id);
    publish(source,0,false);unknown=snapshot(source);
    assert(!unknown["known"].toBool() && unknown["activeGesture"]==id); // Inactive is not neutral.
    publish(source,.8f);auto resumed=snapshot(source);assert(resumed["activeGesture"]==id);
    assert(resumed["events"].toList().last().toMap()["kind"]=="resumed");
    publish(source,0);auto neutral=snapshot(source);assert(neutral["activeGesture"].toString().isEmpty());
    assert(neutral["events"].toList().last().toMap()["kind"]=="neutral");
    assert(neutral["events"].toList()[1].toMap()==start); // Original status bytes/time never rewritten.
    auto once=request();assert(!source->snapshot(once).isEmpty());assert(source->snapshot(once).isEmpty());
    QObject otherOwner;auto other=std::make_shared<LifecycleGestureObservation>(&otherOwner);
    assert(!installLifecycleGesture(&otherOwner,other));delete owner;assert(source->snapshot(request()).isEmpty());
    assert(installLifecycleGesture(&otherOwner,other));publish(other,0);assert(snapshot(other)["known"].toBool());
    // A symlink/ordinary-mode native status cannot become an intercepted-query proof.
    const auto path=gestureResultsDirectory()+"/openxr-input/status.json",original=path+".original";
    assert(QFile::rename(path,original));assert(QFile::link(original,path));
    publish(other,.8f);auto noProof=snapshot(other);assert(noProof["events"].toList().last().toMap()["stream"].toMap().isEmpty());
    assert(QFile::remove(path));assert(QFile::rename(original,path));publish(other,0);
    assert(QFile::setPermissions(path,QFile::ReadOwner|QFile::WriteOwner|QFile::ReadGroup));
    publish(other,.8f);assert(snapshot(other)["events"].toList().last().toMap()["stream"].toMap().isEmpty());
    assert(QFile::setPermissions(path,QFile::ReadOwner|QFile::WriteOwner));publish(other,0);
    for (int index=0;index<520;++index) {publish(other,index%2 ? 0 : .8f);}
    assert(other->snapshot(request()).isEmpty()); // Overflow never discards an original prefix.
}
