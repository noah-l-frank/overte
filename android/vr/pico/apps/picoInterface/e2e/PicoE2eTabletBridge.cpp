// SPDX-License-Identifier: Apache-2.0

#include "PicoE2eTabletBridge.h"
#include "PicoE2eNavigationUi.h"
#include "PicoGraphicsComposition.h"
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "../../../../../../tests/device/native/PendingFieldCommitOwner.h"
#include "../../../../../../tests/device/native/PicoBrowserInputBridge.h"
#include "../../../../../../tests/device/native/PicoWorldWebRay.h"
#include "../../../../../../tests/device/native/LifecycleUiObservation.h"
#include "../../../../../../tests/device/native/LifecycleBackgroundHistory.h"
#include "../../../../../../tests/device/native/AssetsPageObservation.h"
#include <PathUtils.h>
#include "../../../../../../tests/device/native/PrivatePreviewFiles.h"
#include "../../../../../../tests/device/native/PicoSnapshotFastCancel.h"
#include "../../../../../../tests/device/native/PicoSnapshotCancelBridge.h"
#include <scripting/TestScriptingInterface.h>
#include "../../../../../../tests/device/native/LoginUiInventory.h"
#include <AccountManager.h>
#include <scripting/RenderScriptingInterface.h>
#include <Application.h>
#include <ui/Keyboard.h>
#include <EntityScriptingInterface.h>
#include <avatar/AvatarManager.h>
#include <scripting/HMDScriptingInterface.h>
#include <QElapsedTimer>
#include <QInputMethodEvent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QUuid>
#endif

#include <algorithm>
#include <cmath>
#include <functional>

#include <QDateTime>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQuickItem>
#include <QQuickWindow>
#include <QRectF>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <QTimer>
#include <QTouchDevice>

#include <DependencyManager.h>
#include <PointerEvent.h>
#include <shared/GlobalAppProperties.h>
#include <ui/OffscreenQmlSurface.h>
#include <ui/TabletScriptingInterface.h>

