// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Real native helper with explicit synthetic pose/network producers only.
#include <QCoreApplication>
#include <QThread>
#include <QTemporaryDir>
#include <QFile>
#include <QJsonArray>
#include <iostream>
#include "tests/device/native/ChatPeerControl.h"
#include "tests/device/native/ChatObservation.h"
#include "tests/device/native/ChatActorFiles.h"
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);overte::e2e::ChatPeerControl peer;overte::e2e::ChatObservation received;
    const QUuid self("11111111-1111-4111-8111-111111111111"),mixer("22222222-2222-4222-8222-222222222222");
    QVariantMap position{{"x",2.125},{"y",0.0},{"z",2.0}};const auto original=position;QStringList sent;bool ignoreWrite{false};
    if (!peer.configure([&] { return position; },[&](const QVariantMap& value) { if (!ignoreWrite) { position=value; } },[&](const QString& value) { sent.append(value); })) { return 1; }
    const QString run(32,'a'),instance(32,'b');
    auto command=[&](const QString& operation,const QString& action="feature-chat-peer") {
        return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"action",action},{"operation",operation},{"runId",run}};
    };
    auto input=[&](const QString& operation) { return peer.request(command(operation),instance,self,mixer); };
    auto initial=input("inspect");if (initial.isEmpty() || initial.value("source").toMap().value("leasePresent").toBool()) { return 2; }
    auto lease=input("lease");if (lease.isEmpty() || !peer.leased()) { return 3; }
    // The original fixture update has stopped; native waits for actual stable
    // pose after its lease flag, instead of echoing a requested coordinate.
    position["x"]=2.25;input("inspect");QThread::msleep(110);auto admitted=input("inspect");
    const auto captured=position;
    if (!admitted.value("source").toMap().value("admitted").toBool() || admitted.value("source").toMap().value("originalPosition").toMap()!=captured) { return 4; }
    auto opened=received.request(command("observe","feature-chat-observe"),self,mixer);
    auto sentInput=input("send-domain-reply");if (sentInput.isEmpty() || sent.size()!=1) { return 5; }
    auto native=received.request(command("inspect","feature-chat-observe"),self,mixer);
    if (!native.value("source").toMap().value("events").toList().isEmpty()) { return 6; }
    if (!input("send-domain-reply").isEmpty() || sent.size()!=1) { return 7; }
    const auto distant=input("send-local-distant");if (distant.isEmpty() || sent.size()!=2 || position.value("x").toDouble()-captured.value("x").toDouble()<100) { return 8; }
    const auto actualPayload=QJsonDocument::fromJson(sent.last().toUtf8()).object();
    if (actualPayload.value("position").toObject()!=QJsonObject::fromVariantMap(position) || actualPayload.value("message")!="hidden-"+run || actualPayload.value("channel")!="local") { return 9; }
    // A separate explicit synthetic receipt producer is required, preserving
    // its sender and localOnly facts; no Send callback inserted this event.
    received.received("chat",sent.last(),mixer,false);
    if (received.request(command("inspect","feature-chat-observe"),self,mixer).value("source").toMap().value("events").toList().size()!=1) { return 10; }
    auto restored=input("restore");if (restored.isEmpty() || peer.leased() || position!=captured) { return 11; }
    const auto handback=restored.value("source").toMap().value("handback");position["x"]=3.0;
    auto resumed=input("restore");if (resumed.isEmpty() || position.value("x").toDouble()!=3.0 || resumed.value("source").toMap().value("handback")!=handback) { return 12; }
    if (!input("lease").isEmpty() || !input("send-local-reply").isEmpty() || sent.size()!=2) { return 13; }
    // Separate owner with an actual foreign pose change must refuse cleanup.
    overte::e2e::ChatPeerControl foreign;
    foreign.configure([&] { return position; },[&](const QVariantMap& value) { position=value; },[&](const QString& value) { sent.append(value); });
    foreign.request(command("lease"),instance,self,mixer);QThread::msleep(110);foreign.request(command("inspect"),instance,self,mixer);
    position["x"]=4.0;
    if (!foreign.request(command("restore"),instance,self,mixer).isEmpty() || !foreign.leased()) { return 14; }
    // Exercise the actual private file dispatcher too; the original native
    // result is published by this actor, never reconstructed by a host reader.
    QTemporaryDir directory;if (!directory.isValid()) { return 15; }
    QFile::setPermissions(directory.path(),QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);
    overte::e2e::ChatActorFiles files(directory.path(),QString(64,'c'),instance);if (!files.available()) { return 16; }
    auto query=command("inspect");QFile queryFile(directory.path()+"/chat-actor-command.v1.json");
    if (!queryFile.open(QIODevice::WriteOnly|QIODevice::NewOnly)) { return 17; }
    queryFile.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);
    const auto bytes=QJsonDocument(QJsonObject::fromVariantMap(query)).toJson(QJsonDocument::Compact)+'\n';
    if (queryFile.write(bytes)!=bytes.size()) { return 18; }queryFile.close();
    files.tick([&](const QVariantMap& request) { return peer.request(request,instance,self,mixer); });
    QFile resultFile(directory.path()+"/feature-chat-observation.json");if (!resultFile.open(QIODevice::ReadOnly)) { return 19; }
    const auto envelope=QJsonDocument::fromJson(resultFile.readAll()).object();resultFile.close();
    if (envelope.value("actorFileVersion")!=1 || envelope.value("native").toObject().value("chatPeerVersion")!=1
            || envelope.value("native").toObject().value("commandId").toString()!=query.value("commandId").toString()) { return 20; }
    std::cout<<QJsonDocument(QJsonObject::fromVariantMap(resumed)).toJson(QJsonDocument::Compact).constData()<<'\n';
    std::cout<<"PASS: native peer lease/settle, actual send payload pose, at-most-once stimuli, independent receive cache and immutable original handback\n";
    return 0;
}
