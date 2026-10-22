//
//  Snapshot.cpp
//  interface/src/ui
//
//  Created by Stojce Slavkovski on 1/26/14.
//  Copyright 2014 High Fidelity, Inc.
//  Copyright 2022 Overte e.V.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//

#include "Snapshot.h"

#include <QtCore/QDateTime>
#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtCore/QTemporaryFile>
#include <QtCore/QUrl>
#include <QtCore/QUrlQuery>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonArray>
#include <QtNetwork/QHttpMultiPart>
#include <QPainter>
#include <QImageWriter>
#include <QtConcurrent/QtConcurrentRun>

#include <AccountManager.h>
#include <AddressManager.h>
#include <avatar/AvatarManager.h>
#include <avatar/MyAvatar.h>
#include <shared/FileUtils.h>
#include <NodeList.h>
#include <OffscreenUi.h>
#include <SharedUtil.h>
#include <SecondaryCamera.h>
#include <plugins/DisplayPlugin.h>

#include "Application.h"
#include "display-plugins/CompositorHelper.h"
#include "scripting/WindowScriptingInterface.h"
#include "MainWindow.h"
#include "Snapshot.h"
#include "SnapshotUploader.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <PhoneSnapshotUploadEvidence.h>
#endif
#include "SnapshotAnimated.h"
#include "SnapshotStorage.h"
#include <QMutexLocker>
#include <QThread>
#include <QGuiApplication>
#include <QFutureWatcher>
#include <QRegularExpression>
#include <algorithm>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "../../../tests/device/native/PhoneSnapshotHistory.h"
#include "../../../tests/device/native/PhoneSnapshotCaptureFiles.h"
#include "../../../tests/device/native/PhoneSnapshotScriptHistory.h"
#include "../../../tests/device/native/PhoneSnapshotSettingsLease.h"
#include <SettingManager.h>
#include <ScriptManager.h>
#endif

// filename format: overte-snap-by-%username%-on-%date%_%time%_@-%location%.png
// %1 <= username, %2 <= date and time, %3 <= current location
const QString FILENAME_PATH_FORMAT = "overte-snap-by-%1-on-%2";
const QString DEFAULT_FORMAT = "png";
const QString DATETIME_FORMAT = "yyyy-MM-dd_hh-mm-ss";
const QString SNAPSHOTS_DIRECTORY = "Snapshots";
const QString URL = "overte_url";
static const int SNAPSHOT_360_TIMER_INTERVAL = 350;
static const QList<QString> SUPPORTED_IMAGE_FORMATS = { "jpg", "jpeg", "png", "webp" };

Snapshot::Snapshot() {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    _featureSnapshotHistory=std::make_shared<overte::e2e::PhoneSnapshotHistory>();
    _featureSnapshotScriptHistory=std::make_shared<overte::e2e::PhoneSnapshotScriptHistory>();
    connect(this,&Snapshot::captureStatusChanged,this,[this](const QString& id,const QString& phase,const QString& path,const QString& error) {
        _featureSnapshotHistory->record("capture-status",id,phase,path,error);
        overte::e2e::PhoneSnapshotCaptureFiles::get().terminal(id,phase,path);
    });
    connect(this,&Snapshot::uploadStatusChanged,this,[this](const QString& path,const QString& status,const QString& error) {
        _featureSnapshotHistory->record("upload-status",path,status,path,error);
    });
#endif
    _snapshotTimer.setSingleShot(false);
    _snapshotTimer.setTimerType(Qt::PreciseTimer);
    _snapshotTimer.setInterval(SNAPSHOT_360_TIMER_INTERVAL);
    connect(&_snapshotTimer, &QTimer::timeout, this, &Snapshot::takeNextSnapshot);

    _snapshotIndex = 0;
    _oldEnabled = false;
    _oldAttachedEntityId = 0;
    _oldOrientation = 0;
    _oldvFoV = 0;
    _oldNearClipPlaneDistance = 0;
    _oldFarClipPlaneDistance = 0;
    connect(qApp, &QGuiApplication::applicationStateChanged, this, [this](Qt::ApplicationState state) {
        if (state == Qt::ApplicationActive || !nativeReviewEnabled()) { return; }
        QStringList requests;
        { QMutexLocker lock(&_captureMutex); requests = _captures.keys(); }
        for (const auto& request : requests) { cancelCapture(request); }
        cancelUploads();
    });
}

Snapshot::~Snapshot() {
    for (const auto& capture : _captures) { capture->cancel(); }
    for (const auto& uploader : _uploads) { if (uploader) { uploader->disconnect(this); uploader->cancel(); delete uploader.data(); } }
}

bool Snapshot::nativeReviewEnabled() const {
#if defined(Q_OS_ANDROID) || defined(Q_OS_IOS)
    return true;
#else
    return false;
#endif
}

QUrl Snapshot::snapshotFileUrl(const QString& path) const {
    const auto owned = overte::snapshot::exportPath(path);
    return owned.isEmpty() ? QUrl() : QUrl::fromLocalFile(owned);
}

