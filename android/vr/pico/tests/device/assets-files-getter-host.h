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
    QString _testResultsLocation,_featureObservationInstance{QString(32,'e')};
    std::shared_ptr<AssetsHostLifecycle> _featureLifecycle;
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureAssetsFilesQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    std::shared_ptr<PrivateAssetsFiles> _featureAssetsFiles{std::make_shared<PrivateAssetsFiles>()};
    quint64 _featureAssetsFilesSequence{0};QHash<QString,QVariantMap> _featureAssetsFilesCommands,_featureAssetsFilesResults;
};
#include "AssetsFilesMethod.inc"