namespace overte::pico::e2e {
namespace {

const QString SYSTEM_TABLET { QStringLiteral("com.highfidelity.interface.tablet.system") };
const QString BRIDGE_DIRECTORY { QStringLiteral("/data/user/0/org.overte.pico/files/overte-e2e") };
const QString OBSERVATION_PATH { BRIDGE_DIRECTORY + QStringLiteral("/tablet-ui-observation.json") };
const QString DIAGNOSTIC_PATH { BRIDGE_DIRECTORY + QStringLiteral("/tablet-ui-diagnostic.json") };
const QString COMMAND_PATH { BRIDGE_DIRECTORY + QStringLiteral("/tablet-ui-command.json") };
const QString STATUS_PATH { BRIDGE_DIRECTORY + QStringLiteral("/tablet-ui-status.json") };
const QString PROBE_PATH {
    QStringLiteral("/data/user/0/org.overte.pico/files/overte-e2e/overte_e2e_probe.js")
};

const QSet<QString> SCREEN_IDS {
    QStringLiteral("settings.audio"),
    QStringLiteral("settings.controllers"),
    QStringLiteral("settings.general"),
    QStringLiteral("settings.graphics"),
    QStringLiteral("settings.home"),
    QStringLiteral("settings.security"),
    QStringLiteral("tablet.home"),
};

const QSet<QString> CONTROL_IDS {
    QStringLiteral("app.settings"),
    QStringLiteral("nav.back"),
    QStringLiteral("nav.close"),
    QStringLiteral("nav.home"),
    QStringLiteral("settings.audio"),
    QStringLiteral("settings.controllers"),
    QStringLiteral("settings.general"),
    QStringLiteral("settings.graphics"),
    QStringLiteral("settings.hmd-preferences"),
    QStringLiteral("settings.security"),
    QStringLiteral("settings.vr-render-resolution"),
};

bool bridgeEnabled() {
    const QUrl testScript = qApp->property(hifi::properties::TEST).toUrl();
    if (!testScript.isLocalFile()) {
        return false;
    }
    const QString activeProbe = QFileInfo(testScript.toLocalFile()).canonicalFilePath();
    const QString expectedProbe = QFileInfo(PROBE_PATH).canonicalFilePath();
    return !activeProbe.isEmpty() && !expectedProbe.isEmpty()
        && activeProbe == expectedProbe;
}

bool effectiveVisible(const QQuickItem* item) {
    if (!item || !item->isVisible() || item->opacity() <= 0.01
            || item->width() <= 0.0 || item->height() <= 0.0 || !item->window()) {
        return false;
    }
    QRectF visibleRect = item->mapRectToScene(item->boundingRect());
    visibleRect = visibleRect.intersected(
        QRectF(QPointF(0.0, 0.0), QSizeF(item->window()->size())));
    for (auto parent = item->parentItem(); parent; parent = parent->parentItem()) {
        if (!parent->isVisible() || parent->opacity() <= 0.01) {
            return false;
        }
        if (parent->clip()) {
            visibleRect = visibleRect.intersected(
                parent->mapRectToScene(parent->boundingRect()));
        }
    }
    return !visibleRect.isEmpty();
}

void walkItems(QQuickItem* item, const std::function<void(QQuickItem*, int)>& visitor,
               int depth = 0) {
    if (!item) {
        return;
    }
    visitor(item, depth);
    const auto children = item->childItems();
    for (auto child : children) {
        walkItems(child, visitor, depth + 1);
    }
}

bool writeJson(const QString& path, const QJsonObject& value) {
    QSaveFile output(path);
    output.setDirectWriteFallback(false);
    if (!output.open(QIODevice::WriteOnly)
            || !output.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner)) {
        return false;
    }
    const auto bytes = QJsonDocument(value).toJson(QJsonDocument::Compact);
    if (output.write(bytes) != bytes.size()
            || output.write("\n") != 1) {
        output.cancelWriting();
        return false;
    }
    return output.commit();
}

struct Observation {
    QJsonObject snapshot;
    QHash<QString, QQuickItem*> controls;
};

Observation observeTablet() {
    Observation result;
    QString screenId { QStringLiteral("tablet.home") };
    int screenDepth { -1 };
    bool semanticScreenFound { false };
    QSet<QString> visibleControls;

    auto tabletInterface = DependencyManager::get<TabletScriptingInterface>();
    auto tablet = tabletInterface ? tabletInterface->getTablet(SYSTEM_TABLET) : nullptr;
    auto root = tablet ? tablet->getTabletRoot() : nullptr;
    const bool open = tablet && tablet->property("tabletShown").toBool();
    int itemCount { 0 };
    int visibleItemCount { 0 };

    walkItems(root, [&](QQuickItem* item, int depth) {
        ++itemCount;
        if (!effectiveVisible(item)) {
            return;
        }
        ++visibleItemCount;
        // Entry controls intentionally share IDs with their destination screens.
        // An explicit screen property must therefore outrank deeper objectName fallbacks.
        const QString semanticCandidate = item->property("semanticScreenId").toString();
        if (SCREEN_IDS.contains(semanticCandidate)) {
            if (!semanticScreenFound || depth >= screenDepth) {
                screenId = semanticCandidate;
                screenDepth = depth;
            }
            semanticScreenFound = true;
        } else if (!semanticScreenFound) {
            const QString fallbackCandidate = item->objectName();
            if (SCREEN_IDS.contains(fallbackCandidate) && depth >= screenDepth) {
                screenId = fallbackCandidate;
                screenDepth = depth;
            }
        }

        // A shared touch control may need a platform accessibility objectName
        // while exposing the portable tablet contract separately. Prefer the
        // explicit semanticId and retain objectName as the legacy fallback.
        const QString explicitControlId = item->property("semanticId").toString();
        const QString controlId = CONTROL_IDS.contains(explicitControlId)
            ? explicitControlId : item->objectName();
        if (CONTROL_IDS.contains(controlId)) {
            visibleControls.insert(controlId);
            if (item->isEnabled() && !result.controls.contains(controlId)) {
                result.controls.insert(controlId, item);
            }
        }
    });

    QStringList sortedControls = visibleControls.values();
    std::sort(sortedControls.begin(), sortedControls.end());
    QJsonArray controls;
    for (const auto& control : sortedControls) {
        controls.append(control);
    }
    result.snapshot = {
        { QStringLiteral("contractVersion"), 1 },
        { QStringLiteral("schemaVersion"), 1 },
        { QStringLiteral("screenId"), screenId },
        { QStringLiteral("ready"), open && root && screenDepth >= 0 },
        { QStringLiteral("visibleControlIds"), controls },
    };
    // Preserve actual scene-graph geometry when semantic discovery fails.
    // This diagnostic is independent of the portable acceptance snapshot.
    writeJson(DIAGNOSTIC_PATH, {
        { QStringLiteral("updatedEpochMs"), static_cast<double>(QDateTime::currentMSecsSinceEpoch()) },
        { QStringLiteral("tabletAvailable"), bool(tablet) },
        { QStringLiteral("open"), open },
        { QStringLiteral("rootAvailable"), bool(root) },
        { QStringLiteral("rootObjectName"), root ? root->objectName() : QString() },
        { QStringLiteral("rootWidth"), root ? root->width() : 0.0 },
        { QStringLiteral("rootHeight"), root ? root->height() : 0.0 },
        { QStringLiteral("rootVisible"), root && root->isVisible() },
        { QStringLiteral("windowAvailable"), root && root->window() },
        { QStringLiteral("windowWidth"), root && root->window() ? root->window()->width() : 0 },
        { QStringLiteral("windowHeight"), root && root->window() ? root->window()->height() : 0 },
        { QStringLiteral("itemCount"), itemCount },
        { QStringLiteral("visibleItemCount"), visibleItemCount },
        { QStringLiteral("screenDepth"), screenDepth },
    });
    return result;
}

bool exactKeys(const QJsonObject& object, const QSet<QString>& expected) {
    QSet<QString> actual;
    for (const auto& key : object.keys()) {
        actual.insert(key);
    }
    return actual == expected;
}

void writeStatus(const QString& commandId, bool performed, const QString& error) {
    writeJson(STATUS_PATH, {
        { QStringLiteral("schemaVersion"), 1 },
        { QStringLiteral("commandId"), commandId },
        { QStringLiteral("performed"), performed },
        { QStringLiteral("error"), error.left(120) },
        { QStringLiteral("updatedEpochMs"),
          static_cast<double>(QDateTime::currentMSecsSinceEpoch()) },
    });
}

QTouchDevice& bridgeTouchDevice() {
    static QTouchDevice device;
    static const bool configured = [] {
        device.setCapabilities(QTouchDevice::Position);
        device.setType(QTouchDevice::TouchScreen);
        device.setName(QStringLiteral("PicoE2eTabletPointer"));
        device.setMaximumTouchPoints(1);
        return true;
    }();
    Q_UNUSED(configured)
    return device;
}

bool sendPointerAt(QQuickItem* item, OffscreenQmlSurface* surface, const QPointF& position) {
    auto window = surface ? surface->getWindow() : nullptr;
    if (!effectiveVisible(item) || !item->isEnabled() || !surface || !window
            || item->window() != window) {
        return false;
    }
    if (!item->contains(item->mapFromScene(position))) { return false; }
    if (!std::isfinite(position.x()) || !std::isfinite(position.y())
            || position.x() < 0.0 || position.y() < 0.0
            || position.x() >= window->width() || position.y() >= window->height()) {
        return false;
    }
    // A partially clipped item can have an invisible center. Never send its
    // pointer into a different control outside the actual clipping ancestors.
    for (auto parent = item->parentItem(); parent; parent = parent->parentItem()) {
        if (parent->clip() && !parent->clipRect().contains(parent->mapFromScene(position))) {
            return false;
        }
    }
    constexpr uint32_t POINTER_ID { 0xE2E00001u };
    const glm::vec2 pointerPosition {
        static_cast<float>(position.x()), static_cast<float>(position.y())
    };
    PointerEvent move(PointerEvent::Move, POINTER_ID, pointerPosition,
                      PointerEvent::NoButtons, PointerEvent::NoButtons,
                      Qt::NoModifier);
    PointerEvent press(PointerEvent::Press, POINTER_ID, pointerPosition,
                       PointerEvent::PrimaryButton, PointerEvent::PrimaryButton,
                       Qt::NoModifier);
    PointerEvent release(PointerEvent::Release, POINTER_ID, pointerPosition,
                         PointerEvent::PrimaryButton, PointerEvent::NoButtons,
                         Qt::NoModifier);
    auto& touchDevice = bridgeTouchDevice();
    surface->hoverBeginEvent(move, touchDevice);
    const bool pressAccepted = surface->handlePointerEvent(press, touchDevice);
    const bool releaseAccepted = surface->handlePointerEvent(release, touchDevice);
    surface->hoverEndEvent(move, touchDevice);
    return pressAccepted && releaseAccepted;
}

bool sendPointerClick(QQuickItem* item, OffscreenQmlSurface* surface) {
    return item && sendPointerAt(item, surface, item->mapToScene(QPointF(item->width()/2, item->height()/2)));
}

#if defined(OVERTE_E2E_FEATURE_TESTS)
bool sendPointerScroll(QQuickItem* item, OffscreenQmlSurface* surface, const QPointF& position, int delta) {
    auto window=surface ? surface->getWindow() : nullptr;
    if (!effectiveVisible(item) || !item->isEnabled() || !surface || !window || item->window()!=window
            || (delta!=120 && delta!=-120) || !item->contains(item->mapFromScene(position))
            || !std::isfinite(position.x()) || !std::isfinite(position.y())
            || position.x()<0 || position.y()<0 || position.x()>=window->width() || position.y()>=window->height()) { return false; }
    for (auto parent=item->parentItem();parent;parent=parent->parentItem()) {
        if (parent->clip() && !parent->clipRect().contains(parent->mapFromScene(position))) { return false; }
    }
    constexpr uint32_t POINTER_ID { 0xE2E00001u };
    const glm::vec2 point{static_cast<float>(position.x()),static_cast<float>(position.y())};
    PointerEvent move(PointerEvent::Move,POINTER_ID,point,PointerEvent::NoButtons,PointerEvent::NoButtons,Qt::NoModifier);
    PointerEvent scroll(PointerEvent::Scroll,POINTER_ID,point,PointerEvent::NoButtons,PointerEvent::NoButtons,Qt::NoModifier);
    scroll.setScroll(glm::vec2(0.0f,static_cast<float>(delta)/POINTEREVENT_SCROLL_SENSITIVITY));
    // The original surface combines mouse/touch/wheel acceptance. An ignored
    // auxiliary touch event is not proof that the real wheel was not delivered.
    // Observe actual delivery without consuming the event or claiming movement.
    struct WheelDelivery : QObject {
        bool seen{false};
        bool eventFilter(QObject*,QEvent* event) override { if (event->type()==QEvent::Wheel) { seen=true; } return false; }
    } delivery;
    window->installEventFilter(&delivery);
    auto& device=bridgeTouchDevice();surface->hoverBeginEvent(move,device);
    surface->handlePointerEvent(scroll,device);
    surface->hoverEndEvent(move,device);window->removeEventFilter(&delivery);
    return delivery.seen;
}
#endif

#if defined(OVERTE_E2E_FEATURE_TESTS)
QUrl lifecycleScriptSource(const QString& relative) {
    auto base=PathUtils::defaultScriptsLocation();
    if (!base.path().endsWith('/')) { base.setPath(base.path()+'/'); }
    return base.resolved(QUrl(relative));
}

void installBrowserInputProvider() {
    using namespace overte::e2e;
    if (!qApp || QThread::currentThread()!=qApp->thread() || !bridgeEnabled()
            || !previewDirectory(BRIDGE_DIRECTORY) || qApp->property(picoBrowserInputProperty()).isValid()) { return; }
    const auto admitted=[](QQuickItem* item) {
        if (!bridgeEnabled() || !previewDirectory(BRIDGE_DIRECTORY) || !item || !effectiveVisible(item)
                || QGuiApplication::applicationState()!=Qt::ApplicationActive
                || !DependencyManager::isSet<TabletScriptingInterface>()) { return false; }
        const auto tablet=DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        auto root=tablet ? tablet->getTabletRoot() : nullptr;auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        auto window=surface ? surface->getWindow() : nullptr;
        if (!tablet || !tablet->property("tabletShown").toBool() || !root || !window || root->window()!=window
                || item->window()!=window || item->thread()!=qApp->thread() || root->thread()!=qApp->thread()
                || window->thread()!=qApp->thread()) { return false; }
        int depth=0;for (auto parent=item;parent && depth++<128;parent=parent->parentItem()) { if (parent==root) { return true; } }
        return false;
    };
    PicoBrowserInputProvider provider;
    provider.pointer=[admitted](QQuickItem* item,const QPointF& local,qint64 originalEpoch) {
        if (!admitted(item)) { return false; }const auto scene=item->mapToScene(local);
        if (!NormalControlUi::ownsPoint(item,item->window(),scene)) { return false; }
        const auto tablet=DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        const auto now=QDateTime::currentMSecsSinceEpoch();
        return surface && surface->getWindow()==item->window() && originalEpoch>0 && now>=originalEpoch && now-originalEpoch<=1500
            && sendPointerAt(item,surface,scene);
    };
    provider.scroll=[admitted](QQuickItem* item,const QPointF& local,int delta,qint64 originalEpoch) {
        if (!admitted(item) || (delta!=120 && delta!=-120)) { return false; }
        const auto scene=item->mapToScene(local);
        if (!NormalControlUi::ownsPoint(item,item->window(),scene)) { return false; }
        const auto tablet=DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        const auto now=QDateTime::currentMSecsSinceEpoch();
        return surface && surface->getWindow()==item->window() && originalEpoch>0 && now>=originalEpoch && now-originalEpoch<=1500
            && sendPointerScroll(item,surface,scene,delta);
    };
    provider.text=[admitted](QQuickItem* item,const QString& text,qint64 originalEpoch) {
        if (!admitted(item) || item->window()->activeFocusItem()!=item || text.size()>512) { return false; }
        for (int i=0;i<text.size();++i) {
            const auto c=text.at(i);
            if (c.unicode()<32 || c.unicode()==127 || c.isLowSurrogate()) { return false; }
            if (c.isHighSurrogate() && (++i>=text.size() || !text.at(i).isLowSurrogate())) { return false; }
        }
        const auto old=item->inputMethodQuery(Qt::ImSurroundingText);
        bool cursorOkay=false,anchorOkay=false;
        const auto cursor=item->inputMethodQuery(Qt::ImCursorPosition).toInt(&cursorOkay),
            anchor=item->inputMethodQuery(Qt::ImAnchorPosition).toInt(&anchorOkay);
        if (!item->inputMethodQuery(Qt::ImEnabled).toBool() || old.userType()!=QMetaType::QString || old.toString().size()>512
                || !cursorOkay || !anchorOkay || cursor<0 || anchor<0 || cursor>old.toString().size() || anchor>old.toString().size()
                || item->inputMethodQuery(Qt::ImAbsolutePosition).toInt()!=cursor
                || (item->inputMethodQuery(Qt::ImHints).toInt() & (Qt::ImhHiddenText | Qt::ImhSensitiveData))) { return false; }
        // Native WebView editor updates arrive asynchronously. The normal IME
        // replacement describes the actual whole surrounding range; a delivery
        // ACK cannot stand in for subsequent independent DOM/model observation.
        QInputMethodEvent commit;
        commit.setCommitString(text,-std::min(cursor,anchor),old.toString().size()-std::abs(cursor-anchor));
        const auto now=QDateTime::currentMSecsSinceEpoch();
        return originalEpoch>0 && now>=originalEpoch && now-originalEpoch<=1500 && QCoreApplication::sendEvent(item->window(),&commit);
    };
    qApp->setProperty(picoBrowserInputProperty(),QVariant::fromValue(provider));
}

void installWorldWebRayProvider() {
    using namespace overte::e2e;
    if (!qApp || QThread::currentThread()!=qApp->thread() || !bridgeEnabled()
            || !previewDirectory(BRIDGE_DIRECTORY) || qApp->property(picoWorldWebRayProperty()).isValid()) { return; }
    PicoWorldWebRayProvider provider=[](QQuickItem* item,const QPointF& local) -> QVariantMap {
        if (!bridgeEnabled() || !previewDirectory(BRIDGE_DIRECTORY) || !item || !effectiveVisible(item)
                || item->thread()!=qApp->thread() || !item->window() || item->window()->thread()!=qApp->thread()
                || !qApp->isHMDMode() || QGuiApplication::applicationState()!=Qt::ApplicationActive
                || !DependencyManager::isSet<EntityScriptingInterface>()
                || !DependencyManager::isSet<HMDScriptingInterface>() || !DependencyManager::isSet<AvatarManager>()) { return {}; }
        const auto identity=item->property("sourceIdentity").toString();
        if (!identity.startsWith("web-entity:")) { return {}; }
        const QUuid id(identity.mid(11));
        auto* context=QQmlEngine::contextForObject(item);
        if (id.isNull() || identity!="web-entity:"+id.toString(QUuid::WithoutBraces)
                || !context || !context->isValid() || context->contextProperty("nativeWebSourceIdentity").toString()!=identity) { return {}; }
        const auto properties=DependencyManager::get<EntityScriptingInterface>()->getEntityProperties(id);
        if (properties.getType()!=EntityTypes::Web || properties.getEntityHostType()!=entity::HostType::LOCAL
                || properties.getName()!=QStringLiteral("OVERTE_PARITY_WEB_REFERENCE") || !properties.getParentID().isNull()
                || !properties.getVisible() || properties.getIgnorePickIntersection()
                || properties.getSourceUrl()!=item->property("url").toString()) { return {}; }
        const auto dimensions=properties.getDimensions();const auto registration=properties.getRegistrationPoint();
        const auto dpi=properties.getDpi();
        if (!std::isfinite(dpi) || dpi<1 || dpi>1024
                || glm::any(glm::lessThanEqual(dimensions,glm::vec3(0)))
                || !std::isfinite(dimensions.x) || !std::isfinite(dimensions.y) || !std::isfinite(dimensions.z)
                || registration!=glm::vec3(.5f)) { return {}; }
        // Match the actual renderer's window-size cap and RayPick's XY-plane
        // mapping. Parent-scaled/noncentral geometry remains unavailable until
        // its existing product projection can be independently qualified.
        constexpr float pixelsPerInchMeter=39.3701f;
        const float factor=pixelsPerInchMeter*dpi;
        glm::vec2 rendered=glm::vec2(dimensions)*factor;
        const auto longest=std::max(rendered.x,rendered.y);
        if (longest>4096) { rendered*=4096/longest; }
        const auto scene=item->mapToScene(local);auto* window=item->window();
        if (window->width()!=int(rendered.x) || window->height()!=int(rendered.y)
                || !std::isfinite(scene.x()) || !std::isfinite(scene.y()) || scene.x()<0 || scene.y()<0
                || scene.x()>=window->width() || scene.y()>=window->height()
                || !item->contains(local) || !NormalControlUi::ownsPoint(item,window,scene)) { return {}; }
        const auto rotation=properties.getRotation();const auto position=properties.getPosition();
        if (!std::isfinite(position.x) || !std::isfinite(position.y) || !std::isfinite(position.z)
                || !std::isfinite(rotation.x) || !std::isfinite(rotation.y) || !std::isfinite(rotation.z)
                || !std::isfinite(rotation.w) || std::abs(glm::dot(rotation,rotation)-1.f)>1e-5f) { return {}; }
        const auto point=position+rotation*glm::vec3(float(scene.x())/factor-registration.x*dimensions.x,
            (1-registration.y)*dimensions.y-float(scene.y())/factor,0);
        const auto avatar=DependencyManager::get<AvatarManager>()->getMyAvatar();
        const auto hmd=DependencyManager::get<HMDScriptingInterface>();
        if (!avatar || !hmd->isHMDMode()) { return {}; }
        const auto vec=[](const glm::vec3& value){return QVariantList{value.x,value.y,value.z};};
        const auto point2=[](const QPointF& value){return QVariantList{value.x(),value.y()};};
        const QVariantList quad{point2(item->mapToScene(QPointF(0,0))),point2(item->mapToScene(QPointF(item->width(),0))),
            point2(item->mapToScene(QPointF(item->width(),item->height()))),point2(item->mapToScene(QPointF(0,item->height())))};
        QVariantList matrix;const auto sensor=avatar->getSensorToWorldMatrix();
        for (int column=0;column<4;++column) { for (int row=0;row<4;++row) { matrix.append(sensor[column][row]); } }
        return {{"worldWebRayVersion",1},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"sourceIdentity",identity},{"entityId",id.toString(QUuid::WithoutBraces)},
            {"entityName",properties.getName()},{"entityType",QStringLiteral("Web")},{"hostType",QStringLiteral("local")},
            {"sourceUrl",properties.getSourceUrl()},{"visible",properties.getVisible()},
            {"ignorePickIntersection",properties.getIgnorePickIntersection()},
            {"position",vec(position)},{"rotation",QVariantList{rotation.x,rotation.y,rotation.z,rotation.w}},
            {"dimensions",vec(dimensions)},{"registrationPoint",vec(registration)},{"dpi",dpi},
            {"scenePoint",QVariantList{scene.x(),scene.y()}},{"itemQuad",quad},{"surfaceSize",QVariantList{window->width(),window->height()}},
            {"worldPoint",vec(point)},{"sensorToWorld",matrix},{"headPosition",vec(hmd->getPosition())}};
    };
    qApp->setProperty(picoWorldWebRayProperty(),QVariant::fromValue(provider));
}

