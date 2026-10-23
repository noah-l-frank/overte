// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PrivateAssetsFiles.h"
#include "AudioSettingsQueue.h"
#include <QDateTime>
#include <QHash>
using overte::e2e::PrivateAssetsFiles;
struct AssetsHostLifecycle {QVariantMap snapshot() const {return {{"present",true}};}};
class TestScriptingInterface:public QObject {
public:
    QVariantMap featurePicoAssetsFiles(const QVariantMap& command);
#if defined(ASSETS_ORIGINAL_ENDPOINTS)
    QVariantMap featurePicoAssetsUploadsObservation(const QVariantMap& command);
    QVariantMap featurePicoAssetsRead(const QVariantMap& command,bool abort=false);
    QVariantMap featurePicoAssetsReadRetire(const QVariantMap& command);
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureAssetsReadQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    std::shared_ptr<overte::e2e::PicoAssetsReadJob> _featureAssetsRead{std::make_shared<overte::e2e::PicoAssetsReadJob>()};
    quint64 _featureAssetsReadRetireSequence{0},_featureAssetsReadSequence{0};
    QHash<QString,QVariantMap> _featureAssetsReadRetireCommands,_featureAssetsReadRetireResults;
    QHash<QString,qint64> _featureAssetsReadRetireRequested;
    QPointer<QObject> _featureAssetsClientObject,_featureAssetsNodesObject,_featureAssetsServerObject;
    QString _featureAssetsClientBirth,_featureAssetsNodesBirth,_featureAssetsServerBirth;
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureAssetsUploadsQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    QPointer<QObject> _featureAssetsUploadsManager;quint64 _featureAssetsUploadsSequence{0};
    QHash<QString,QVariantMap> _featureAssetsUploadsCommands,_featureAssetsUploadsResults;
#endif
    QString _testResultsLocation,_featureObservationInstance{QString(32,'e')};
    std::shared_ptr<AssetsHostLifecycle> _featureLifecycle;
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureAssetsFilesQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    std::shared_ptr<PrivateAssetsFiles> _featureAssetsFiles{std::make_shared<PrivateAssetsFiles>()};
    quint64 _featureAssetsFilesSequence{0};QHash<QString,QVariantMap> _featureAssetsFilesCommands,_featureAssetsFilesResults;
};
#include "AssetsFilesMethod.inc"

#if defined(ASSETS_ORIGINAL_ENDPOINTS)
#include "AssetsUploadsMethod.inc"
#include "AssetsReadMethod.inc"
#endif