SnapshotCapture Snapshot::beginCapture(const QString& requestId) {
    auto capture = std::make_shared<SnapshotCaptureRequest>(requestId);
    if (requestId.isEmpty()) { return capture; } // Existing un-ticketed callers.
    QMutexLocker lock(&_captureMutex);
    if (requestId.size() > 64 || !QRegularExpression(QStringLiteral("^[A-Za-z0-9_-]+$")).match(requestId).hasMatch() ||
            _captures.size() >= 8 || _captures.contains(requestId)) {
        lock.unlock();
        emit captureStatusChanged(requestId, "error", {}, "capture-busy-or-invalid-request");
        return {};
    }
    _captures.insert(requestId, capture);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    _featureSnapshotHistory->record("capture-begin",requestId);
    overte::e2e::PhoneSnapshotCaptureFiles::get().begin(requestId);
#endif
    return capture;
}

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
void Snapshot::featureCaptureEvent(const QString& kind,const QString& id,const QString& mode,int revision) {
    _featureSnapshotScriptHistory->record(kind,id,mode,revision,ScriptManager::featureNativeCallContext());
}

QVariantMap Snapshot::featureSnapshotSettings(const QVariantMap& command,bool closed) {
    using Lease=overte::e2e::PhoneSnapshotSettingsLease;
    if (QThread::currentThread()!=thread() || !QCoreApplication::arguments().contains("--testScript")
            || !DependencyManager::isSet<Setting::Manager>()) { return {}; }
    if (!Lease::validCommand(command)) { return {}; }
    const auto json=QJsonObject::fromVariantMap(command);const auto run=json.value("runId").toString();
    auto owner=_featureSnapshotSettingsScopes.value(run);
    if (!owner) {
        if (json.value("operation")!=QJsonValue("capture") || !closed || _featureSnapshotSettingsScopes.size()>=32) { return {}; }
        for (const auto& other:_featureSnapshotSettingsScopes) { if (!other || !other->retired()) { return {}; } }
        owner=std::make_shared<Lease>();_featureSnapshotSettingsScopes.insert(run,owner);
    }
    const auto manager=DependencyManager::get<Setting::Manager>();
    const auto read=[&]() -> QVariantMap {
        // Read the real typed Handle first, including its original unset state.
        // Its ordinary lazy initialization precedes the captured raw map.
        const bool set=_snapshotFormat.isSet();const auto value=_snapshotFormat.get();
        return {{"format",QVariantMap{{"set",set},{"value",value}}},{"entries",manager->featureSnapshotEntries()}};
    };
    const auto entries=[&](const QVariantMap& expected,const QVariantMap& original) {
        return manager->featureRestoreSnapshotEntries(expected,original);
    };
    const auto format=[&](const QVariantMap& original) {
        if (original.value("set").toBool()) { _snapshotFormat.set(original.value("value").toString()); }
        else { _snapshotFormat.remove(); }
        return _snapshotFormat.isSet()==original.value("set").toBool() && _snapshotFormat.get()==original.value("value").toString();
    };
    return owner->request(command,closed,read,[&](const QVariantMap& expected,const QVariantMap& original) {
        return overte::e2e::restoreSnapshotSettings(expected,original,read,entries,format);
    });
}

QVariantMap Snapshot::featureSnapshotObservation() {
    if (QThread::currentThread()!=thread() || !QCoreApplication::arguments().contains("--testScript")) { return {}; }
    QVariantList captures;QStringList uploads;QVariantMap history;
    {
        QMutexLocker lock(&_captureMutex);
        auto ids=_captures.keys();std::sort(ids.begin(),ids.end());
        if (ids.size()>8) { return {}; }
        for (const auto& id:ids) {
            const auto capture=_captures.value(id);if (!capture || capture->id!=id) { return {}; }
            const auto state=capture->state.load();
            captures.append(QVariantMap{{"id",id},{"state",state==SnapshotCaptureRequest::State::Active ? "active"
                : state==SnapshotCaptureRequest::State::Cancelled ? "cancelled" : "completed"},{"announced",capture->announced.load()}});
        }
        // beginCapture records under this same lock, so a concurrent insertion
        // cannot fall between the current inventory and its original history.
        history=_featureSnapshotHistory->snapshot();
    }
    if (_uploads.size()>64) { return {}; }
    for (auto it=_uploads.begin();it!=_uploads.end();++it) { if (it.value()) { uploads.append(it.key()); } }
    std::sort(uploads.begin(),uploads.end());
    if (history.isEmpty()) { return {}; }
    return {{"phoneSnapshotObservationVersion",1},{"nativeReview",nativeReviewEnabled()},
        {"storageRoot",overte::snapshot::storageRoot()},{"captures",captures},{"uploads",uploads},{"history",history},
        {"scriptHistory",_featureSnapshotScriptHistory->snapshot()}};
}
#endif

void Snapshot::captureStatus(const SnapshotCapture& capture, const QString& phase, const QString& path, const QString& error) {
    if (!capture || !capture->current()) { return; }
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, capture, phase, path, error] { captureStatus(capture, phase, path, error); }, Qt::QueuedConnection);
        return;
    }
    const bool terminal = phase == "complete" || phase == "error";
    if (terminal && !capture->finish()) { return; }
    if (terminal) { capture->announced.store(true); }
    if (!capture->id.isEmpty()) {
        if (terminal) { QMutexLocker lock(&_captureMutex); if (_captures.value(capture->id) == capture) { _captures.remove(capture->id); } }
        emit captureStatusChanged(capture->id, phase, path, error);
    }
}

