//
//  Created by Bradley Austin Davis on 2016/12/12
//  Copyright 2013-2016 High Fidelity, Inc.
//  Copyright 2023 Overte e.V.
//
//  Distributed under the Apache License, Version 2.0.
//  See the accompanying file LICENSE or http://www.apache.org/licenses/LICENSE-2.0.html
//  SPDX-License-Identifier: Apache-2.0
//

#pragma once
#ifndef hifi_TestScriptingInterface_h
#define hifi_TestScriptingInterface_h

#include <functional>
#include <QtCore/QObject>
#include <QtCore/QVariantMap>
#include <ScriptValue.h>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QSet>
#include <memory>
namespace overte::e2e { class ChatViewObservation; }
namespace overte::e2e { class ChatPeerPosition; }
#include <QUuid>
namespace overte::e2e { class FeatureLifecycle; class AccountOriginLease; }
#endif

class TestScriptingInterface : public QObject {
    Q_OBJECT

public:
    void setTestResultsLocation(const QString path);
    const QString& getTestResultsLocation() { return _testResultsLocation;  };

public slots:
    static TestScriptingInterface* getInstance();

    /*@jsdoc
     * Exits the application
     * @function Test.quit
     */
    void quit();

    /*@jsdoc
    * Waits for all texture transfers to be complete
    * @function Test.waitForTextureIdle
    */
    void waitForTextureIdle();

    /*@jsdoc
    * Waits for all pending downloads to be complete
    * @function Test.waitForDownloadIdle
    */
    void waitForDownloadIdle();

    /*@jsdoc
    * Waits for all file parsing operations to be complete
    * @function Test.waitForProcessingIdle
    */
    void waitForProcessingIdle();

    /*@jsdoc
    * Waits for all pending downloads, parsing and texture transfers to be complete
    * @function Test.waitIdle
    */
    void waitIdle();

    /*@jsdoc
    * Waits for establishment of connection to server
    * @function Test.waitForConnection
    * @param {int} maxWaitMs [default=10000] - Number of milliseconds to wait
    */
    bool waitForConnection(qint64 maxWaitMs = 10000);

    /*@jsdoc
    * Waits a specific number of milliseconds
    * @function Test.wait
    * @param {int} milliseconds - Number of milliseconds to wait
    */
    void wait(int milliseconds);

    /*@jsdoc
    * Waits for all pending downloads, parsing and texture transfers to be complete
    * @function Test.loadTestScene
    * @param {string} sceneFile - URL of scene to load
    */
    bool loadTestScene(QString sceneFile);

    /*@jsdoc
    * Clears all caches
    * @function Test.clear
    */
    void clear();

    /*@jsdoc
    * Start recording Chrome compatible tracing events
    * logRules can be used to specify a set of logging category rules to limit what gets captured
    * @function Test.startTracing
    * @param {string} logrules [defaultValue=""] - See implementation for explanation
    */
    bool startTracing(QString logrules = "");

    /*@jsdoc
    * Stop recording Chrome compatible tracing events and serialize recorded events to a file
    * Using a filename with a .gz extension will automatically compress the output file
    * @function Test.stopTracing
    * @param {string} filename - Name of file to save to
    * @returns {bool} True if successful.   
    */
    bool stopTracing(QString filename);

    /*@jsdoc
    * Starts a specific trace event
    * @function Test.startTraceEvent
    * @param {string} name - Name of event
    */
    void startTraceEvent(QString name);

    /*@jsdoc
    * Stop a specific name event
    * Using a filename with a .gz extension will automatically compress the output file
    * @function Test.endTraceEvent
    * @param {string} filename - Name of event
    */
    void endTraceEvent(QString name);

    /*@jsdoc
     * Write detailed timing stats of next physics stepSimulation() to filename
     * @function Test.savePhysicsSimulationStats
     * @param {string} filename - Name of file to save to
     */
    void savePhysicsSimulationStats(QString filename);

    /*@jsdoc
    * Profiles a specific function
    * @function Test.savePhysicsSimulationStats
    * @param {string} name - Name used to reference the function
    * @param {function} function - Function to profile
    */
    Q_INVOKABLE void profileRange(const QString& name, const ScriptValue& function);

    /*@jsdoc
    * Clear all caches (menu command Reload Content)
    * @function Test.clearCaches
    */
    void clearCaches();

