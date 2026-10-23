// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
// Declared host service seams for the complete original NavigationUi::observe
// body. Avatar source/control/metadata, traversal, tokens and DTO are original.
// Other feature services are unavailable; this is not an Interface build.
#include <QSharedPointer>
#include <limits>
#include "tests/device/native/FeatureUiInventory.h"
#include "tests/device/native/PicoCreateFileControls.h"
#include "tests/device/native/NormalEmoteControls.h"
#include "tests/device/native/AudioPageObservation.h"
#include "tests/device/native/ViewMenuLifetimes.h"
#include "tests/device/native/SnapshotReviewObservation.h"
#include "tests/device/native/PicoSnapshotExportControls.h"
#include "android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.h"
class HostApplication:public QGuiApplication {
public:using QGuiApplication::QGuiApplication;bool isHMDMode()const{return true;}
};
#undef qApp
#define qApp static_cast<HostApplication*>(QCoreApplication::instance())
class AudioClient:public QObject {public:
    QVariantMap featureRecordedVoiceObservation()const{return {};}
    bool isMuted()const{return false;}bool getLocalEcho()const{return false;}
};
class AccountManager:public QObject {public:QVariantMap featureAccountObservation()const{return {};}};
class OffscreenUi:public QObject {public:QVariantMap featureCreateDialogIdentity(QQuickItem*)const{return {};}};
class RenderScriptingInterface {public:
    static RenderScriptingInterface* getInstance(){static RenderScriptingInterface value;return &value;}
    double getViewportResolutionScale()const{return std::numeric_limits<double>::quiet_NaN();}
    bool getHazeEnabled()const{return false;}bool getMirrorsEnabled()const{return false;}
};
#if defined(ASSETS_ORIGINAL_ENDPOINTS)
#include "assets-dependency-host.h"
#else
class DependencyManager {public:
    template<class T>static bool isSet(){return false;}
    template<class T>static QSharedPointer<T> get(){qFatal("Unavailable host dependency must not be instantiated");return {};}
};
#endif
namespace overte::e2e {
inline void ensureTabletHttpProvider(QQuickItem*){}
struct AccountMenuUiContext {
    LoginUiContext login;
    static AccountMenuUiContext fromNative(const QVariantMap&){return {};}
};
inline QString accountMenuControlId(QQuickItem*){return {};}
inline QString accountMenuSource(QQuickItem*,const QString&,const AccountMenuUiContext&){return {};}
inline void appendAccountMenuObservation(QJsonObject&,QQuickItem*,const QString&,const AccountMenuUiContext&){}
inline QString navigationLookupControlSource(QQuickItem*,const QString&){return {};}
inline QJsonObject navigationAddressObservation(QQuickItem*){return {};}
// Fixed Root d5ad48ed3f has the additive Browser app branch. It stays an
// unavailable unrelated service when this Avatar-only harness is integrated.
inline QString picoBrowserAppControlId(QQuickItem*){return {};}
inline QString picoBrowserAppControlSource(QQuickItem*,const QString&){return {};}
inline void appendPicoBrowserAppObservation(QJsonObject&,QQuickItem*,const QString&){}
struct ViewMenuContext {};
inline QString viewMenuControlId(QQuickItem*,const ViewMenuContext&){return {};}
inline QString viewMenuControlSource(QQuickItem*,const QString&,const ViewMenuContext&){return {};}
inline void appendViewMenuObservation(QJsonObject&,QQuickItem*,const QString&,const ViewMenuContext&){}
inline QString placesControlId(QQuickItem*){return {};}
inline QString placesControlSource(QQuickItem*,const QString&){return {};}
inline void appendPlacesObservation(QJsonObject&,QQuickItem*,const QString&){}
struct UnavailableNavigationFailure {
    template<class... Args>void observeRoot(Args&&...){}
    QString controlId(QQuickItem*)const{return {};}
    QString controlSource(QQuickItem*,const QString&)const{return {};}
    void appendControl(QJsonObject&,QQuickItem*,const QString&)const{}
};
inline UnavailableNavigationFailure& navigationFailureModals(){static UnavailableNavigationFailure value;return value;}
struct UnavailableNavigationPanels {void observe(QQuickItem*,QQuickWindow*,QJsonObject&)const{}};
inline UnavailableNavigationPanels navigationPanelsObservation(){return {};}
struct UnavailableNavigationEnvironment {void observe(QJsonObject&,QQuickItem*,QQuickItem*)const{}};
inline UnavailableNavigationEnvironment navigationEnvironmentObservation(){return {};}
struct UnavailableNavigationDirectory {std::function<void(QQuickItem*,QJsonObject&)> watch;};
inline UnavailableNavigationDirectory navigationDirectoryProvider(){return {};}
}
namespace overte::pico::e2e {
inline overte::e2e::ViewMenuContext viewMenuContext(){return {};}
}