void Snapshot::cancelCapture(const QString& requestId) {
    SnapshotCapture capture;
    { QMutexLocker lock(&_captureMutex); capture = _captures.take(requestId); }
    if (!capture) { return; }
    if (!capture->cancel()) { return; } // Invalidate render/worker callbacks immediately.
    QMetaObject::invokeMethod(this, [this, capture] {
        SnapshotAnimated::cancelCapture(capture);
        if (_capture360 == capture) {
            _snapshotTimer.stop();
            _taking360Snapshot = false;
            _waitingOnSnapshot = false;
            restoreSecondaryCamera();
            _capture360.reset();
            for (auto& image : _imageArray) { image = {}; }
        }
        if (!capture->announced.exchange(true)) { emit captureStatusChanged(capture->id, "cancelled", {}, {}); }
    }, Qt::QueuedConnection);
}

SnapshotMetaData* Snapshot::parseSnapshotData(QString snapshotPath) {
    if (!QFile(snapshotPath).exists()) {
        return NULL;
    }

    QUrl url;

    if (snapshotPath.right(3) == "jpg") {
        QImage shot(snapshotPath);

        // no location data stored
        if (shot.text(URL).isEmpty()) {
            return NULL;
        }

        // parsing URL
        url = QUrl(shot.text(URL), QUrl::ParsingMode::StrictMode);
    } else {
        return NULL;
    }

    SnapshotMetaData* data = new SnapshotMetaData();
    data->setURL(url);

    return data;
}

QString Snapshot::saveSnapshot(QImage image, const QString& filename, const QString& pathname) {
    QFile* snapshotFile = savedFileForSnapshot(image, false, filename, pathname);

    if (snapshotFile) {
        // we don't need the snapshot file, so close it, grab its filename and delete it
        snapshotFile->close();

        QString snapshotPath = QFileInfo(*snapshotFile).absoluteFilePath();

        delete snapshotFile;

        return snapshotPath;
    }

    return "";
}


static const float CUBEMAP_SIDE_PIXEL_DIMENSION = 2048.0f;
static const float SNAPSHOT_360_FOV = 90.0f;
static const float SNAPSHOT_360_NEARCLIP = 0.3f;
static const float SNAPSHOT_360_FARCLIP = 16384.0f;
static const glm::quat CAMERA_ORIENTATION_DOWN(glm::quat(glm::radians(glm::vec3(-90.0f, 0.0f, 0.0f))));
static const glm::quat CAMERA_ORIENTATION_FRONT(glm::quat(glm::radians(glm::vec3(0.0f, 0.0f, 0.0f))));
static const glm::quat CAMERA_ORIENTATION_LEFT(glm::quat(glm::radians(glm::vec3(0.0f, 90.0f, 0.0f))));
static const glm::quat CAMERA_ORIENTATION_BACK(glm::quat(glm::radians(glm::vec3(0.0f, 180.0f, 0.0f))));
static const glm::quat CAMERA_ORIENTATION_RIGHT(glm::quat(glm::radians(glm::vec3(0.0f, 270.0f, 0.0f))));
static const glm::quat CAMERA_ORIENTATION_UP(glm::quat(glm::radians(glm::vec3(90.0f, 0.0f, 0.0f))));
void Snapshot::save360Snapshot(const glm::vec3& cameraPosition,
                               const bool& cubemapOutputFormat,
                               const bool& notify,
                               const QString& filename, const SnapshotCapture& capture) {
    if (_capture360) {
        captureStatus(capture, "error", {}, "capture-busy");
        return;
    }
    _capture360 = capture ? capture : beginCapture({});
    if (!_capture360 || !_capture360->current()) { _capture360.reset(); return; }
    _snapshotFilename = filename;
    _notify360 = notify;
    _cubemapOutputFormat = cubemapOutputFormat;
    SecondaryCameraJobConfig* secondaryCameraRenderConfig =
        static_cast<SecondaryCameraJobConfig*>(qApp->getRenderEngine()->getConfiguration()->getConfig("SecondaryCamera"));

    // Save initial values of secondary camera render config
    _oldEnabled = secondaryCameraRenderConfig->isEnabled();
    _oldAttachedEntityId = secondaryCameraRenderConfig->property("attachedEntityId");
    _oldOrientation = secondaryCameraRenderConfig->property("orientation");
    _oldPosition = secondaryCameraRenderConfig->property("position");
    _oldMirrorProjection = secondaryCameraRenderConfig->property("mirrorProjection");
    _oldPortalProjection = secondaryCameraRenderConfig->property("portalProjection");
    _oldTextureWidth = secondaryCameraRenderConfig->textureWidth;
    _oldTextureHeight = secondaryCameraRenderConfig->textureHeight;
    _oldvFoV = secondaryCameraRenderConfig->property("vFoV");
    _oldNearClipPlaneDistance = secondaryCameraRenderConfig->property("nearClipPlaneDistance");
    _oldFarClipPlaneDistance = secondaryCameraRenderConfig->property("farClipPlaneDistance");

    if (!_oldEnabled) {
        secondaryCameraRenderConfig->enableSecondaryCameraRenderConfigs(true);
    }

    secondaryCameraRenderConfig->resetSizeSpectatorCamera(static_cast<int>(CUBEMAP_SIDE_PIXEL_DIMENSION),
                                                          static_cast<int>(CUBEMAP_SIDE_PIXEL_DIMENSION));
    secondaryCameraRenderConfig->setProperty("attachedEntityId", "");
    secondaryCameraRenderConfig->setProperty("mirrorProjection", false);
    secondaryCameraRenderConfig->setProperty("portalProjection", false);
    secondaryCameraRenderConfig->setPosition(cameraPosition);
    secondaryCameraRenderConfig->setProperty("vFoV", SNAPSHOT_360_FOV);
    secondaryCameraRenderConfig->setProperty("nearClipPlaneDistance", SNAPSHOT_360_NEARCLIP);
    secondaryCameraRenderConfig->setProperty("farClipPlaneDistance", SNAPSHOT_360_FARCLIP);

    // Setup for Down Image capture
    secondaryCameraRenderConfig->setOrientation(CAMERA_ORIENTATION_DOWN);

    _snapshotIndex = 0;
    _taking360Snapshot = true;

    _snapshotTimer.start(SNAPSHOT_360_TIMER_INTERVAL);
}

