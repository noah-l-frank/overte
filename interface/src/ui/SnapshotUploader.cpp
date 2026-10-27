//
//  SnapshotUploader.cpp
//  interface/src/ui
//
//  Created by Howard Stearns on 8/22/2016
//  Copyright 2016 High Fidelity, Inc.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#include "SnapshotUploader.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "../../../tests/device/native/IOSSnapshotUploadObservation.h"
#include "../../../tests/device/native/IOSSnapshotCausalDispatch.h"
#endif

#include <QtCore/QJsonDocument>
#include <QtCore/QJsonArray>

#include <AddressManager.h>

#include "scripting/WindowScriptingInterface.h"

SnapshotUploader::SnapshotUploader(QUrl inWorldLocation, QString pathname) :
    _inWorldLocation(inWorldLocation),
    _pathname(pathname) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    if (auto* book=overte::e2e::IOSSnapshotUploadObservation::get()) {_featureUploadId=book->begin(this,_pathname,_requests.snapshot());}
    if (auto* causal=overte::e2e::IOSSnapshotCausalDispatch::get()) {causal->associated(_featureUploadId);}
#endif
}

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
std::shared_ptr<overte::e2e::IOSRequestObservation> SnapshotUploader::featureRequestObservation(const QString& stage,const overte::network::RequestTicket& ticket) {
#if defined(OVERTE_IOS_E2E_TEST_BUILD)
    if (auto* book=overte::e2e::IOSSnapshotUploadObservation::get()) {return book->observer(_featureUploadId,stage,ticket);}
#endif
    return {};
}
void SnapshotUploader::featureFileRejected() {
#if defined(OVERTE_IOS_E2E_TEST_BUILD)
    if (auto* book=overte::e2e::IOSSnapshotUploadObservation::get()) {book->event(_featureUploadId,"file-rejected",_requests.snapshot(),_finished,true);}
#endif
}
#endif

void SnapshotUploader::cancel() {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    auto* book=overte::e2e::IOSSnapshotUploadObservation::get();
    if (book) {book->event(_featureUploadId,"cancel-entry",_requests.snapshot(),_finished);}
#endif
    if (_finished) { return; }
    _finished = true;
    _requests.setActive(false);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    if (book) {book->event(_featureUploadId,"cancel-invalidated",_requests.snapshot(),_finished);}
#endif
    emit finished(_pathname, "cancelled", "upload-cancelled");
    deleteLater();
}

void SnapshotUploader::complete(bool error, const QString& reply) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    auto* book=overte::e2e::IOSSnapshotUploadObservation::get();
    if (book) {book->event(_featureUploadId,"completion-entry",_requests.snapshot(),_finished,error);}
#endif
    if (_finished || !_requests.snapshot().current()) { return; }
    _finished = true;
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    if (book) {book->event(_featureUploadId,"completion-issued",_requests.snapshot(),_finished,error);}
#endif
    emit DependencyManager::get<WindowScriptingInterface>()->snapshotShared(error, reply);
    emit finished(_pathname, error ? "error" : "success", error ? "upload-failed" : QString());
    deleteLater();
}