void installPendingCommitOwner() {
    using namespace overte::e2e;
    if (!qApp || QThread::currentThread() != qApp->thread() || !bridgeEnabled()
            || !previewDirectory(BRIDGE_DIRECTORY) || qApp->property(pendingCommitProviderProperty()).isValid()) { return; }
    const auto roots = [] {
        PendingFieldCommitOwner::Roots result;
        if (!bridgeEnabled() || QGuiApplication::applicationState() != Qt::ApplicationActive
                || !DependencyManager::isSet<TabletScriptingInterface>()) { return result; }
        const auto tablet = DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        auto root = tablet ? tablet->getTabletRoot() : nullptr;
        auto surface = tablet ? tablet->getTabletSurface() : nullptr;
        auto window = surface ? surface->getWindow() : nullptr;
        if (!tablet || !tablet->property("tabletShown").toBool() || !root || !window || root->window() != window
                || root->thread() != qApp->thread() || window->thread() != qApp->thread()) { return result; }
        result.available = true; result.items.append(root); return result;
    };
    const auto pointer = [roots](QQuickItem* item, QQuickWindow* window, const QPointF& point) {
        if (!roots().available || !NormalControlUi::ownsPoint(item, window, point)) { return false; }
        const auto tablet = DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        auto surface = tablet ? tablet->getTabletSurface() : nullptr;
        return surface && surface->getWindow() == window && sendPointerAt(item, surface, point);
    };
    const auto owner = std::make_shared<PendingFieldCommitOwner>(roots, pointer);
    PendingCommitProvider provider = [owner](const QVariantMap& command) {
        if (!qApp || QThread::currentThread() != qApp->thread() || !bridgeEnabled()
                || !previewDirectory(BRIDGE_DIRECTORY)) { return QVariantMap(); }
        return owner->request(command);
    };
    qApp->setProperty(pendingCommitProviderProperty(), QVariant::fromValue(provider));
}
#endif