void Snapshot::takeNextSnapshot() {
    if (_taking360Snapshot) {
        if (!_waitingOnSnapshot) {
            _waitingOnSnapshot = true;
            const auto capture = _capture360;
            const QPointer<Snapshot> guard(this);
            qApp->addSnapshotOperator(std::make_tuple([this, guard, capture](const QImage& snapshot) {
                qApp->postLambdaEvent([this, guard, capture, snapshot] {
                if (!guard) { return; }
                if (_capture360 != capture || !capture->current()) { return; }
                // Order is:
                // 0. Down
                // 1. Front
                // 2. Left
                // 3. Back
                // 4. Right
                // 5. Up
                if (_snapshotIndex < 6) {
                    _imageArray[_snapshotIndex] = snapshot;
                }

                SecondaryCameraJobConfig* config = static_cast<SecondaryCameraJobConfig*>(qApp->getRenderEngine()->getConfiguration()->getConfig("SecondaryCamera"));
                if (_snapshotIndex == 0) {
                    // Setup for Front Image capture
                    config->setOrientation(CAMERA_ORIENTATION_FRONT);
                } else if (_snapshotIndex == 1) {
                    // Setup for Left Image capture
                    config->setOrientation(CAMERA_ORIENTATION_LEFT);
                } else if (_snapshotIndex == 2) {
                    // Setup for Back Image capture
                    config->setOrientation(CAMERA_ORIENTATION_BACK);
                } else if (_snapshotIndex == 3) {
                    // Setup for Right Image capture
                    config->setOrientation(CAMERA_ORIENTATION_RIGHT);
                } else if (_snapshotIndex == 4) {
                    // Setup for Up Image capture
                    config->setOrientation(CAMERA_ORIENTATION_UP);
                } else if (_snapshotIndex == 5) {
                    _taking360Snapshot = false;
                }

                _waitingOnSnapshot = false;
                _snapshotIndex++;
                });
            }, 0.0f, false));
        }
    } else {
        _snapshotTimer.stop();

        restoreSecondaryCamera();
        const auto capture = _capture360;
        const auto filename = _snapshotFilename;
        const bool notify = _notify360;
        std::array<QImage, 6> images;
        std::copy(std::begin(_imageArray), std::end(_imageArray), images.begin());
        _capture360.reset();
        for (auto& image : _imageArray) { image = {}; }
        if (!capture || !capture->current()) { return; }
        captureStatus(capture, "processing");
        // Workers own immutable images/request state; a replacement cannot
        // mutate their camera faces or revive cancelled completion callbacks.
        auto watcher = new QFutureWatcher<QImage>(this);
        connect(watcher, &QFutureWatcher<QImage>::finished, this, [this, watcher, filename, notify, capture] {
            const auto image = watcher->result();
            watcher->deleteLater();
            complete360(image, filename, notify, capture);
        });
        const bool cubemap = _cubemapOutputFormat;
        watcher->setFuture(QtConcurrent::run([images, capture, cubemap] {
            return cubemap ? convertToCubemap(images, capture) : convertToEquirectangular(images, capture);
        }));
    }
}

void Snapshot::restoreSecondaryCamera() {
        SecondaryCameraJobConfig* config = static_cast<SecondaryCameraJobConfig*>(qApp->getRenderEngine()->getConfiguration()->getConfig("SecondaryCamera"));
        config->resetSizeSpectatorCamera(_oldTextureWidth, _oldTextureHeight);
        config->setProperty("attachedEntityId", _oldAttachedEntityId);
        config->setProperty("vFoV", _oldvFoV);
        config->setProperty("nearClipPlaneDistance", _oldNearClipPlaneDistance);
        config->setProperty("farClipPlaneDistance", _oldFarClipPlaneDistance);
        config->setProperty("orientation", _oldOrientation);
        config->setProperty("position", _oldPosition);
        config->setProperty("mirrorProjection", _oldMirrorProjection);
        config->setProperty("portalProjection", _oldPortalProjection);

        if (!_oldEnabled) {
            config->enableSecondaryCameraRenderConfigs(false);
        }

}

