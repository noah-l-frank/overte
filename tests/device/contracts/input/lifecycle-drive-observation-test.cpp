// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/LifecycleDriveObservation.h"
#include <QCoreApplication>
#include <cassert>
#include <limits>
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);
    using namespace overte::e2e;
    LifecycleDriveSample actual;actual.sceneUrl="file:///explicit-native-boundary.json";actual.scale=1;
    actual.controllerState=0;actual.physicsReady=true;actual.advancedMovement=true;actual.actionEnabled=true;
    actual.drive[2]=actual.raw[2]=-.8f;actual.feet={1,2,3};actual.body={1,3,3};
    LifecycleDriveObservation source;
    if (!app.arguments().contains("--testScript")) { assert(source.observe(actual).isEmpty());return 0; }
    QVariantMap command{{"schemaVersion",1.0},{"commandId",QString(32,'a')},{"runId",QString(32,'b')},{"action","feature-lifecycle-drive-observe"}};
    assert(lifecycleDriveCommand(command));command["schemaVersion"]=true;assert(!lifecycleDriveCommand(command));
    command["schemaVersion"]="1";assert(!lifecycleDriveCommand(command));command["schemaVersion"]=1;
    command["expected"]="forward";assert(!lifecycleDriveCommand(command));command.remove("expected");
    auto first=source.observe(actual);assert(!first.isEmpty());auto original=first["source"].toMap();
    assert(original["feetPosition"].toList()==QVariantList({1.0,2.0,3.0}));
    assert(original["driveKeys"].toList()[2].toFloat()==-.8f);
    actual.disabled[2]=true;actual.drive[2]=0;actual.feet={1.125f,2.25f,3.5f};
    auto next=source.observe(actual);assert(next["instance"]==first["instance"] && next["sequence"].toULongLong()>first["sequence"].toULongLong());
    assert(next["source"].toMap()["rawDriveKeys"].toList()[2].toFloat()==-.8f);
    assert(next["source"].toMap()["driveKeys"].toList()[2].toFloat()==0);
    assert(original["feetPosition"].toList()==QVariantList({1.0,2.0,3.0})); // Original cannot be retimed/replaced.
    actual.feet.x=std::numeric_limits<float>::quiet_NaN();assert(source.observe(actual).isEmpty());
    actual.feet.x=0;actual.orientation={0,0,0,0};assert(source.observe(actual).isEmpty());
    actual.orientation={1,0,0,0};actual.controllerState=5;assert(source.observe(actual).isEmpty());
    actual.controllerState=0;LifecycleDriveObservation replacement;
    assert(replacement.observe(actual)["instance"]!=first["instance"]);
}
