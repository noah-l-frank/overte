// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original history helper execution; HTTP/Model callers remain explicit seams.
#include <QCoreApplication>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QJsonDocument>
#include "libraries/render-utils/src/FeatureModelLoads.h"
#include "libraries/networking/src/FeatureResourceReplies.h"
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
    qInfo("PASS: original generation/failure/fallback history and non-consuming owned HTTP reply provenance");return 0;
}