QImage Snapshot::convertToCubemap(std::array<QImage, 6> images, SnapshotCapture capture) {
    if (!capture->current() || std::any_of(images.begin(), images.end(), [](const QImage& image) { return image.isNull(); })) { return {}; }
    float outputImageHeight = CUBEMAP_SIDE_PIXEL_DIMENSION * 3.0f;
    float outputImageWidth = CUBEMAP_SIDE_PIXEL_DIMENSION * 4.0f;

    QImage outputImage(outputImageWidth, outputImageHeight, QImage::Format_RGB32);
    if (outputImage.isNull()) { return {}; }
    outputImage.fill(Qt::black);

    QPainter painter(&outputImage);
    QPoint destPos;

    // Paint DownImage
    destPos = QPoint(CUBEMAP_SIDE_PIXEL_DIMENSION, CUBEMAP_SIDE_PIXEL_DIMENSION * 2.0f);
    painter.drawImage(destPos, images[0]);

    // Paint FrontImage
    destPos = QPoint(CUBEMAP_SIDE_PIXEL_DIMENSION, CUBEMAP_SIDE_PIXEL_DIMENSION);
    painter.drawImage(destPos, images[1]);

    // Paint LeftImage
    destPos = QPoint(0, CUBEMAP_SIDE_PIXEL_DIMENSION);
    painter.drawImage(destPos, images[2]);

    // Paint BackImage
    destPos = QPoint(CUBEMAP_SIDE_PIXEL_DIMENSION * 3.0f, CUBEMAP_SIDE_PIXEL_DIMENSION);
    painter.drawImage(destPos, images[3]);

    // Paint RightImage
    destPos = QPoint(CUBEMAP_SIDE_PIXEL_DIMENSION * 2.0f, CUBEMAP_SIDE_PIXEL_DIMENSION);
    painter.drawImage(destPos, images[4]);

    // Paint UpImage
    destPos = QPoint(CUBEMAP_SIDE_PIXEL_DIMENSION, 0);
    painter.drawImage(destPos, images[5]);

    painter.end();

    return outputImage;
}

QImage Snapshot::convertToEquirectangular(std::array<QImage, 6> images, SnapshotCapture capture) {
    if (!capture->current() || std::any_of(images.begin(), images.end(), [](const QImage& image) { return image.size() != QSize(2048, 2048); })) { return {}; }
    // I got help from StackOverflow while writing this code:
    // https://stackoverflow.com/questions/34250742/converting-a-cubemap-into-equirectangular-panorama

    int cubeFaceWidth = static_cast<int>(CUBEMAP_SIDE_PIXEL_DIMENSION);
    int cubeFaceHeight = static_cast<int>(CUBEMAP_SIDE_PIXEL_DIMENSION);
    float outputImageHeight = CUBEMAP_SIDE_PIXEL_DIMENSION * 2.0f;
    float outputImageWidth = outputImageHeight * 2.0f;
    QImage outputImage(outputImageWidth, outputImageHeight, QImage::Format_RGB32);
    if (outputImage.isNull()) { return {}; }
    outputImage.fill(0);
    QRgb sourceColorValue;
    float phi, theta;

    for (int j = 0; j < outputImageHeight; j++) {
        if (!capture->current()) { return {}; }
        theta = (1.0f - ((float)j / outputImageHeight)) * PI;

        for (int i = 0; i < outputImageWidth; i++) {
            phi = ((float)i / outputImageWidth) * 2.0f * PI;

            float x = glm::sin(phi) * glm::sin(theta) * -1.0f;
            float y = glm::cos(theta);
            float z = glm::cos(phi) * glm::sin(theta) * -1.0f;

            float a = std::max(std::max(std::abs(x), std::abs(y)), std::abs(z));

            float xa = x / a;
            float ya = y / a;
            float za = z / a;

            // Pixel in the source images
            int xPixel, yPixel;
            QImage sourceImage;

            if (xa == 1) {
                // Right image
                xPixel = (int)((((za + 1.0f) / 2.0f) - 1.0f) * cubeFaceWidth);
                yPixel = (int)((((ya + 1.0f) / 2.0f)) * cubeFaceHeight);
                sourceImage = images[4];
            } else if (xa == -1) {
                // Left image
                xPixel = (int)((((za + 1.0f) / 2.0f)) * cubeFaceWidth);
                yPixel = (int)((((ya + 1.0f) / 2.0f)) * cubeFaceHeight);
                sourceImage = images[2];
            } else if (ya == 1) {
                // Down image
                xPixel = (int)((((xa + 1.0f) / 2.0f)) * cubeFaceWidth);
                yPixel = (int)((((za + 1.0f) / 2.0f) - 1.0f) * cubeFaceHeight);
                sourceImage = images[0];
            } else if (ya == -1) {
                // Up image
                xPixel = (int)((((xa + 1.0f) / 2.0f)) * cubeFaceWidth);
                yPixel = (int)((((za + 1.0f) / 2.0f)) * cubeFaceHeight);
                sourceImage = images[5];
            } else if (za == 1) {
                // Front image
                xPixel = (int)((((xa + 1.0f) / 2.0f)) * cubeFaceWidth);
                yPixel = (int)((((ya + 1.0f) / 2.0f)) * cubeFaceHeight);
                sourceImage = images[1];
            } else if (za == -1) {
                // Back image
                xPixel = (int)((((xa + 1.0f) / 2.0f) - 1.0f) * cubeFaceWidth);
                yPixel = (int)((((ya + 1.0f) / 2.0f)) * cubeFaceHeight);
                sourceImage = images[3];
            } else {
                qDebug() << "Unknown face encountered when processing 360 Snapshot";
                xPixel = 0;
                yPixel = 0;
            }

            xPixel = std::min(std::abs(xPixel), 2047);
            yPixel = std::min(std::abs(yPixel), 2047);

            sourceColorValue = sourceImage.pixel(xPixel, yPixel);
            outputImage.setPixel(i, j, sourceColorValue);
        }
    }

    return outputImage;
}