    /*@jsdoc
    * Save a JSON object to a file in the test results location
    * @function Test.saveObject
    * @param {string} name - Name of the object
    * @param {string} filename - Name of file to save to
    */
    void saveObject(QVariant v, const QString& filename);
#if defined(OVERTE_E2E_FEATURE_TESTS)
    // Native E2E observations/fixture storage. Requires a dedicated build and
    // existing explicit --testScript/--testResultsLocation launch boundary.
    Q_INVOKABLE QVariantMap featureNativeObservation(const QString& requestId);
    Q_INVOKABLE QVariantMap featureChatObservation(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureChatViewObservation(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureChatPeerPosition(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureWebRuntimeObservation(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureWebDOMObservation(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureNavigationReplies(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureProcessPresence(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featurePendingCommitOwner(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureAccountProbe(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureAccountOrigin(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureRecordedVoiceEvidence(const QString& requestId);
    Q_INVOKABLE QVariantMap releaseFeatureRecordedVoiceEvidence(const QString& requestId);
    Q_INVOKABLE QVariantMap featureRecordedVoiceFiles(const QString& requestId);
    Q_INVOKABLE QVariantMap featureScriptObservation(const QString& requestId);
    Q_INVOKABLE QVariantMap featureScriptFiles(const QVariantMap& command);
#if defined(ANDROID_APP_PICO_INTERFACE)
    Q_INVOKABLE QVariantMap featureLocationBookmarks(const QVariantMap& command);
    void featurePlacesRecordsChanged();
    Q_INVOKABLE QVariantMap featureNavigationPanels(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureNavigationDirectory(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureNavigationEnvironment(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureNavigationModals(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureWorldRenderReceipts(const QVariantMap& command);
    Q_INVOKABLE void featureBindTabletHttpRequest(const QString& lease, QObject* request);
    Q_INVOKABLE QVariantMap featureTabletHttpObservation(const QVariantMap& command);
#endif
    Q_INVOKABLE QVariantMap featureSceneLoadObservation(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureGraphicsSubjectObservation(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureWorldRenderCapture(const QString& requestId);
    Q_INVOKABLE QVariantMap featureWorldRenderStorage(const QVariantMap& command);
    Q_INVOKABLE QVariantMap featureWorldRenderReceipt(const QVariantMap& command);
#endif
#if defined(OVERTE_E2E_VOICE_TESTS)
    Q_INVOKABLE QVariantMap voiceTest(const QVariantMap& command);
#endif

    /*@jsdoc
    * Maximizes the window
    * @function Test.showMaximized
    */
    void showMaximized();

    /*@jsdoc
    * Values higher than 0 will create replicas of other-avatars when entering a domain for testing purpouses
    * @function Test.setOtherAvatarsReplicaCount
    * @param {number} count - Number of replicas we want to create
    */
    Q_INVOKABLE void setOtherAvatarsReplicaCount(int count);

    /*@jsdoc
    * Return the number of replicas that are being created of other-avatars when entering a domain
    * @function Test.getOtherAvatarsReplicaCount
    * @returns {number} Current number of replicas of other-avatars.
    */
    Q_INVOKABLE int getOtherAvatarsReplicaCount();

    /*@jsdoc
     * Set number of cycles texture size is required to be stable
     * @function Test.setMinimumGPUTextureMemStabilityCount
    * @param {number} count - Number of cycles to wait
     */
    Q_INVOKABLE void setMinimumGPUTextureMemStabilityCount(int count);

    /*@jsdoc
     * Check whether all textures have been loaded.
     * @function Test.isTextureLoadingComplete
     * @returns {boolean} <code>true</code> texture memory usage is not increasing
     */
    Q_INVOKABLE bool isTextureLoadingComplete();

private:
    bool waitForCondition(qint64 maxWaitMs, std::function<bool()> condition);
    QString _testResultsLocation;
#if defined(OVERTE_E2E_FEATURE_TESTS)
    overte::e2e::FeatureLifecycle* _featureLifecycle {nullptr};
    overte::e2e::AccountOriginLease* _featureAccountOriginLease {nullptr};
    std::shared_ptr<overte::e2e::ChatViewObservation> _featureChatView;
    std::shared_ptr<overte::e2e::ChatPeerPosition> _featureChatPeerPosition;
    QString _featureObservationInstance;
    quint64 _featureObservationSequence {0};
    QString _featurePendingRequest;
    qint64 _featurePendingEpochMs {0};
    quint64 _featurePendingAnimationSequence {0};
    int _featurePendingRigId {-1};
    bool _featurePendingAnimationFence {false};
    QString _featureCompletedRequest;
    QVariantMap _featureCompletedObservation;
    QString _featurePreviewRequest;
    QVariantMap _featurePreviewObservation;
    QByteArray _featurePreviewInputDigest, _featurePreviewSinkDigest;
    quint64 _featurePreviewSequence {0}, _featurePreviewLease {0};
    quint64 _featureScriptSequence {0};
    QSet<QUuid> _featureScriptEffectIds;
    quint64 _featureScriptFilesSequence {0};
    quint64 _featureWorldReceiptSequence {0};
#if defined(ANDROID_APP_PICO_INTERFACE)
    quint64 _featureWorldReceiptsSequence {0};
    quint64 _featureLocationBookmarksSequence {0};
    QSet<QString> _featureLocationBookmarksRequests;
    QSet<QString> _featureWorldReceiptsRequests;
#endif
    quint64 _featureGraphicsSubjectSequence {0};
    QSet<QString> _featureGraphicsSubjectRequests;
    QSet<QString> _featureSceneLoadRequests;
    quint64 _featureProcessPresenceSequence {0};
    QVariantMap _featureScriptFilesCommand, _featureScriptFilesResult;
#endif
#if defined(OVERTE_E2E_VOICE_TESTS)
    QString _voiceCapturePath;
    quint64 _voiceCaptureGeneration { 0 };
#endif
};

#endif  // hifi_TestScriptingInterface_h