class TabletBridge : public QObject {
public:
    explicit TabletBridge(QObject* owner) : QObject(owner) {
        connect(&_timer, &QTimer::timeout, this, [this] { tick(); });
        _timer.start(100);
#if defined(OVERTE_E2E_FEATURE_TESTS)
        _homeClock.start();
#endif
    }

private:
    void tick() {
        if (!bridgeEnabled()) {
            return;
        }
#if defined(OVERTE_E2E_FEATURE_TESTS)
        installPendingCommitOwner();
        installBrowserInputProvider();
        installWorldWebRayProvider();
        installSnapshotCancelProvider();
#endif
        const Observation observation = observeTablet();
        writeJson(OBSERVATION_PATH, {
            { QStringLiteral("bridgeVersion"), 1 },
            { QStringLiteral("updatedEpochMs"),
              static_cast<double>(QDateTime::currentMSecsSinceEpoch()) },
            { QStringLiteral("snapshot"), observation.snapshot },
        });
        applyCommand(observation);
        navigationTick();
#if defined(OVERTE_E2E_FEATURE_TESTS)
        lifecycleObservationTick();
        lifecycleBackgroundTick();
        scriptObservationTick();
        loginObservationTick();
        graphicsObservationTick();
        homeObservationTick();
        assetsPageObservationTick();
        snapshotCancelTick();
#endif
    }

#if defined(OVERTE_E2E_FEATURE_TESTS)
    struct SnapshotCancelRoots {
        QPointer<QQuickItem> root;QPointer<QQuickWindow> window;QPointer<OffscreenQmlSurface> surface;bool shown{false};
    };
    SnapshotCancelRoots snapshotCancelRoots() {
        if(!bridgeEnabled() || !overte::e2e::previewDirectory(BRIDGE_DIRECTORY) || !qApp->isHMDMode()
                || QThread::currentThread()!=qApp->thread() || QGuiApplication::applicationState()!=Qt::ApplicationActive
                || !DependencyManager::isSet<TabletScriptingInterface>()) {return {};}
        const auto tablet=DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        auto root=tablet ? tablet->getTabletRoot() : nullptr;auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        auto window=surface ? surface->getWindow() : nullptr;
        if(!root || !window || root->window()!=window || root->thread()!=qApp->thread() || window->thread()!=qApp->thread()) {return {};}
        return {root,window,surface,tablet->property("tabletShown").toBool()};
    }
    QVariantMap snapshotCancelRequest(const QVariantMap& command,const QVariantMap& closedWork) {
        using namespace overte::e2e;
        if(!picoSnapshotCancelCommand(command)) {return {};}
        const auto roots=snapshotCancelRoots();if(!roots.root || !roots.window) {return {};}
        const auto job=command.value("jobId").toString(),run=command.value("runId").toString(),operation=command.value("operation").toString();
        auto owner=_snapshotCancelJobs.value(job);
        if(!owner) {
            if(operation!="start" || _snapshotCancelJobs.size()>=8) {return {};}
            owner=std::make_shared<PicoSnapshotFastCancel>();
            _snapshotCancelJobs.insert(job,owner); // Retain before input, even if later read/serialization fails.
        }
        QPointer<TabletBridge> guarded(this);
        const auto ui=std::make_shared<PicoSnapshotCancelInput>();
        ui->observe=[guarded](QQuickItem* root,QQuickWindow* window) -> QJsonObject {
            if(!guarded) {return {};}
            const auto actual=guarded->snapshotCancelRoots();
            return actual.root==root && actual.window==window ? guarded->_navigation.observe(root,window,actual.shown) : QJsonObject{};
        };
        ui->apply=[guarded](QQuickItem* root,QQuickWindow* window,const QJsonObject& input,const PicoSnapshotCancelInput::Click& click) -> QJsonObject {
            if(!guarded) {return {};}
            const auto actual=guarded->snapshotCancelRoots();
            return actual.root==root && actual.window==window ? guarded->_navigation.apply(root,window,actual.shown,input,click) : QJsonObject{};
        };
        const auto read=[guarded,run]() -> QVariantMap {
            if(!guarded || !guarded->snapshotCancelRoots().root) {return {};}
            auto native=[](const QString& action,const QString& run) {
                return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
                    {"runId",run},{"action",action}};
            };
            auto capture=native("feature-snapshot-capture-originals",run);capture.insert("operation","read");
            const auto original=TestScriptingInterface::getInstance();
            return {{"native",original->featureSnapshotCaptureOriginals(capture)},
                {"script",original->featureSnapshotScriptOriginals(native("feature-snapshot-script-originals",run))}};
        };
        const auto click=[guarded](QQuickItem* item) {
            if(!guarded) {return false;}
            const auto actual=guarded->snapshotCancelRoots();
            return actual.shown && actual.surface && item && item->window()==actual.window && sendPointerClick(item,actual.surface);
        };
        const auto source=owner->request(run,job,operation,QJsonObject::fromVariantMap(command.value("request").toMap()),
            roots.root,roots.window,ui,read,click,closedWork);
        if(source.isEmpty()) {return {};}
        QVariantList jobs;for(const auto& owned:_snapshotCancelJobs) {jobs.append(owned->summary());}
        return {{"source",source},{"jobs",jobs}};
    }
    void snapshotCancelTick() {
        using namespace overte::e2e;
        if(!previewDirectory(BRIDGE_DIRECTORY)) {return;}
        const QString path=BRIDGE_DIRECTORY+"/snapshot-cancel-ui-command.json";const QFileInfo info(path);
        QFile input(path);
        if(!info.isFile() || info.isSymLink() || info.permissions() & (QFile::ReadGroup|QFile::WriteGroup|QFile::ExeGroup
                |QFile::ReadOther|QFile::WriteOther|QFile::ExeOther) || !input.open(QIODevice::ReadOnly) || input.size()>24*1024) {return;}
        QJsonParseError error;const auto json=QJsonDocument::fromJson(input.readAll(),&error);
        if(error.error!=QJsonParseError::NoError || !json.isObject() || !picoSnapshotCancelCommand(json.object().toVariantMap())) {return;}
        const auto id=json.object().value("commandId").toString();if(_lastSnapshotCancelCommand==id) {return;}
        _lastSnapshotCancelCommand=id;
        const auto original=TestScriptingInterface::getInstance()->featurePicoSnapshotCancel(json.object().toVariantMap());
        writeJson(BRIDGE_DIRECTORY+"/snapshot-cancel-ui-status.json",{{"commandId",id},{"packet",QJsonObject::fromVariantMap(original)}});
    }
    void installSnapshotCancelProvider() {
        using namespace overte::e2e;
        if(!bridgeEnabled() || !previewDirectory(BRIDGE_DIRECTORY) || qApp->property(picoSnapshotCancelProperty()).isValid()) {return;}
        QPointer<TabletBridge> guarded(this);
        PicoSnapshotCancelProvider provider=[guarded](const QVariantMap& command,const QVariantMap& work) {
            return guarded ? guarded->snapshotCancelRequest(command,work) : QVariantMap{};
        };
        qApp->setProperty(picoSnapshotCancelProperty(),QVariant::fromValue(provider));
    }

    // Passive actual world geometry. The command accepts only a fresh nonce;
    // no entity, pose, Home message, tablet mutation or click is supplied here.
    void homeObservationTick() {
        const QString path=BRIDGE_DIRECTORY+"/tablet-home-observation-command.json";
        QFile input(path);
        if (QFileInfo(path).isSymLink() || !input.open(QIODevice::ReadOnly) || input.size()>4096) { return; }
        QJsonParseError error;const auto document=QJsonDocument::fromJson(input.readAll(),&error);
        if (error.error!=QJsonParseError::NoError || !document.isObject()) { return; }
        const auto command=document.object();const auto id=command.value("commandId").toString();
        if (!exactKeys(command,{"schemaVersion","commandId","action"})
                || command.value("schemaVersion")!=QJsonValue(1) || command.value("action")!=QJsonValue(QStringLiteral("observe"))
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || _homeNonces.contains(id) || _homeNonces.size()>=4096) { return; }
        _homeNonces.insert(id);
        if (QThread::currentThread()!=qApp->thread()
                || !DependencyManager::isSet<HMDScriptingInterface>()
                || !DependencyManager::isSet<EntityScriptingInterface>()
                || !DependencyManager::isSet<AvatarManager>()) { return; }
        const auto hmd=DependencyManager::get<HMDScriptingInterface>();
        const auto entities=DependencyManager::get<EntityScriptingInterface>();
        const auto avatar=DependencyManager::get<AvatarManager>()->getMyAvatar();
        const auto tablet=DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        const auto homeId=hmd->getCurrentHomeButtonID();const auto tabletId=hmd->getCurrentTabletFrameID();
        if (!hmd->isHMDMode() || !tablet || !avatar || homeId.isNull() || tabletId.isNull()) { return; }
        const auto original=entities->getEntityProperties(homeId);
        if (original.getType()!=EntityTypes::Gizmo || original.getName()!=QStringLiteral("homeButton")
                || original.getParentID()!=tabletId || original.getEntityHostType()!=entity::HostType::LOCAL) { return; }
        const auto vector=[](const glm::vec3& value) { return QJsonArray{value.x,value.y,value.z}; };
        const auto uuid=[](const QUuid& value) { return value.toString(QUuid::WithoutBraces).remove('-'); };
        QJsonArray matrix;const auto sensor=avatar->getSensorToWorldMatrix();
        for (int column=0;column<4;++column) { for (int row=0;row<4;++row) { matrix.append(sensor[column][row]); } }
        writeJson(BRIDGE_DIRECTORY+"/tablet-home-observation.json",{
            {"schemaVersion",1},{"commandId",id},{"action",QStringLiteral("observe")},
            {"instance",_homeInstance},{"generation",_homeInstance},
            {"sourceSequence",static_cast<double>(++_homeSequence)},{"lastCommandSequence",0},
            {"elapsedMs",static_cast<double>(_homeClock.elapsed())},
            {"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},
            {"homeObservationVersion",1},{"tabletShown",tablet->property("tabletShown").toBool()},
            {"onHomeScreen",tablet->onHomeScreen()},{"tabletId",uuid(tabletId)},
            {"homeId",uuid(homeId)},{"parentId",uuid(original.getParentID())},
            {"entityType",QStringLiteral("Gizmo")},{"entityName",original.getName()},
            {"hostType",QStringLiteral("local")},{"visible",original.getVisible()},
            {"ignorePickIntersection",original.getIgnorePickIntersection()},
            {"sensorToWorld",matrix},{"headPosition",vector(hmd->getPosition())},{"position",vector(original.getPosition())}
        });
    }

    // Original generic VR controls and retained roots. This channel has no
    // input action; ordinary input stays in NavigationUi/OpenXR.
    void graphicsObservationTick() {
        const QString path=BRIDGE_DIRECTORY+"/graphics-ui-command.json";
        QFile input(path);
        if (QFileInfo(path).isSymLink() || !input.open(QIODevice::ReadOnly) || input.size()>4096) { return; }
        QJsonParseError error;const auto document=QJsonDocument::fromJson(input.readAll(),&error);
        if (error.error!=QJsonParseError::NoError || !document.isObject()) { return; }
        const auto command=document.object();const auto id=command.value("commandId").toString();
        if (!exactKeys(command,{"schemaVersion","commandId","action"})
                || command.value("schemaVersion")!=QJsonValue(1) || command.value("action")!=QJsonValue(QStringLiteral("observe"))
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || _graphicsObservationNonces.contains(id) || _graphicsObservationNonces.size()>=4096) { return; }
        _graphicsObservationNonces.insert(id);
        if (QThread::currentThread()!=qApp->thread() || !DependencyManager::isSet<Keyboard>()) { return; }
        const auto render=RenderScriptingInterface::getInstance();
        const auto context=overte::e2e::GraphicsUiContext::fromNative(render->getViewportResolutionScale(),
            render->getHazeEnabled(),render->getMirrorsEnabled());
        const auto tablet=DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        const auto root=tablet ? tablet->getTabletRoot() : nullptr;
        const auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        const auto window=surface ? surface->getWindow() : nullptr;
        auto packet=_graphicsObservation.observe(root,window,{},context);
        if (packet.isEmpty()) { return; }
        auto inventory=_graphicsInventory.observe(root,window);
        inventory["qmlLoads"]=surface ? QJsonObject::fromVariantMap(surface->featureQmlLoadObservation()) : QJsonObject();
        const auto keyboard=DependencyManager::get<Keyboard>();
        inventory["keyboard3D"]=QJsonObject{{"raised",keyboard->isRaised()},{"enabled",keyboard->getUse3DKeyboard()}};
        packet["commandId"]=id;packet["action"]=QStringLiteral("observe");
        packet["graphicsObservationVersion"]=2;packet["graphicsInventory"]=inventory;
        packet["composition"]=_graphicsComposition.observe(root,window,
            DependencyManager::isSet<EntityScriptingInterface>() ? DependencyManager::get<EntityScriptingInterface>().data() : nullptr,
            DependencyManager::isSet<HMDScriptingInterface>() ? DependencyManager::get<HMDScriptingInterface>().data() : nullptr);
        packet["tabletShown"]=tablet && tablet->property("tabletShown").toBool();
        auto focused=window ? window->activeFocusItem() : nullptr;
        packet["editorFocused"]=focused && (focused->inherits("QQuickTextInput") || focused->inherits("QQuickTextEdit"))
            && focused->hasActiveFocus();
        packet["capturedEpochMs"]=static_cast<double>(QDateTime::currentMSecsSinceEpoch());
        writeJson(BRIDGE_DIRECTORY+"/graphics-ui.json",packet);
    }

    // Separate passive source for both publisher roles. No input command,
    // credentials, AccountManager mutation or tablet-open fallback is accepted.
    void loginObservationTick() {
        const QString path=BRIDGE_DIRECTORY+"/login-ui-command.json";
        QFile input(path);
        if (QFileInfo(path).isSymLink() || !input.open(QIODevice::ReadOnly) || input.size()>4096) { return; }
        QJsonParseError error;
        const auto document=QJsonDocument::fromJson(input.readAll(),&error);
        if (error.error!=QJsonParseError::NoError || !document.isObject()) { return; }
        const auto command=document.object();const auto id=command.value("commandId").toString();
        if (!exactKeys(command,{"schemaVersion","commandId","action"})
                || command.value("schemaVersion")!=QJsonValue(1) || command.value("action")!=QJsonValue(QStringLiteral("observe"))
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || _loginObservationNonces.contains(id) || _loginObservationNonces.size()>=4096) { return; }
        _loginObservationNonces.insert(id); // Retain uncertainty; never recapture/retime a nonce.
        overte::e2e::LoginUiContext context;
        if (DependencyManager::isSet<AccountManager>()) {
            const auto account=DependencyManager::get<AccountManager>();QVariantMap original;
            const auto read=[&] { original=account->featureAccountObservation(); };
            const bool okay=QThread::currentThread()==account->thread()
                ? (read(),true) : QMetaObject::invokeMethod(account.data(),read,Qt::BlockingQueuedConnection);
            if (okay) { context=overte::e2e::LoginUiContext::fromNative(original); }
        }
        auto tablets=DependencyManager::get<TabletScriptingInterface>();
        auto tablet=tablets ? tablets->getTablet(SYSTEM_TABLET) : nullptr;
        auto root=tablet ? tablet->getTabletRoot() : nullptr;
        auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        auto packet=_loginObservation.observe(root,surface ? surface->getWindow() : nullptr,{},{},context);
        if (packet.isEmpty()) { return; }
        packet["commandId"]=id;packet["action"]=QStringLiteral("observe");
        packet["loginObservationVersion"]=1;packet["startupDialogPresent"]=qApp->getLoginDialogPoppedUp();
        auto inventory=_loginInventory.observe(root,surface ? surface->getWindow() : nullptr);
        inventory["qmlLoads"]=surface ? QJsonObject::fromVariantMap(surface->featureQmlLoadObservation()) : QJsonObject();
        if (!DependencyManager::isSet<Keyboard>()) { return; }
        const auto keyboard=DependencyManager::get<Keyboard>();
        inventory["keyboard3D"]=QJsonObject{{"raised",keyboard->isRaised()},{"enabled",keyboard->getUse3DKeyboard()}};
        packet["loginInventory"]=inventory;
        packet["capturedEpochMs"]=static_cast<double>(QDateTime::currentMSecsSinceEpoch());
        writeJson(BRIDGE_DIRECTORY+"/login-ui.json",packet);
    }

    // Original editor/context identities and physical VR keyboard owners.
    // No input, requested generation or UI-property mutation exists here.
    void assetsPageObservationTick() {
        const QString path=BRIDGE_DIRECTORY+"/assets-pages-command.json";
        QFile input(path);
        if(QFileInfo(path).isSymLink() || !input.open(QIODevice::ReadOnly) || input.size()>4096) {return;}
        QJsonParseError error;const auto document=QJsonDocument::fromJson(input.readAll(),&error);
        if(error.error!=QJsonParseError::NoError || !document.isObject()) {return;}
        const auto command=document.object();const auto id=command.value("commandId").toString();
        if(!exactKeys(command,{"schemaVersion","commandId","action"}) || command.value("schemaVersion")!=QJsonValue(1)
                || command.value("action")!=QJsonValue(QStringLiteral("observe"))
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || _assetsPageNonces.contains(id) || _assetsPageNonces.size()>=4096) {return;}
        _assetsPageNonces.insert(id);
        if(QThread::currentThread()!=qApp->thread() || !DependencyManager::isSet<TabletScriptingInterface>()) {return;}
        const auto tablet=DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        const auto root=tablet ? tablet->getTabletRoot() : nullptr;
        const auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        const auto window=surface ? surface->getWindow() : nullptr;
        if(!tablet || !surface) {return;}
        auto packet=_assetsPages.observe(root,window,tablet->property("tabletShown").toBool(),tablet->onHomeScreen(),surface->featureQmlLoadObservation());
        if(packet.isEmpty()) {return;}
        packet["commandId"]=id;packet["action"]=QStringLiteral("observe");
        writeJson(BRIDGE_DIRECTORY+"/assets-pages.json",packet);
    }

    void lifecycleObservationTick() {
        const QString path=BRIDGE_DIRECTORY+"/lifecycle-ui-command.json";
        QFile input(path);
        if (QFileInfo(path).isSymLink() || !input.open(QIODevice::ReadOnly) || input.size()>4096) { return; }
        QJsonParseError error;const auto document=QJsonDocument::fromJson(input.readAll(),&error);
        if (error.error!=QJsonParseError::NoError || !document.isObject()) { return; }
        const auto command=document.object();const auto id=command.value("commandId").toString();
        const auto run=command.value("runId").toString();
        if (!exactKeys(command,{"schemaVersion","commandId","action","runId"})
                || command.value("schemaVersion")!=QJsonValue(1) || command.value("action")!=QJsonValue("observe")
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(run).hasMatch()
                || _lifecycleObservationNonces.contains(id) || _lifecycleObservationNonces.size()>=4096
                || QThread::currentThread()!=qApp->thread() || !qApp->isHMDMode()
                || !DependencyManager::isSet<Keyboard>() || !DependencyManager::isSet<TabletScriptingInterface>()) { return; }
        _lifecycleObservationNonces.insert(id); // Failed writes cannot retime an original nonce.
        auto packet=lifecycleCurrent(run);
        if (packet.isEmpty()) { return; }
        packet["commandId"]=id;
        writeJson(BRIDGE_DIRECTORY+"/lifecycle-ui-observation.json",QJsonObject::fromVariantMap(packet));
    }

    QVariantMap lifecycleCurrent(const QString& run) {
        if (!bridgeEnabled() || !overte::e2e::previewDirectory(BRIDGE_DIRECTORY) || QThread::currentThread()!=qApp->thread()
                || !qApp->isHMDMode() || !DependencyManager::isSet<Keyboard>()
                || !DependencyManager::isSet<TabletScriptingInterface>()) { return {}; }
        const auto tablet=DependencyManager::get<TabletScriptingInterface>()->getTablet(SYSTEM_TABLET);
        const auto root=tablet ? tablet->getTabletRoot() : nullptr;
        const auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        const auto window=surface ? surface->getWindow() : nullptr;
        const auto keyboard=DependencyManager::get<Keyboard>()->featureChatObservation();
        return _lifecycleObservation.observe(root,window,tablet && tablet->property("tabletShown").toBool(),
            tablet && tablet->onHomeScreen(),run,keyboard);
    }

    void lifecycleBackgroundTick() {
        if (!overte::e2e::previewDirectory(BRIDGE_DIRECTORY)) { return; }
        const QString path=BRIDGE_DIRECTORY+"/lifecycle-background-command.json";const QFileInfo info(path);
        QFile input(path);
        if (!info.isFile() || info.isSymLink() || info.permissions() & (QFile::ReadGroup|QFile::WriteGroup|QFile::ExeGroup
                |QFile::ReadOther|QFile::WriteOther|QFile::ExeOther) || !input.open(QIODevice::ReadOnly) || input.size()>4096) { return; }
        QJsonParseError error;const auto document=QJsonDocument::fromJson(input.readAll(),&error);
        if (error.error!=QJsonParseError::NoError || !document.isObject()) { return; }
        const auto value=_lifecycleBackground.request(document.object().toVariantMap());
        if (!value.isEmpty()) { writeJson(BRIDGE_DIRECTORY+"/lifecycle-background-observation.json",QJsonObject::fromVariantMap(value)); }
    }

    // Passive source on the actual VR TabletRoot and offscreen surface. Input
    // remains in NavigationUi with its existing native VR pointer/controller path.
    void scriptObservationTick() {
        const QString path=BRIDGE_DIRECTORY+"/script-file-ui-command.json";
        QFile input(path);
        if (QFileInfo(path).isSymLink() || !input.open(QIODevice::ReadOnly) || input.size()>4096) { return; }
        QJsonParseError error;
        const auto document=QJsonDocument::fromJson(input.readAll(),&error);
        if (error.error!=QJsonParseError::NoError || !document.isObject()) { return; }
        const auto command=document.object();
        const auto id=command.value("commandId").toString();
        if (!exactKeys(command,{"schemaVersion","commandId","action"})
                || command.value("schemaVersion")!=QJsonValue(1)
                || command.value("action")!=QJsonValue(QStringLiteral("observe"))
                || !QRegularExpression("\\A[0-9a-f]{32}\\z").match(id).hasMatch()
                || id==_lastScriptObservationId || _scriptObservationNonces.contains(id)
                || _scriptObservationNonces.size()>=4096) { return; }
        // Never recapture a prior original nonce after another role's read.
        // A failed write also retains its nonce; no later query can retime it.
        _scriptObservationNonces.insert(id);
        _lastScriptObservationId=id;
        auto tablets=DependencyManager::get<TabletScriptingInterface>();
        auto tablet=tablets ? tablets->getTablet(SYSTEM_TABLET) : nullptr;
        auto root=tablet ? tablet->getTabletRoot() : nullptr;
        auto surface=tablet ? tablet->getTabletSurface() : nullptr;
        auto window=surface ? surface->getWindow() : nullptr;
        auto packet=_scriptObservation.observe(root,window);
        if (packet.isEmpty()) { return; }
        auto inventory=packet.value("scriptInventory").toObject();
        if (inventory.isEmpty()) { return; }
        inventory["tabletPresent"]=bool(tablet);
        inventory["tabletShown"]=tablet && tablet->property("tabletShown").toBool();
        packet["scriptInventory"]=inventory;
        packet["commandId"]=id;packet["action"]=QStringLiteral("observe");
        writeJson(BRIDGE_DIRECTORY+"/script-file-ui.json",packet);
    }
#endif

    void navigationTick() {
        auto tabletInterface = DependencyManager::get<TabletScriptingInterface>();
        auto tablet = tabletInterface ? tabletInterface->getTablet(SYSTEM_TABLET) : nullptr;
        auto root = tablet ? tablet->getTabletRoot() : nullptr;
        auto surface = tablet ? tablet->getTabletSurface() : nullptr;
        auto window = surface ? surface->getWindow() : nullptr;
        const bool open = tablet && tablet->property("tabletShown").toBool();
        writeJson(BRIDGE_DIRECTORY + "/navigation-ui-observation.json", _navigation.observe(root, window, open));
        const QString path = BRIDGE_DIRECTORY + "/navigation-ui-command.json";
        QFile input(path);
        if (QFileInfo(path).isSymLink() || !input.open(QIODevice::ReadOnly) || input.size() > 24 * 1024) { return; }
        QJsonParseError error;
        const auto document = QJsonDocument::fromJson(input.readAll(), &error);
        if (error.error != QJsonParseError::NoError || !document.isObject()) { return; }
        const auto command = document.object();
        const auto id = command.value("commandId").toString();
        if (id.isEmpty() || id.size() > 128 || id == _lastNavigationCommandId) { return; }
        _lastNavigationCommandId = id;
        // The pointer callback is the existing native VR surface route. The
        // navigation resolver itself cannot call AddressManager or QML slots.
        const auto status = _navigation.apply(root, window, open, command,
            [surface](QQuickItem* item) { return sendPointerClick(item, surface); },
            [surface](QQuickItem* item, const QPointF& point) { return sendPointerAt(item, surface, point); },
            [surface](QQuickItem* item, const QPointF& point, int delta) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
                return sendPointerScroll(item,surface,point,delta);
#else
                Q_UNUSED(item) Q_UNUSED(point) Q_UNUSED(delta) return false;
#endif
            });
        writeJson(BRIDGE_DIRECTORY + "/navigation-ui-status.json", status);
    }

    void applyCommand(const Observation& observation) {
        QFile input(COMMAND_PATH);
        if (!input.exists() || QFileInfo(COMMAND_PATH).isSymLink()
                || input.size() > 16 * 1024
                || !input.open(QIODevice::ReadOnly)) {
            return;
        }
        QJsonParseError parseError;
        const auto document = QJsonDocument::fromJson(input.readAll(), &parseError);
        if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
            return;
        }
        const auto command = document.object();
        const QString commandId = command.value(QStringLiteral("commandId")).toString();
        if (commandId.isEmpty() || commandId.size() > 128 || commandId == _lastCommandId) {
            return;
        }
        _lastCommandId = commandId;
        if (!exactKeys(command, {
                QStringLiteral("schemaVersion"), QStringLiteral("commandId"),
                QStringLiteral("contractVersion"), QStringLiteral("controlId") })
                || command.value(QStringLiteral("schemaVersion")).toInt(-1) != 1
                || command.value(QStringLiteral("contractVersion")).toInt(-1) != 1) {
            writeStatus(commandId, false, QStringLiteral("malformed-command"));
            return;
        }
        const QString controlId = command.value(QStringLiteral("controlId")).toString();
        if (!observation.snapshot.value(QStringLiteral("ready")).toBool()
                || !CONTROL_IDS.contains(controlId)
                || !observation.controls.contains(controlId)) {
            writeStatus(commandId, false, QStringLiteral("control-not-visible"));
            return;
        }
        auto tabletInterface = DependencyManager::get<TabletScriptingInterface>();
        auto tablet = tabletInterface ? tabletInterface->getTablet(SYSTEM_TABLET) : nullptr;
        auto surface = tablet ? tablet->getTabletSurface() : nullptr;
        if (!sendPointerClick(observation.controls.value(controlId), surface)) {
            writeStatus(commandId, false, QStringLiteral("pointer-activation-failed"));
            return;
        }
        writeStatus(commandId, true, QString());
    }

    QTimer _timer;
    QString _lastCommandId;
    QString _lastNavigationCommandId;
    NavigationUi _navigation;