void Snapshot::complete360(const QImage& image, const QString& filename, bool notify, const SnapshotCapture& capture) {
    if (!capture->current()) { return; }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    overte::e2e::PhoneSnapshotCaptureFiles::Scope originalFileScope(capture->id);
#endif
    const auto path = saveSnapshot(image, filename);
    if (path.isEmpty()) { captureStatus(capture, "error", {}, "save-failed"); return; }
    emit DependencyManager::get<WindowScriptingInterface>()->snapshot360Taken(path, notify);
    captureStatus(capture, "complete", path);
}

QTemporaryFile* Snapshot::saveTempSnapshot(QImage image) {
    // return whatever we get back from saved file for snapshot
    return static_cast<QTemporaryFile*>(savedFileForSnapshot(image, true));
}

QFile* Snapshot::savedFileForSnapshot(QImage& shot,
                                      bool isTemporary,
                                      const QString& userSelectedFilename,
                                      const QString& userSelectedPathname) {
    // adding URL to snapshot
    QUrl currentURL = DependencyManager::get<AddressManager>()->currentPublicAddress();
    shot.setText(URL, currentURL.toString());

    QString username = DependencyManager::get<AccountManager>()->getAccountInfo().getUsername();
    // normalize username, replace all non alphanumeric with '-'
    username.replace(QRegularExpression("[^A-Za-z0-9_]"), "-");

    QDateTime now = QDateTime::currentDateTime();

    // If user has supplied a specific filename for the snapshot:
    //     If the user's requested filename has a suffix that's contained within SUPPORTED_IMAGE_FORMATS,
    //         DON'T append ".jpg" to the filename. QT will save the image in the format associated with the
    //         filename's suffix.
    //         If you want lossless Snapshots, supply a `.png` filename. Otherwise, use `.jpeg` or `.jpg`.
    //         For PNGs, we use a "quality" of "50". The output image quality is the same as "100"
    //             is the same as "0" -- the difference lies in the amount of compression applied to the PNG,
    //             which slightly affects the time it takes to save the image.
    //     Otherwise, ".jpg" is appended to the user's requested filename so that the image is saved in JPG format.
    // If the user hasn't supplied a specific filename for the snapshot:
    //     Save the snapshot in JPG format at "100" quality according to FILENAME_PATH_FORMAT
    int imageQuality = 100;
    QString filename;
    if (!userSelectedFilename.isNull()) {
        if (nativeReviewEnabled() && (userSelectedFilename.contains('/') || userSelectedFilename.contains('\\'))) { return nullptr; }
        QFileInfo snapshotFileInfo(userSelectedFilename);
        QString userSelectedFilenameSuffix = snapshotFileInfo.suffix();
        userSelectedFilenameSuffix = userSelectedFilenameSuffix.toLower();
        if (SUPPORTED_IMAGE_FORMATS.contains(userSelectedFilenameSuffix)) {
            filename = userSelectedFilename;
            if (userSelectedFilenameSuffix == "png") {
                imageQuality = 50;
            }
        } else {
            filename = userSelectedFilename + ".png";
            imageQuality = 50;
        }
    } else {
        QString selectedFormat(DEFAULT_FORMAT);
        if (getSnapshotFormat() != "") {
            selectedFormat = getSnapshotFormat();
        }
        filename = FILENAME_PATH_FORMAT.arg(username, now.toString(DATETIME_FORMAT)) + "." + selectedFormat;
        QFileInfo snapshotFileInfo(filename);
        QString filenameSuffix = snapshotFileInfo.suffix();
        filenameSuffix = filenameSuffix.toLower();
        if (filenameSuffix == "png") {
            imageQuality = 50;
        }
    }
    

    if (!isTemporary) {
        // If user has requested specific path then use it, else use the application value
        QString snapshotFullPath;
        if (!userSelectedPathname.isNull()) {
            snapshotFullPath = userSelectedPathname;
        } else {
            snapshotFullPath = getSnapshotsLocation();
        }

        if (nativeReviewEnabled()) {
            if (snapshotFullPath.isEmpty()) { snapshotFullPath = overte::snapshot::storageRoot(); }
            if (snapshotFullPath.isEmpty() || QFileInfo(snapshotFullPath).isSymLink() || !QDir().mkpath(snapshotFullPath)) { return nullptr; }
        }

        if (snapshotFullPath.isEmpty()) {
            snapshotFullPath =
                OffscreenUi::getExistingDirectory(nullptr, "Choose Snapshots Directory",
                                                  QStandardPaths::writableLocation(QStandardPaths::DesktopLocation));
            _snapshotsLocation.set(snapshotFullPath);
        }

        if (!snapshotFullPath.isEmpty()) {  // not cancelled

            if (!snapshotFullPath.endsWith(QDir::separator())) {
                snapshotFullPath.append(QDir::separator());
            }

            snapshotFullPath.append(filename);

            if (nativeReviewEnabled() && QFileInfo(snapshotFullPath).isSymLink()) { return nullptr; }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
            auto originalFileTicket=overte::e2e::PhoneSnapshotCaptureFiles::get().opening(snapshotFullPath,overte::snapshot::storageRoot());
#endif
            QFile* imageFile = new QFile(snapshotFullPath);
            while (!imageFile->open(QIODevice::WriteOnly)) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
                overte::e2e::PhoneSnapshotCaptureFiles::get().openFailed(originalFileTicket);
#endif
                delete imageFile;
                if (nativeReviewEnabled()) { return nullptr; }
                // It'd be better for the directory chooser to restore the cursor to its previous state
                // after choosing a directory, but if the user has entered this codepath,
                // something terrible has happened. Let's just show the user their cursor so they can get
                // out of this awful state.
                qApp->getApplicationCompositor().getReticleInterface()->setVisible(true);
                qApp->getApplicationCompositor().getReticleInterface()->setAllowMouseCapture(true);

                snapshotFullPath =
                    OffscreenUi::getExistingDirectory(nullptr, "Write Error - Choose New Snapshots Directory",
                                                      QStandardPaths::writableLocation(QStandardPaths::DesktopLocation));
                if (snapshotFullPath.isEmpty()) {
                    return NULL;
                }
                _snapshotsLocation.set(snapshotFullPath);

                if (!snapshotFullPath.endsWith(QDir::separator())) {
                    snapshotFullPath.append(QDir::separator());
                }
                snapshotFullPath.append(filename);

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
                originalFileTicket=overte::e2e::PhoneSnapshotCaptureFiles::get().opening(snapshotFullPath,overte::snapshot::storageRoot());
#endif
                imageFile = new QFile(snapshotFullPath);
            }

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
            overte::e2e::PhoneSnapshotCaptureFiles::get().opened(originalFileTicket,imageFile->handle());
#endif
            if (!shot.save(imageFile, nullptr, imageQuality)) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
                overte::e2e::PhoneSnapshotCaptureFiles::get().beforeClose(originalFileTicket,imageFile->handle());
#endif
                imageFile->close();
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
                overte::e2e::PhoneSnapshotCaptureFiles::get().closed(originalFileTicket,imageFile->isOpen());
                const bool actualRemoved=imageFile->remove();
                overte::e2e::PhoneSnapshotCaptureFiles::get().removed(originalFileTicket,actualRemoved);
#else
                imageFile->remove();
#endif
                delete imageFile; return nullptr;
            }
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
            overte::e2e::PhoneSnapshotCaptureFiles::get().beforeClose(originalFileTicket,imageFile->handle());
#endif
            imageFile->close();
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
            overte::e2e::PhoneSnapshotCaptureFiles::get().closed(originalFileTicket,imageFile->isOpen());
#endif

            return imageFile;
        }
    }
    // Either we were asked for a tempororary, or the user didn't set a directory.
    QTemporaryFile* imageTempFile = new QTemporaryFile(QDir::tempPath() + "/XXXXXX-" + filename);

    if (!imageTempFile->open()) {
        qDebug() << "Unable to open QTemporaryFile for temp snapshot. Will not save.";
        delete imageTempFile;
        return NULL;
    }
    imageTempFile->setAutoRemove(isTemporary);

    if (!shot.save(imageTempFile, nullptr, imageQuality)) {
        imageTempFile->close(); imageTempFile->remove(); delete imageTempFile; return nullptr;
    }
    imageTempFile->close();

    return imageTempFile;
}

