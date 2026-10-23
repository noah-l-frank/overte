// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Complete original bundle entry/validation/cancel/finish bodies below.
// Mapping-model knowledge and downstream server dispatch are explicit boundaries.
#include <QJSValue>
#include <QJsonArray>
#include <QFileInfo>
#include <QTimer>
#if !defined(ANDROID_APP_PICO_INTERFACE)
#define ANDROID_APP_PICO_INTERFACE
#define ASSETS_UPLOAD_LOCAL_PICO
#endif
#include "PicoAssetsUploadOriginals.h"
#include "assets-read-nodes-host.h"
#include "libraries/ui/src/FileDialogHelper.h"
class AssetMappingsScriptingInterface:public QObject {
 Q_OBJECT
public:
 Q_INVOKABLE QString uploadBundle(QStringList,QStringList,QString,QString,QJSValue,QJSValue);
 Q_INVOKABLE bool cancelUploadBundle(const QString&);
 bool isKnownMapping(const QString&)const{return false;}
 bool isKnownFolder(const QString&)const{return false;}
 QVariantMap featurePicoBundleOriginals(const QString& run);
 std::shared_ptr<overte::e2e::PicoAssetsUploadOriginals> _e2eBundles{std::make_shared<overte::e2e::PicoAssetsUploadOriginals>()};
 int backendDispatches{0};
private:
 struct BundleUpload;
 QHash<QString,std::shared_ptr<BundleUpload>> _bundleUploads;
 void finishBundle(const std::shared_ptr<BundleUpload>&,const QString&);
 void advanceBundle(const std::shared_ptr<BundleUpload>& state);
};

#if defined(ASSETS_UPLOAD_LOCAL_PICO)
#undef ANDROID_APP_PICO_INTERFACE
#undef ASSETS_UPLOAD_LOCAL_PICO
#endif