void SnapshotUploader::uploadSuccess(QNetworkReply* reply) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    overte::e2e::IOSSnapshotUploadCallback observed(_featureUploadId,"upload-success",reply,_finished,_requests.snapshot());
#endif
    if (_finished || !_requests.snapshot().current()) { return; }
    const QString STORY_UPLOAD_URL = "/api/v1/user_stories";

    // parse the reply for the thumbnail_url
    QByteArray contents = reply->readAll();
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    if (auto* book=overte::e2e::IOSSnapshotUploadObservation::get()) {book->response(_featureUploadId,reply,contents);}
#endif
    QJsonParseError jsonError;
    auto doc = QJsonDocument::fromJson(contents, &jsonError);
    if (jsonError.error == QJsonParseError::NoError) {
        auto dataObject = doc.object().value("data").toObject();
        QString thumbnailUrl = dataObject.value("thumbnail_url").toString();
        QString imageUrl = dataObject.value("image_url").toString();
        QString snapshotID = dataObject.value("id").toString();
        QString originalImageFileName = dataObject.value("original_image_file_name").toString();
        if (thumbnailUrl.isEmpty() || imageUrl.isEmpty()) { complete(true, "Invalid snapshot upload response"); return; }
        QString placeName = _inWorldLocation.authority(); // We currently only upload shareable places, in which case this is just host.
        QString currentPath = _inWorldLocation.path();

        // create json post data
        QJsonObject rootObject;
        QJsonObject userStoryObject;
        QJsonObject detailsObject;
        detailsObject.insert("image_url", imageUrl);
        if (dataObject.contains("shareable_url")) {
            detailsObject.insert("shareable_url", dataObject.value("shareable_url").toString());
        }
        detailsObject.insert("snapshot_id", snapshotID);
        detailsObject.insert("original_image_file_name", originalImageFileName);
        QString pickledDetails = QJsonDocument(detailsObject).toJson();
        userStoryObject.insert("details", pickledDetails);
        userStoryObject.insert("thumbnail_url", thumbnailUrl);
        userStoryObject.insert("place_name", placeName);
        userStoryObject.insert("path", currentPath);
        userStoryObject.insert("action", "snapshot");
        userStoryObject.insert("audience", "for_url");
        rootObject.insert("user_story", userStoryObject);

        auto accountManager = DependencyManager::get<AccountManager>();
        JSONCallbackParameters callbackParams(this, "createStorySuccess", "createStoryFailure");
        callbackParams.requestTicket = nextTicket();
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
        callbackParams.featureRequestObservation=featureRequestObservation("story",callbackParams.requestTicket);
#endif

        accountManager->sendRequest(STORY_UPLOAD_URL,
            AccountManagerAuth::Required,
            QNetworkAccessManager::PostOperation,
            callbackParams,
            QJsonDocument(rootObject).toJson());

    } else {
        complete(true, contents);
    }
}

void SnapshotUploader::uploadFailure(QNetworkReply* reply) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    overte::e2e::IOSSnapshotUploadCallback observed(_featureUploadId,"upload-failure",reply,_finished,_requests.snapshot());
#endif
    if (_finished || !_requests.snapshot().current()) { return; }
    QString replyString = reply->readAll();
    qWarning() << "Snapshot upload failed";
    if (replyString.size() == 0) {
        replyString = reply->errorString();
    }
    replyString = replyString.left(1000); // Only print first 1000 characters of error
    complete(true, replyString);
}

void SnapshotUploader::createStorySuccess(QNetworkReply* reply) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    overte::e2e::IOSSnapshotUploadCallback observed(_featureUploadId,"story-success",reply,_finished,_requests.snapshot());
#endif
    if (_finished || !_requests.snapshot().current()) { return; }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    const auto originalReply=reply->readAll();
    if (auto* book=overte::e2e::IOSSnapshotUploadObservation::get()) {book->response(_featureUploadId,reply,originalReply);}
    QString replyString = originalReply;
#else
    QString replyString = reply->readAll();
#endif
    QJsonParseError error;
    const auto document = QJsonDocument::fromJson(replyString.toUtf8(), &error);
    const auto story = document.object().value("user_story").toObject();
    if (error.error != QJsonParseError::NoError || !story.contains("id") ||
            story.value("details").toObject().value("image_url").toString().isEmpty()) {
        complete(true, "Invalid snapshot story response"); return;
    }
    complete(false, replyString);
}

void SnapshotUploader::createStoryFailure(QNetworkReply* reply) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
    overte::e2e::IOSSnapshotUploadCallback observed(_featureUploadId,"story-failure",reply,_finished,_requests.snapshot());
#endif
    if (_finished || !_requests.snapshot().current()) { return; }
    QString replyString = reply->readAll();
    qWarning() << "Snapshot story upload failed";
    if (replyString.size() == 0) {
        replyString = reply->errorString();
    }
    replyString = replyString.left(1000); // Only print first 1000 characters of error
    complete(true, replyString);
}