void Snapshot::uploadSnapshot(const QString& filename, const QUrl& href) {
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, filename, href] { uploadSnapshot(filename, href); }, Qt::QueuedConnection);
        return;
    }
    if (_uploads.value(filename)) { emit uploadStatusChanged(filename, "error", "upload-busy"); return; }
    if (nativeReviewEnabled() && overte::snapshot::exportPath(filename).isEmpty()) {
        emit uploadStatusChanged(filename, "error", "invalid-snapshot-file");
        return;
    }
    const QString SNAPSHOT_UPLOAD_URL = "/api/v1/snapshots";
    QUrl url = href;
    if (url.isEmpty()) {
        SnapshotMetaData* snapshotData = parseSnapshotData(filename);
        if (snapshotData) {
            url = snapshotData->getURL();
        }
        delete snapshotData;
    }
    if (url.isEmpty()) {
        url = QUrl(DependencyManager::get<AddressManager>()->currentShareableAddress());
    }
    SnapshotUploader* uploader = new SnapshotUploader(url, filename);

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    QFile* file = new overte::e2e::PhoneSnapshotUploadFile(filename,uploader->featureUploadJob());
#else
    QFile* file = new QFile(filename);
#endif
    if (!file->open(QIODevice::ReadOnly) || file->size() <= 0) {
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
        overte::e2e::PhoneSnapshotUploadEvidence::get().change(uploader->featureUploadJob(),"terminal","error","file-unavailable");
#endif
        delete file; delete uploader;
        emit DependencyManager::get<WindowScriptingInterface>()->snapshotShared(true, "Snapshot file is unavailable");
        emit uploadStatusChanged(filename, "error", "file-unavailable");
        return;
    }

