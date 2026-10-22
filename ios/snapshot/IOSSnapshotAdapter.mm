// Copyright 2026 Overte e.V.
// SPDX-License-Identifier: Apache-2.0
#include "IOSSnapshotAdapter.h"
#include "SnapshotExportOperation.h"
#include "IOSSnapshotObservation.h"
#include "../../interface/src/ui/SnapshotStorage.h"
#include <QCoreApplication>
#include <QGuiApplication>
#include <QPointer>
#include <QThread>
#include <QUuid>
#include <QtQml/qqml.h>
#import <UIKit/UIKit.h>
#import <Photos/Photos.h>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QDateTime>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QMap>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#endif

namespace overte::ios {
struct IOSSnapshotNativeOperation {
    IOSSnapshotNativeOperation(QString ticket,QString path,QString action,IOSSnapshotAdapter* owner) :
        state(std::move(ticket),std::move(path),std::move(action)),owner(owner) {}
    SnapshotExportOperation state;
    QPointer<IOSSnapshotAdapter> owner;
    // Accessed only on the UIKit main actor; retain original app-owned files.
    __strong UIActivityViewController* sheet {nil};
};
namespace {
#if defined(OVERTE_E2E_FEATURE_TESTS)
struct ExportOriginals {
    struct Owner {std::weak_ptr<IOSSnapshotNativeOperation> operation;QString action,file;bool owned;};
    QMutex mutex;QElapsedTimer timer;QMap<QString,Owner> owners;QVariantList events;
    const QString instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    qint64 born{QDateTime::currentMSecsSinceEpoch()},last{born};bool complete{true};
    ExportOriginals() {timer.start();}
    static ExportOriginals& get() {static ExportOriginals value;return value;}
    static bool enabled() {return QCoreApplication::arguments().contains("--testScript");}
    QVariantMap clock() {
        const auto epoch=QDateTime::currentMSecsSinceEpoch();
        if (epoch<last || epoch<born) {complete=false;}last=epoch;
        return {{"epochMs",epoch},{"monotonicMs",timer.elapsed()}};
    }
    void add(const std::shared_ptr<IOSSnapshotNativeOperation>& operation) {
        if (!enabled()) {return;}QMutexLocker guard(&mutex);
        if (owners.contains(operation->state.ticket) || owners.size()>=64) {complete=false;return;}
        const auto name=QFileInfo(operation->state.path).fileName();
        const bool owned=QRegularExpression("\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,20}_[0-9]{1,10}\\.(png|jpg|jpeg|webp|gif)\\z").match(name).hasMatch();
        owners.insert(operation->state.ticket,{operation,operation->state.action,owned ? name : QString(),owned});
    }
    void event(const std::shared_ptr<IOSSnapshotNativeOperation>& operation,const QString& kind,const QVariantMap& detail={}) {
        if (!enabled()) {return;}QMutexLocker guard(&mutex);
        if (!owners.contains(operation->state.ticket) || events.size()>=2048) {complete=false;return;}
        auto original=detail;
        if (kind=="photos-placeholder" && !owners.value(operation->state.ticket).owned) {original["identifier"]=QString();}
        events.append(QVariantMap{{"sequence",events.size()+1},{"operation",operation->state.ticket},
            {"kind",kind},{"clock",clock()},{"detail",original}});
    }
};
void exportEvent(const std::shared_ptr<IOSSnapshotNativeOperation>& operation,const QString& kind,const QVariantMap& detail={}) {
    ExportOriginals::get().event(operation,kind,detail);
}
struct ExportCallback {
    std::shared_ptr<IOSSnapshotNativeOperation> operation;QString name;
    ExportCallback(const std::shared_ptr<IOSSnapshotNativeOperation>& value,const QString& callback):operation(value),name(callback) {
        exportEvent(operation,"callback-enter",{{"name",name}});
    }
    ~ExportCallback() {exportEvent(operation,"callback-returned",{{"name",name}});}
};
#else
#define exportEvent(...) ((void)0)
struct ExportCallback {ExportCallback(const std::shared_ptr<IOSSnapshotNativeOperation>&,const QString&) {}};
#endif
bool guiThread() { return qGuiApp && QThread::currentThread()==qGuiApp->thread(); }
NSString* string(const QString& value) { const auto bytes=value.toUtf8();return [[NSString alloc] initWithBytes:bytes.constData() length:bytes.size() encoding:NSUTF8StringEncoding]; }
UIViewController* presenter() {
    for(UIScene* scene in UIApplication.sharedApplication.connectedScenes) {
        if(scene.activationState!=UISceneActivationStateForegroundActive || ![scene isKindOfClass:UIWindowScene.class]) { continue; }
        for(UIWindow* window in ((UIWindowScene*)scene).windows) {
            if(!window.isKeyWindow || window.hidden) { continue; }
            UIViewController* controller=window.rootViewController;
            while(controller.presentedViewController && !controller.presentedViewController.isBeingDismissed) { controller=controller.presentedViewController; }
            if(controller.view.window && !controller.isBeingDismissed) { return controller; }
        }
    }
    return nil;
}
void deliver(const std::shared_ptr<IOSSnapshotNativeOperation>& operation,const QString& status,const QString& error={}) {
    if(!operation->state.finish()) { return; }
    exportEvent(operation,"delivery-enqueued",{{"status",status},{"hasError",!error.isEmpty()}});
    // Delivery and QPointer inspection execute in the Qt GUI owner, not a
    // Photos worker queue. A destroyed/replaced review cannot receive results.
    if(auto application=QCoreApplication::instance()) {
        QMetaObject::invokeMethod(application,[operation,status,error] {
            ExportCallback callback(operation,"qt-delivery");
            exportEvent(operation,"delivery-owner",{{"present",bool(operation->owner)}});
            if(operation->owner) { operation->owner->nativeFinished(operation,status,error); }
        },Qt::QueuedConnection);
    }
}
// Objective-C Blocks preserve reference capture types. Own the request and
// return payload by value before any delayed native callback captures them.
void dismissShare(std::shared_ptr<IOSSnapshotNativeOperation> operation,QString status,QString error={}) {
    auto sheet=operation->sheet;
    if(!sheet || !sheet.presentingViewController) { operation->sheet=nil;deliver(operation,status,error);return; }
    if(sheet.isBeingPresented && sheet.transitionCoordinator) {
        [sheet.transitionCoordinator animateAlongsideTransition:nil completion:^(id<UIViewControllerTransitionCoordinatorContext> context) {
            (void)context;
            dismissShare(operation,status,error);
        }];
        return;
    }
    [sheet dismissViewControllerAnimated:NO completion:^{
        ExportCallback callback(operation,"share-dismissed");
        operation->sheet=nil;
        deliver(operation,status,error);
    }];
}
void cancelNative(std::shared_ptr<IOSSnapshotNativeOperation> operation) {
    dispatch_async(dispatch_get_main_queue(),^{
        if(!operation->state.current()) { return; }
        const auto phase=operation->state.phase();
        if(phase==SnapshotExportOperation::Phase::Committed || phase==SnapshotExportOperation::Phase::Authorizing) {
            // A visible permission prompt cannot be dismissed by the app. Wait
            // for its real return; after Photos commitment await the real save.
            return;
        }
        dismissShare(operation,"cancelled");
    });
}
void saveToPhotos(std::shared_ptr<IOSSnapshotNativeOperation> operation) {
    if(!operation->state.advance(SnapshotExportOperation::Phase::Authorizing)) { deliver(operation,"cancelled");return; }
    exportEvent(operation,"photos-authorization-requested");
    [PHPhotoLibrary requestAuthorizationForAccessLevel:PHAccessLevelAddOnly handler:^(PHAuthorizationStatus status) {
        ExportCallback callback(operation,"photos-authorization");
        exportEvent(operation,"photos-authorization",{{"status",int(status)}});
        exportEvent(operation,"main-enqueued",{{"name","photos-authorized-main"}});
        dispatch_async(dispatch_get_main_queue(),^{
            ExportCallback callback(operation,"photos-authorized-main");
            if(!operation->state.current()) { return; }
            if(operation->state.cancelled()) { deliver(operation,"cancelled");return; }
            if(status!=PHAuthorizationStatusAuthorized && status!=PHAuthorizationStatusLimited) {
                deliver(operation,"error",IOSSnapshotAdapter::tr("Permission to save snapshots to Photos was denied."));return;
            }
            const auto validated=overte::snapshot::exportPath(operation->state.path);
            if(validated.isEmpty() || validated!=operation->state.path) {
                deliver(operation,"error",IOSSnapshotAdapter::tr("The snapshot file is no longer available."));return;
            }
            NSURL* file=[NSURL fileURLWithPath:string(validated)];
            if(!operation->state.advance(SnapshotExportOperation::Phase::Committed)) { deliver(operation,"cancelled");return; }
            exportEvent(operation,"photos-commit-enqueued");
            [[PHPhotoLibrary sharedPhotoLibrary] performChanges:^{
                ExportCallback callback(operation,"photos-changes");
                PHAssetCreationRequest* asset=[PHAssetCreationRequest creationRequestForAsset];
                PHAssetResourceCreationOptions* options=[[PHAssetResourceCreationOptions alloc] init];
                options.shouldMoveFile=NO;
                [asset addResourceWithType:PHAssetResourceTypePhoto fileURL:file options:options];
                // The placeholder is an original native creation identity,
                // not proof that Photos committed or retained these bytes.
                exportEvent(operation,"photos-placeholder",{{"identifier",QString::fromUtf8(asset.placeholderForCreatedAsset.localIdentifier.UTF8String ?: "")}});
            } completionHandler:^(BOOL success,NSError* error) {
                ExportCallback callback(operation,"photos-completion");
                exportEvent(operation,"photos-completed",{{"success",bool(success)},{"hasError",error!=nil}});
                // Preserve the actual Photos result even if Cancel/background
                // arrives after commitment. No fabricated rollback receipt.
                deliver(operation,success ? "success" : "error",success ? QString() : IOSSnapshotAdapter::tr("Photos could not save this snapshot."));
                (void)error;
            }];
        });
    }];
}
void shareWithSystem(std::shared_ptr<IOSSnapshotNativeOperation> operation) {
    if(!operation->state.advance(SnapshotExportOperation::Phase::Choosing)) { deliver(operation,"cancelled");return; }
    auto controller=presenter();
    if(!controller) { deliver(operation,"error",IOSSnapshotAdapter::tr("Open the snapshot review in the foreground to share."));return; }
    const auto validated=overte::snapshot::exportPath(operation->state.path);
    if(validated.isEmpty() || validated!=operation->state.path) { deliver(operation,"error",IOSSnapshotAdapter::tr("The snapshot file is no longer available."));return; }
    // NSURL preserves full-resolution still, panorama/cubemap and animated GIF
    // bytes. UIImage conversion would silently discard GIF animation.
    UIActivityViewController* sheet=[[UIActivityViewController alloc] initWithActivityItems:@[[NSURL fileURLWithPath:string(validated)]] applicationActivities:nil];
    operation->sheet=sheet;
    exportEvent(operation,"share-created");
    sheet.completionWithItemsHandler=^(UIActivityType activityType,BOOL completed,NSArray* returnedItems,NSError* error) {
        ExportCallback callback(operation,"share-completion");
        exportEvent(operation,"share-completed",{{"completed",bool(completed)},{"hasError",error!=nil}});
        (void)activityType;(void)returnedItems;
        dispatch_async(dispatch_get_main_queue(),^{
            dismissShare(operation,error ? "error" : completed ? "success" : "cancelled",error ? IOSSnapshotAdapter::tr("The selected sharing service failed.") : QString());
        });
    };
    sheet.popoverPresentationController.sourceView=controller.view;
    sheet.popoverPresentationController.sourceRect=CGRectMake(CGRectGetMidX(controller.view.bounds),CGRectGetMidY(controller.view.bounds),1,1);
    sheet.popoverPresentationController.permittedArrowDirections=0;
    [controller presentViewController:sheet animated:YES completion:nil];
    exportEvent(operation,"share-presentation-requested");
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW,2*NSEC_PER_SEC),dispatch_get_main_queue(),^{
        if(operation->state.current() && operation->state.phase()==SnapshotExportOperation::Phase::Choosing &&
                !sheet.presentingViewController && !sheet.isBeingPresented) {
            operation->sheet=nil;
            deliver(operation,"error",IOSSnapshotAdapter::tr("The system sharing window could not open."));
        }
    });
}
} // namespace
IOSSnapshotAdapter::IOSSnapshotAdapter(QObject* parent) : QObject(parent) {
    connect(qGuiApp,&QGuiApplication::applicationStateChanged,this,[this](Qt::ApplicationState state) {
        // The application's own Photos authorization prompt is inactive, not
        // background. Keep it alive until the user's real answer arrives.
        if(state==Qt::ApplicationHidden || state==Qt::ApplicationSuspended) {
            if(_operation) { cancel(_operation->state.ticket); }
        }
    });
}
IOSSnapshotAdapter::~IOSSnapshotAdapter() {
    if(_operation) { _operation->state.cancel();cancelNative(_operation); }
}
QString IOSSnapshotAdapter::request(const QString& canonicalPath,const QString& action) {
    if(!guiThread() || _operation || !capabilities().contains(action)) {
        _error=tr("A system snapshot request is already active or cannot start here.");emit changed();return {};
    }
    const auto validated=overte::snapshot::exportPath(canonicalPath);
    if(validated.isEmpty()) { _error=tr("Choose an existing snapshot saved by this app.");emit changed();return {}; }
    const auto ticket=QUuid::createUuid().toString(QUuid::WithoutBraces);
    auto operation=std::make_shared<IOSSnapshotNativeOperation>(ticket,validated,action,this);
#if defined(OVERTE_E2E_FEATURE_TESTS)
    ExportOriginals::get().add(operation);
#endif
    exportEvent(operation,"created");
    _operation=operation;_error.clear();emit changed();
    dispatch_async(dispatch_get_main_queue(),^{
        if(!operation->state.current() || operation->state.cancelled()) { deliver(operation,"cancelled");return; }
        if(!presenter()) { deliver(operation,"error",IOSSnapshotAdapter::tr("Open the snapshot review in the foreground."));return; }
        if(operation->state.action=="save") { saveToPhotos(operation); } else { shareWithSystem(operation); }
    });
    return ticket;
}
void IOSSnapshotAdapter::cancel(const QString& ticket) {
    if(!guiThread() || !_operation || _operation->state.ticket!=ticket) { return; }
    exportEvent(_operation,"cancel-requested");_operation->state.cancel();cancelNative(_operation);
}
void IOSSnapshotAdapter::nativeFinished(const std::shared_ptr<IOSSnapshotNativeOperation>& operation,const QString& status,const QString& error) {
    if(!guiThread() || _operation!=operation) { return; }
    const auto ticket=operation->state.ticket;
    exportEvent(operation,"qt-completed",{{"status",status},{"hasError",!error.isEmpty()}});
    _operation.reset();_error=error;emit changed();emit completed(ticket,status,error);
}
} // namespace overte::ios
#if defined(OVERTE_E2E_FEATURE_TESTS)
namespace overte::ios {
bool featureSnapshotQtInputBlocked() {
    if (!ExportOriginals::enabled() || !NSThread.isMainThread || !guiThread()
            || UIApplication.sharedApplication.applicationState!=UIApplicationStateActive) {return true;}
    const auto controller=presenter();
    // UIKit sheets and ordinary native pickers receive actual system input.
    // Sending a Qt event beneath their visible controller would bypass it.
    return !controller || controller.presentingViewController!=nil || controller.isBeingPresented || controller.isBeingDismissed;
}

QVariantMap featureSnapshotExportObservation() {
    if (!ExportOriginals::enabled() || !NSThread.isMainThread || !guiThread()) {return {};}
    auto& original=ExportOriginals::get();QMutexLocker guard(&original.mutex);QVariantList owners;
    for (auto it=original.owners.cbegin();it!=original.owners.cend();++it) {
        const auto operation=it->operation.lock();
        QVariantMap row{{"id",it.key()},{"action",it->action},{"fileName",it->file},{"owned",it->owned},{"alive",bool(operation)}};
        if (operation) {
            auto sheet=operation->sheet;
            const auto state=operation->state.featureObservedState();
            row["state"]=QVariantMap{{"current",state!=0},{"cancelled",bool(state&8U)},
                {"phase",int(state&~8U)},{"ownerAlive",bool(operation->owner)},
                {"sheetPresent",sheet!=nil},{"sheetPresenting",sheet && sheet.isBeingPresented},
                {"sheetDismissing",sheet && sheet.isBeingDismissed},{"sheetAttached",sheet && sheet.presentingViewController!=nil}};
        } else {row["state"]=QVariantMap{};}
        owners.append(row);
    }
    const auto sample=original.clock();
    return {{"iosSnapshotExportsSourceVersion",1},{"instance",original.instance},{"bornEpochMs",original.born},
        {"complete",original.complete},{"clock",sample},{"authorization",int([PHPhotoLibrary authorizationStatusForAccessLevel:PHAccessLevelAddOnly])},
        {"operations",owners},{"events",original.events}};
}
}
#endif
namespace {
void registerIOSSnapshotAdapter() { qmlRegisterType<overte::ios::IOSSnapshotAdapter>("Overte.iOS",1,0,"IOSSnapshotAdapter"); }
Q_COREAPP_STARTUP_FUNCTION(registerIOSSnapshotAdapter)
}