#if defined(OVERTE_E2E_FEATURE_TESTS)
    QMap<QString,std::shared_ptr<overte::e2e::PicoSnapshotFastCancel>> _snapshotCancelJobs;
    QString _lastSnapshotCancelCommand;
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
    overte::e2e::LifecycleUiObservation _lifecycleObservation {{
        {"create",lifecycleScriptSource("system/create/qml/NativeCreate.qml")},
        {"chat",lifecycleScriptSource("communityScripts/armored-chat/armored_chat.qml")},
        {"scripts",PathUtils::qmlUrl("hifi/dialogs/TabletRunningScripts.qml")}
    }};
    QSet<QString> _lifecycleObservationNonces;
    overte::e2e::AssetsPageObservation _assetsPages;
    QSet<QString> _assetsPageNonces;
    overte::e2e::LifecycleBackgroundHistory _lifecycleBackground {this,[this](const QString& run) { return lifecycleCurrent(run); }};
    overte::e2e::ScriptFileUi _scriptObservation;
    overte::e2e::LoginUi _loginObservation;
    overte::e2e::GraphicsUi _graphicsObservation;
    PicoGraphicsComposition _graphicsComposition;
    overte::e2e::FeatureUiInventory& _graphicsInventory {overte::e2e::graphicsUiInventory()};
    QSet<QString> _graphicsObservationNonces;
    overte::e2e::LoginUiInventory _loginInventory;
    QSet<QString> _loginObservationNonces;
    QSet<QString> _homeNonces;
    const QString _homeInstance { QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') };
    quint64 _homeSequence { 0 };
    QElapsedTimer _homeClock;
    QString _lastScriptObservationId;
    QSet<QString> _scriptObservationNonces;
#endif
};

}  // namespace

void installTabletBridge(QObject* owner) {
    if (owner) {
        new TabletBridge(owner);
    }
}

}  // namespace overte::pico::e2e