#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    overte::e2e::PhoneSnapshotUploadEvidence::get().file(uploader->featureUploadJob(),file);
#endif
    QHttpPart imagePart;
    const QString suffix = QFileInfo(filename).suffix().toLower();
    const QString mime = suffix == "gif" ? "image/gif" : suffix == "png" ? "image/png" : suffix == "webp" ? "image/webp" : "image/jpeg";
    imagePart.setHeader(QNetworkRequest::ContentTypeHeader, mime);
    imagePart.setHeader(QNetworkRequest::ContentDispositionHeader,
                        QVariant("form-data; name=\"image\"; filename=\"" + QFileInfo(*file).fileName().replace(QRegularExpression("[\"\\r\\n\\\\]"), "_") + "\""));
    imagePart.setBodyDevice(file);

    QHttpMultiPart* multiPart = new QHttpMultiPart(QHttpMultiPart::FormDataType);
    file->setParent(multiPart);  // we cannot delete the file now, so delete it with the multiPart
    multiPart->append(imagePart);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    overte::e2e::PhoneSnapshotUploadEvidence::get().multipart(uploader->featureUploadJob(),multiPart);
#endif

    auto accountManager = DependencyManager::get<AccountManager>();
    if (!_uploadContextConnected) {
        _uploadContextConnected = true;
        connect(accountManager.data(), &AccountManager::authEndpointChanged, this, &Snapshot::cancelUploads);
        connect(accountManager.data(), &AccountManager::logoutComplete, this, &Snapshot::cancelUploads);
        connect(accountManager.data(), &AccountManager::usernameChanged, this, &Snapshot::cancelUploads);
    }
    _uploads.insert(filename, uploader);
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    _featureSnapshotHistory->record("upload-begin",filename,{},filename);
#endif
    connect(uploader, &SnapshotUploader::finished, this, &Snapshot::uploadStatusChanged);
    connect(uploader, &QObject::destroyed, this, [this, filename] { if (!_uploads.value(filename)) { _uploads.remove(filename); } });
    JSONCallbackParameters callbackParams(uploader, "uploadSuccess", "uploadFailure");
    callbackParams.requestTicket = uploader->nextTicket();
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
    callbackParams.phoneSnapshotUploadJob=uploader->featureUploadJob();callbackParams.phoneSnapshotUploadStage="image";
#endif

    accountManager->sendRequest(SNAPSHOT_UPLOAD_URL, AccountManagerAuth::Required, QNetworkAccessManager::PostOperation,
                                callbackParams, nullptr, multiPart);
}

void Snapshot::cancelUpload(const QString& path) {
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(this, [this, path] { cancelUpload(path); }, Qt::QueuedConnection);
        return;
    }
    if (auto uploader = _uploads.value(path)) { uploader->cancel(); }
}

void Snapshot::cancelUploads() {
    const auto paths = _uploads.keys();
    for (const auto& path : paths) { cancelUpload(path); }
}

QString Snapshot::getSnapshotsLocation() {
    if (nativeReviewEnabled()) { return overte::snapshot::storageRoot(); }
    return _snapshotsLocation.get("");
}

void Snapshot::setSnapshotsLocation(const QString& location) {
    _snapshotsLocation.set(location);
}

QString Snapshot::getSnapshotFormat(){
    const auto available = getAvailableSnapshotFormats();
    const auto saved = _snapshotFormat.get();
    return available.contains(saved) ? saved : available.value(0);
}

void Snapshot::setSnapshotFormat(const QString& format){
    if (getAvailableSnapshotFormats().contains(format)) {
        _snapshotFormat.set(format);
    } else {
        qDebug() << "Snapshot format not supported: " << format;
    }
}

QString Snapshot::getAnimatedSnapshotFormat(){
    return _animatedSnapshotFormat.get();
}

void Snapshot::setAnimatedSnapshotFormat(const QString& format){
    if (getAvailableAnimatedSnapshotFormats().contains(format)) {
        _animatedSnapshotFormat.set(format);
    } else {
        qDebug() << "Snapshot format not supported: " << format;
    }
}

QStringList Snapshot::getAvailableSnapshotFormats() {
    const auto supported = QImageWriter::supportedImageFormats();
    QStringList available;
    for (const auto& format : {QStringLiteral("png"), QStringLiteral("jpg"), QStringLiteral("webp")}) {
        if (supported.contains(format.toLatin1())) {
            available.append(format);
        }
    }
    return available;
}

QStringList Snapshot::getAvailableSnapshotFormatsWithDescriptions() {
    QStringList descriptions;
    for (const auto& format : getAvailableSnapshotFormats()) {
        if (format == QStringLiteral("png")) {
            descriptions.append(QStringLiteral("PNG - lossless, large file size"));
        } else if (format == QStringLiteral("jpg")) {
            descriptions.append(QStringLiteral("JPG - lossy, fast compression"));
        } else if (format == QStringLiteral("webp")) {
            descriptions.append(QStringLiteral("WEBP - lossy, higher quality and file size than JPG"));
        }
    }
    return descriptions;
}

QStringList Snapshot::getAvailableAnimatedSnapshotFormats() {
    return QStringList({"gif"});
}

QStringList Snapshot::getAvailableAnimatedSnapshotFormatsWithDescriptions() {
    return QStringList({"GIF"});
}
