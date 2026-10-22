// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original history helper execution; HTTP/Model callers remain explicit seams.
#include <QCoreApplication>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QJsonDocument>
#include "libraries/render-utils/src/FeatureModelLoads.h"
#include "libraries/networking/src/FeatureResourceReplies.h"
#include "libraries/networking/src/FeaturePeopleReplies.h"
#include "libraries/entities/src/FeatureAvatarEntityOrigins.h"
#include "tests/device/native/MeasuredCameraLease.h"
struct Reply : QNetworkReply {
    QByteArray raw{"original missing resource"};qint64 cursor{0};
    explicit Reply(const QUrl& url) {
        setUrl(url);setAttribute(QNetworkRequest::HttpStatusCodeAttribute,404);
        setError(ContentNotFoundError,"owned 404");setRawHeader("X-Overte-Fixture-Response",QByteArray(32,'c'));
        open(QIODevice::ReadOnly);setFinished(true);
    }
    void abort() override {}
    qint64 bytesAvailable() const override { return raw.size()-cursor+QNetworkReply::bytesAvailable(); }
    qint64 readData(char* data,qint64 maximum) override { const auto n=qMin(maximum,raw.size()-cursor);memcpy(data,raw.constData()+cursor,n);cursor+=n;return n; }
};
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);
    overte::e2e::FeatureModelLoads model;
    const QUrl a("https://controlled.invalid/feature-fixture/v1/runs/"+QString(32,'a')+"/tickets/"+QString(32,'b')+"/avatar-a.fst");
    auto missing=a;missing.setPath(missing.path().replace("avatar-a.fst","missing.fst"));
    model.requested(a);model.finished(true,a);const auto first=model.snapshot();
    model.requested(missing);model.finished(false,missing);model.finished(true,QUrl("qrc:/meshes/defaultAvatar_full.fst"));
    const auto failed=model.snapshot();const auto events=failed.value("events").toList();
    if (!failed.value("complete").toBool() || failed.value("currentGeneration").toULongLong()!=2 || events.size()!=5
            || events[3].toMap().value("success").toBool() || !events[4].toMap().value("success").toBool()
            || events[3].toMap().value("generation")!=events[4].toMap().value("generation")) { return 1; }
    model.requested(a);const auto recovered=model.snapshot();
    if (recovered.value("currentGeneration").toULongLong()!=3 || recovered.value("events").toList().mid(0,5)!=events
            || first.value("events").toList().size()!=2) { return 2; }
    Reply reply(missing);auto& replies=overte::e2e::FeatureResourceReplies::instance();
    replies.completed(&reply,missing);
    if (reply.readAll()!=reply.raw) { return 3; } // Observation never consumes product bytes.
    auto observed=replies.snapshot(QString(32,'a'));const auto rows=observed.value("events").toList();
    if (!observed.value("complete").toBool() || rows.size()!=1 || rows[0].toMap().value("httpStatus").toInt()!=404
            || rows[0].toMap().value("networkError").toInt()!=QNetworkReply::ContentNotFoundError
            || rows[0].toMap().value("responseId").toString()!=QString(32,'c')) { return 4; }
    Reply unrelated(QUrl("https://controlled.invalid/private"));replies.completed(&unrelated,unrelated.url());
    if (replies.snapshot(QString(32,'a')).value("events").toList()!=rows || !replies.snapshot(QString(32,'d')).value("events").toList().isEmpty()) { return 5; }
    auto& people=overte::e2e::FeaturePeopleReplies::instance();
    Reply social(QUrl("https://controlled.invalid/api/v1/user/connection_request"));
    const QByteArray sent("{\"user_connection_request\":{\"node_id\":\"original\"}}");
    people.completed(&social,social.url(),"POST",sent);
    if (social.readAll()!=social.raw) { return 6; }
    const auto received=people.snapshot();const auto socialRows=received.value("events").toList();
    if (!received.value("complete").toBool() || socialRows.size()!=1 || socialRows[0].toMap().value("method")!="POST"
            || socialRows[0].toMap().value("requestBodySha256").toString()!=QString::fromLatin1(QCryptographicHash::hash(sent,QCryptographicHash::Sha256).toHex())
            || socialRows[0].toMap().value("responseId").toString()!=QString(32,'c')) { return 7; }
    people.completed(&unrelated,unrelated.url(),"GET",{});
    if (people.snapshot().value("events").toList()!=socialRows) { return 8; }
    auto& origins=overte::e2e::FeatureAvatarEntityOrigins::instance();
    const QUuid entity("11111111-1111-4111-8111-111111111111"),parent("22222222-2222-4222-8222-222222222222");
    const auto url=a.toString().replace("avatar-a.fst","gltf-bundle/main.gltf");auto entityObject=std::make_shared<int>(17);
    origins.added(entity,url,parent,17,true,entityObject);
    const auto original=origins.snapshot(QString(32,'a'));const auto returned=original.value("events").toList();
    if (!original.value("complete").toBool() || returned.size()!=1 || returned[0].toMap().value("entityId").toString()!=entity.toString(QUuid::WithoutBraces)
            || returned[0].toMap().value("parentJointIndex").toInt()!=17 || !returned[0].toMap().value("treePresent").toBool()) { return 9; }
    origins.added(QUuid::createUuid(),"https://controlled.invalid/foreign",parent,17,true,entityObject);
    if (origins.snapshot(QString(32,'a')).value("events").toList()!=returned || !origins.snapshot(QString(32,'e')).value("events").toList().isEmpty()) { return 10; }
    if (!origins.knownIds(QString(32,'a')).contains(entity) || !origins.observe(QString(32,'a'),entity,entityObject)
            || origins.retained(QString(32,'a')).size()!=1) { return 25; }
    auto replacement=std::make_shared<int>(18);
    if (origins.observe(QString(32,'a'),entity,replacement)) { return 26; }
    entityObject.reset();if (!origins.retained(QString(32,'a')).isEmpty() || !origins.knownIds(QString(32,'a')).contains(entity)) { return 27; }
    const auto remoteId=QUuid::createUuid();
    if (!origins.observe(QString(32,'a'),remoteId,replacement) || !origins.knownIds(QString(32,'a')).contains(remoteId)) { return 28; }
    replacement.reset();if (!origins.retained(QString(32,'a')).isEmpty()) { return 29; }
    using Lease=overte::e2e::MeasuredCameraLease;
    const QVariantMap cameraOriginal{{"mode","selfie"},{"position",QVariantList{0.,1.6,4.}},
        {"rotation",QVariantList{0.,0.,0.,1.}},{"projection",QVariantList{1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,-1.,-1.,0.,0.,-.2,0.}}};
    QObject camera;QVariantMap actualView=cameraOriginal;bool ignore=false;
    Lease::Source cameraSource{&camera,[&] { return actualView; },[&](const QVariantMap& captured,bool hold) {
        if (!ignore) { actualView=captured;if (hold) { actualView.insert("mode","independent"); } }
    }};
    Lease lease;
    if (!lease.prepare(cameraSource) || !lease.owns(cameraSource) || actualView.value("mode")!="independent"
            || lease.observe(cameraSource).value("originalView").toMap()!=cameraOriginal) { return 11; }
    if (lease.prepare(cameraSource) || !lease.release(cameraSource) || actualView!=cameraOriginal || !lease.restored()
            || !lease.release(cameraSource)) { return 12; }
    const auto returnedViewProof=lease.observe(cameraSource).value("restoration").toMap();
    if (returnedViewProof.isEmpty() || returnedViewProof.value("view").toMap()!=cameraOriginal || !returnedViewProof.value("originalObject").toBool()) { return 23; }
    actualView.insert("mode","first person look at");actualView.insert("position",QVariantList{8.,1.6,4.});const auto laterView=actualView;
    if (!lease.release(cameraSource) || actualView!=laterView || lease.observe(cameraSource).value("restoration").toMap()!=returnedViewProof) { return 24; }
    Lease replaced;actualView=cameraOriginal;if (!replaced.prepare(cameraSource)) { return 13; }
    QObject foreign;auto foreignSource=cameraSource;foreignSource.object=&foreign;
    if (replaced.owns(foreignSource) || replaced.release(foreignSource) || replaced.observe(foreignSource).value("originalObject").toBool()) { return 14; }
    Lease moved;actualView=cameraOriginal;if (!moved.prepare(cameraSource)) { return 15; }
    actualView.insert("position",QVariantList{1.,1.6,4.});const auto foreignView=actualView;
    if (moved.owns(cameraSource) || moved.release(cameraSource) || actualView!=foreignView) { return 16; }
    Lease switched;actualView=cameraOriginal;if (!switched.prepare(cameraSource)) { return 17; }
    switched.modeChanged(); // Original Camera signal is hooked by the product caller.
    if (switched.owns(cameraSource) || switched.release(cameraSource)
            || switched.observe(cameraSource).value("foreignModeChanges").toInt()!=1) { return 18; }
    Lease ignored;actualView=cameraOriginal;ignore=true;
    if (ignored.prepare(cameraSource) || ignored.release(cameraSource) || actualView!=cameraOriginal) { return 19; }
    ignore=false;Lease restoreIgnored;actualView=cameraOriginal;if (!restoreIgnored.prepare(cameraSource)) { return 20; }
    ignore=true;if (restoreIgnored.release(cameraSource) || restoreIgnored.restored()) { return 21; }
    ignore=false;Lease unsupported;actualView=cameraOriginal;actualView.insert("mode","entity");
    if (unsupported.prepare(cameraSource)) { return 22; }
    qInfo("PASS: original model/wire/entity histories and owned measured camera lease counterexamples");return 0;
}
