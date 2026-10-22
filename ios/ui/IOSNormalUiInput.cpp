// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSNormalUiInput.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMouseEvent>
#include <QSet>
#include <QRegularExpression>
#include <QThread>
#include <QUuid>
#include <QVariant>
#include <algorithm>
#include <cmath>
#include <functional>
#include <ui/NativeFieldInput.h>
#include "../../tests/device/native/NormalScriptControls.h"
#include "../../tests/device/native/NormalScriptFileControls.h"
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "../../tests/device/native/ScriptFileUi.h"
#include "../../tests/device/native/ScriptUiInventory.h"
#include "../../tests/device/native/NormalAccountMenuControls.h"
#include "../../tests/device/native/NormalViewMenuControls.h"
#include "../../tests/device/native/NormalPlacesControls.h"
#include "../../tests/device/native/NormalNavigationErrorControls.h"
#include "../../tests/device/native/AccountPreferenceObservation.h"
#endif

namespace overte::ios {
namespace {

QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces); }

QRectF visibleBounds(QQuickItem* item) {
    auto window = item ? item->window() : nullptr;
    if (!window || window->thread() != QThread::currentThread()
            || !item->isVisible() || item->width() <= 0 || item->height() <= 0) { return {}; }
    auto result = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
    const auto center = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
    if (!std::isfinite(result.x()) || !std::isfinite(result.y())
            || !std::isfinite(result.width()) || !std::isfinite(result.height())
            || !std::isfinite(center.x()) || !std::isfinite(center.y())) { return {}; }
    result = result.intersected(QRectF(0, 0, window->width(), window->height()));
    for (auto parent = item; parent; parent = parent->parentItem()) {
        if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity() <= 0.01) { return {}; }
        if (parent->clip()) {
            if (!parent->clipRect().contains(parent->mapFromScene(center))) { return {}; }
            result = result.intersected(parent->mapRectToScene(parent->clipRect()));
        }
    }
    return result.contains(center) ? result : QRectF();
}

QString identify(QQuickItem* item, bool hud, bool fileAllowed) {
    if (fileAllowed) {
        const auto file = overte::e2e::scriptFileControlId(item);
        if (!file.isEmpty() && (!hud || file != QStringLiteral("scripts.from-file"))) { return file; }
    }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (fileAllowed) {
        const auto error=overte::e2e::navigationErrorControlId(item);
        if (!error.isEmpty()) { return error; }
        const auto places=overte::e2e::placesControlId(item);
        if (!places.isEmpty()) { return places; }
        const auto chat=overte::e2e::chatControlId(item);
        if (!chat.isEmpty()) { return chat; }
        const auto create=overte::e2e::createControlId(item);
        if (!create.isEmpty()) { return create; }
        const auto graphics = overte::e2e::graphicsControlId(item);
        if (!graphics.isEmpty()) { return graphics; }
        const auto audio = overte::e2e::audioControlId(item);
        if (!audio.isEmpty()) { return audio; }
        const auto accountPreference=overte::e2e::accountPreferenceControlId(item);
        if (!accountPreference.isEmpty()) { return accountPreference; }
        const auto accountMenu=overte::e2e::accountMenuControlId(item);
        if (!accountMenu.isEmpty()) { return accountMenu; }
        const auto viewMenu=overte::e2e::viewMenuControlId(item);
        if (!viewMenu.isEmpty()) { return viewMenu; }
        const auto login=overte::e2e::loginControlId(item);
        if (!login.isEmpty()) { return login; }
    }
#endif
    const auto name = item->objectName();
    if (hud) {
        static const QHash<QString, QString> fields {
            { "PhoneAddressField", "address.field" }, { "PhoneAddressGoButton", "address.go" },
            { "PhoneAddressCancelButton", "address.cancel" }, { "PhoneAddressBackButton", "address.back" },
            { "OverteTabletOpen", "hud.tablet" },
        };
        if (fields.contains(name)) { return fields.value(name); }
        if (item->property("text").toString() == QStringLiteral("GO TO")
                && item->metaObject()->indexOfSignal("clicked()") >= 0) { return QStringLiteral("hud.goto"); }
    } else {
        const auto script = overte::e2e::scriptControlId(item);
        if (!script.isEmpty()) { return script; }
        static const QHash<QString, QString> controls {
            { "nav.home", "tablet.home" }, { "goBack", "places.back" }, { "goForward", "places.forward" },
            { "nav.close", "tablet.close" }, { "OverteTabletClose", "tablet.close" },
            { "snapshotName", "snapshot.name" }, { "snapshotMode", "snapshot.mode" },
            { "snapshotFormat", "snapshot.format" }, { "snapshotCapture", "snapshot.capture" },
            { "snapshotCancelCapture", "snapshot.cancel" },
        };
        if (controls.contains(name)) { return controls.value(name); }
        for (const auto& mode : {"still", "animated", "panorama", "cubemap"}) {
            if (name == QStringLiteral("snapshotMode.option.") + mode) {
                return QStringLiteral("snapshot.mode.") + mode;
            }
        }
        for (const auto& format : {"png", "jpg", "webp"}) {
            if (name == QStringLiteral("snapshotFormat.option.") + format) {
                return QStringLiteral("snapshot.format.") + format;
            }
        }
        if (item->property("text").toString() == QStringLiteral("SNAP")
                && item->metaObject()->indexOfSignal("clicked()") >= 0) { return QStringLiteral("snapshot.entry"); }
        if (item->property("text").toString() == QStringLiteral("PLACES")
                && item->metaObject()->indexOfSignal("clicked()") >= 0) { return QStringLiteral("tablet.places"); }
        for (int page = 1; page <= 32; ++page) {
            if (name == QStringLiteral("tabletPage.%1").arg(page)) { return QStringLiteral("tablet.page.%1").arg(page); }
        }
    }
    return {};
}

bool enabled(QQuickItem* item) {
    const auto button = item->property("buttonEnabled");
    return item->isEnabled() && (!button.isValid() || button.toBool());
}

bool ownedObject(QObject* object, const QObject* owner) {
    for (int depth = 0; object && depth < 128; ++depth, object = object->parent()) {
        if (object == owner) { return true; }
    }
    return false;
}

bool integer(const QJsonValue& value, qint64& result) {
    const double number = value.toDouble(-1);
    if (!value.isDouble() || !std::isfinite(number) || number < 0
            || number > 9007199254740991.0 || std::floor(number) != number) { return false; }
    result = static_cast<qint64>(number);
    return true;
}

} // namespace

NormalUiInput::NormalUiInput() : _instance(nonce()) { _clock.start(); }

bool NormalUiInput::guiThread() const { return qApp && QThread::currentThread() == qApp->thread(); }

QJsonObject NormalUiInput::observe(QQuickItem* hud, QQuickItem* tablet, bool tabletShown) {
    if (!guiThread()) { return {}; }
    const bool changed=_hud!=hud || _tablet!=tablet || _tabletShown!=tabletShown;
    if (changed) { _controls.clear(); }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (changed || _loginGeneration.isEmpty()) { _loginGeneration=nonce(); }
#endif
    _hud = hud; _tablet = tablet; _tabletShown = tabletShown;
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto loginContext=_loginReader ? _loginReader() : overte::e2e::LoginUiContext();
    const auto audioContext = _audioReader ? _audioReader() : overte::e2e::AudioUiContext();
    const auto graphicsContext = _graphicsReader ? _graphicsReader() : overte::e2e::GraphicsUiContext();
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
    // This separate passive walk includes hidden roots and actual retained
    // objects. Input eligibility/modal suppression cannot manufacture absence.
    overte::e2e::ScriptUiInventory scriptInventory;
    QSet<QQuickItem*> surveyed;
    bool inventoryComplete {hud != nullptr && hud->window() != nullptr};
    std::function<void(QQuickItem*, int)> survey = [&](QQuickItem* node, int depth) {
        if (!node || surveyed.contains(node) || !inventoryComplete) { return; }
        if (depth > 128 || surveyed.size() >= 8192 || node->thread() != qApp->thread()) {
            inventoryComplete=false;return;
        }
        surveyed.insert(node);
        scriptInventory.visit(node);
        if (node->objectName()=="RunningScripts"
                || (node->objectName()=="nativeFileBrowser"
                    && node->property("caption").toString()=="Open Script and Companion Files")) {
            _scriptRoots.insert(node,node);
        }
        for (auto child:node->childItems()) { survey(child,depth+1); }
    };
    if (hud && hud->window()) { survey(hud->window()->contentItem(),0); }
    else { survey(hud,0); }
    if (tablet && tablet->window()) { survey(tablet->window()->contentItem(),0); }
    else { survey(tablet,0); }
    // QPointers remain owned until actual destruction, including objects which
    // were removed from their visual parent while a callback is outstanding.
    for (auto it=_scriptRoots.begin();it!=_scriptRoots.end();) {
        if (!it.value()) { it=_scriptRoots.erase(it);continue; }
        ++it;
    }
    const auto retainedRoots=_scriptRoots.values();
    for (const auto& root:retainedRoots) { if (root) { survey(root,0); } }
    if (_scriptRoots.size()>32 || _scriptObservationSequence>=9007199254740991LL) { inventoryComplete=false; }
    auto scriptState=scriptInventory.observation(inventoryComplete);
    scriptState["tabletPresent"]=tablet!=nullptr;
    scriptState["tabletShown"]=tabletShown;
#endif
    QHash<QString, Control> controls;
    int visited { 0 };
    bool ambiguous { false };
    std::function<void(QQuickItem*, int, bool)> walk = [&](QQuickItem* node, int depth, bool hudTree) {
        if (!node || ambiguous) { return; }
        if (++visited > 4096 || depth > 128 || node->thread() != qApp->thread()) { ambiguous = true; return; }
        if (!visibleBounds(node).isEmpty()
#if defined(OVERTE_E2E_FEATURE_TESTS)
                || overte::e2e::graphicsObservable(node)
#endif
                ) {
            bool fileAllowed = true;
            if (hudTree && tabletShown && tablet && tablet != hud) {
                fileAllowed = !ownedObject(node, tablet);
                for (auto parent = node; parent; parent = parent->parentItem()) {
                    if (parent == tablet) { fileAllowed = false; break; }
                }
            }
            const auto id = identify(node, hudTree, fileAllowed);
            if (!id.isEmpty()) {
                if (controls.contains(id)) { ambiguous = true; return; }
                const auto old = _controls.value(id);
                auto source = overte::e2e::scriptFileControlSource(node);
                if (source.isEmpty()) { source = overte::e2e::scriptRowSource(node); }
#if defined(OVERTE_E2E_FEATURE_TESTS)
                if (id.startsWith("navigation.error.")) {
                    source=overte::e2e::navigationErrorControlSource(node);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (overte::e2e::placesControlId(node)==id) {
                    source=overte::e2e::placesControlSource(node,id);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (id.startsWith("view.")) {
                    source=overte::e2e::viewMenuControlSource(node);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (id.startsWith("account.")) {
                    source=id=="account.remember" ? overte::e2e::accountPreferenceControlSource(node,loginContext)
                        : overte::e2e::accountMenuControlSource(node);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (id.startsWith("chat.")) {
                    source=overte::e2e::chatControlSource(node,id);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (id.startsWith("create.")) {
                    source=overte::e2e::createControlSource(node,id);
                } else if (id.startsWith("login.")) {
                    if (!loginContext.valid) { return; }
                    source=overte::e2e::loginControlSource(node,id,loginContext);
                } else if (id.startsWith("graphics.") || (id == "settings.entry" && graphicsContext.valid)) {
                    if (!graphicsContext.valid) { return; }
                    source = overte::e2e::graphicsControlSource(node,id,graphicsContext);
                } else if (id.startsWith("audio.") || id == "settings.entry") {
                    if (!audioContext.valid) { return; }
                    source = overte::e2e::audioControlSource(node, id, audioContext);
                }
#endif
                const auto token = old.item == node && old.window == node->window() && old.source == source ? old.token : nonce();
                controls.insert(id, { node, node->window(), token, source });
            }
        }
        const auto children = node->childItems();
        for (auto child : children) { walk(child, depth + 1, hudTree); }
    };
    if (hud) { walk(hud, 0, true); }
    if (tabletShown && tablet && tablet != hud) {
        walk(tablet, 0, false);
        // The screen-space tablet is nested inside the HUD's window. Qt
        // reparents popup visuals beside the complete HUD root. Their QObject
        // ownership still identifies the actual originating tablet control.
        if (auto window = tablet->window()) {
            for (auto layer : window->contentItem()->childItems()) {
                if (layer->inherits("QQuickOverlay")) {
                    for (auto popup : layer->childItems()) {
                        if (ownedObject(popup, tablet)) { walk(popup, 0, false); }
                    }
                }
            }
        }
    }
    // A modal editor and the tablet cover the underlying world toolbar.
    if (tabletShown || controls.contains(QStringLiteral("address.field"))) {
        controls.remove(QStringLiteral("hud.goto"));
        controls.remove(QStringLiteral("hud.tablet"));
    }
    if (controls.contains(QStringLiteral("address.field"))) {
        for (const auto& id : controls.keys()) {
            if (id.startsWith(QStringLiteral("tablet.")) || id.startsWith(QStringLiteral("places."))
                    || id.startsWith(QStringLiteral("snapshot.")) || id.startsWith(QStringLiteral("scripts."))
                    || id.startsWith(QStringLiteral("script-file.")) || id.startsWith("chat.") || id.startsWith("create.") || id.startsWith("audio.") || id.startsWith("graphics.") || id == "settings.entry") {
                controls.remove(id);
            }
        }
    }
    if (controls.contains(QStringLiteral("scripts.url.field"))) {
        for (const auto& id : controls.keys()) {
            if (!id.startsWith(QStringLiteral("scripts.url."))) { controls.remove(id); }
        }
    }
    bool fileModal { false };
    for (const auto& id : controls.keys()) {
        fileModal = fileModal || id.startsWith(QStringLiteral("script-file."));
    }
    if (fileModal) {
        for (const auto& id : controls.keys()) {
            if (!id.startsWith(QStringLiteral("script-file."))) { controls.remove(id); }
        }
    }
    if (controls.size() > 384) { ambiguous = true; }
    if (ambiguous) { controls.clear(); }
    _controls = controls;
    auto ids = controls.keys(); std::sort(ids.begin(), ids.end());
    QJsonArray observed;
    for (const auto& id : ids) {
        const auto control = controls.value(id);
        const auto bounds = visibleBounds(control.item);
        QJsonObject row { { "id", id }, { "token", control.token },
            { "enabled", enabled(control.item) }, { "focused", control.item->hasActiveFocus() },
            { "frame", QJsonObject { { "x", bounds.x() }, { "y", bounds.y() },
                { "width", bounds.width() }, { "height", bounds.height() } } } };
        if (id.startsWith(QStringLiteral("snapshot.mode.")) || id.startsWith(QStringLiteral("snapshot.format."))) {
            row["checked"] = control.item->property("checked").toBool();
        }
        overte::e2e::appendScriptControlObservation(row, control.item, id);
        overte::e2e::appendScriptFileObservation(row, control.item, id);
#if defined(OVERTE_E2E_FEATURE_TESTS)
        if (id.startsWith("navigation.error.")) {
            overte::e2e::appendNavigationErrorControl(row,control.item);
        } else if (overte::e2e::placesControlId(control.item)==id) {
            overte::e2e::appendPlacesControlObservation(row,control.item,id);
        } else if (id.startsWith("view.")) {
            const auto metadata=overte::e2e::viewMenuControlObservation(control.item);
            for (auto it=metadata.begin();it!=metadata.end();++it) { row[it.key()]=it.value(); }
        } else if (id.startsWith("account.")) {
            if (id=="account.remember") {
                const auto metadata=overte::e2e::accountPreferenceControlObservation(control.item,loginContext);
                for (auto it=metadata.begin();it!=metadata.end();++it) { row[it.key()]=it.value(); }
            } else { overte::e2e::appendAccountMenuObservation(row,control.item); }
        } else if (id.startsWith("chat.")) {
            overte::e2e::appendChatControlObservation(row,control.item,id);
        } else if (id.startsWith("create.")) {
            overte::e2e::appendCreateControlObservation(row,control.item,id);
        } else if (id.startsWith("login.")) {
            overte::e2e::appendLoginControlObservation(row,control.item,id,loginContext);
        } else if (id.startsWith("graphics.") || (id == "settings.entry" && graphicsContext.valid)) {
            overte::e2e::appendGraphicsControlObservation(row,control.item,id,graphicsContext);
            if (row.value("viewport").toString() != "visible") { row["frame"] = QJsonValue(); }
        } else if (id.startsWith("audio.") || id == "settings.entry") {
            overte::e2e::appendAudioControlObservation(row, control.item, id, audioContext);
        }
#endif
        observed.append(row);
    }
    QJsonObject result { { "schemaVersion", 1 }, { "instance", _instance },
        { "frameSpace", QStringLiteral("qt-window-logical") },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) },
        { "sampleEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch()) },
        { "elapsedMs", static_cast<double>(_clock.elapsed()) }, { "lastSequence", static_cast<double>(_sequence) },
        { "tabletShown", tabletShown }, { "ready", !ambiguous && hud && hud->window() }, { "controls", observed } };
#if defined(OVERTE_E2E_FEATURE_TESTS)
    result["featureControlsVersion"] = 1;
    result["placesControlsVersion"]=2;result["placesSourceSequence"]=static_cast<double>(++_placesObservationSequence);
    result["navigationDialogControlsVersion"]=1;
    result["navigationDialogSourceSequence"]=static_cast<double>(++_navigationDialogSequence);
    result["accountMenuControlsVersion"]=1;
    result["viewMenuControlsVersion"]=1;
    result["loginClearInputVersion"]=1;
    result["accountPreferences"]=overte::e2e::accountPreferenceObservation();
    result["scriptObservationVersion"]=1;
    result["scriptSourceSequence"]=++_scriptObservationSequence;
    result["scriptInventory"]=scriptState;
    result["createControlsVersion"]=1;result["createGeneration"]=_loginGeneration;
    result["chatControlsVersion"]=1;result["chatGeneration"]=_loginGeneration;
    result["fileControlsVersion"] = 1;
    if (audioContext.valid) { result["audioControlsVersion"] = 1; }
    if (graphicsContext.valid) { result["graphicsControlsVersion"] = 1; }
    if (loginContext.valid) { result["loginControlsVersion"]=2;result["generation"]=_loginGeneration; }
#endif
    return result;
}

QQuickItem* NormalUiInput::item(const QString& controlId, const QString& token) {
    if (!guiThread()) { return nullptr; }
    observe(_hud, _tablet, _tabletShown);
    const auto control = _controls.value(controlId);
    return control.token == token && control.item && control.item->window() == control.window
        && !visibleBounds(control.item).isEmpty() ? control.item.data() : nullptr;
}

QRectF NormalUiInput::projectedFrame(const QString& controlId, const QString& token,
                                   const QRectF& windowBounds, const QRectF& safeBounds) {
    auto control = item(controlId, token);
    const auto finite = [](const QRectF& rect) {
        return std::isfinite(rect.x()) && std::isfinite(rect.y())
            && std::isfinite(rect.width()) && std::isfinite(rect.height());
    };
    if (!control || !finite(windowBounds) || !finite(safeBounds) || windowBounds.isEmpty()
            || safeBounds.isEmpty() || !windowBounds.contains(safeBounds)) { return {}; }
    auto window = control->window();
    if (!window || window->width() <= 0 || window->height() <= 0) { return {}; }
    const auto source = visibleBounds(control);
    const double sx = windowBounds.width() / window->width();
    const double sy = windowBounds.height() / window->height();
    return QRectF(windowBounds.x() + source.x() * sx, windowBounds.y() + source.y() * sy,
                  source.width() * sx, source.height() * sy).intersected(safeBounds);
}

bool NormalUiInput::press(const QString& controlId, const QString& token) {
    auto control = item(controlId, token);
    if (!control || !enabled(control)) { return false; }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    const auto graphicsContext = _graphicsReader ? _graphicsReader() : overte::e2e::GraphicsUiContext();
    if (controlId.startsWith("navigation.error.")) {
        const auto original=OffscreenUi::featureNavigationDialogControl(control);
        if (controlId!="navigation.error.ok" || original.value("id").toString()!=controlId
                || original.value("inputReady")!=QVariant(true)
                || overte::e2e::navigationErrorControlSource(control)!=_controls.value(controlId).source
                || !overte::e2e::NormalControlUi::ownsPoint(control,control->window(),
                    control->mapToScene(QPointF(control->width()/2,control->height()/2)))) { return false; }
    } else if (overte::e2e::placesControlId(control)==controlId) {
        const auto source=overte::e2e::placesControlSource(control,controlId);
        QJsonObject row;overte::e2e::appendPlacesControlObservation(row,control,controlId);
        if (source.isEmpty() || controlId=="places.page" || !row.value("inputReady").toBool()
                || source!=_controls.value(controlId).source
                || !overte::e2e::NormalControlUi::ownsPoint(control,control->window(),
                    control->mapToScene(QPointF(control->width()/2,control->height()/2)))) { return false; }
    } else if (controlId.startsWith("view.")) {
        const auto source=overte::e2e::viewMenuControlSource(control);
        if (source.isEmpty() || source!=_controls.value(controlId).source
                || !overte::e2e::NormalControlUi::ownsPoint(control,control->window(),
                    control->mapToScene(QPointF(control->width()/2,control->height()/2)))) { return false; }
    } else if (controlId.startsWith("account.")) {
        const auto point=control->mapToScene(QPointF(control->width()/2,control->height()/2));
        const auto context=_loginReader ? _loginReader() : overte::e2e::LoginUiContext();
        if (controlId=="account.remember" && (!context.valid || context.pending || context.tokenPresent)) { return false; }
        const auto source=controlId=="account.remember" ? overte::e2e::accountPreferenceControlSource(control,context)
            : overte::e2e::accountMenuControlSource(control);
        if (source.isEmpty() || source!=_controls.value(controlId).source
                || !overte::e2e::NormalControlUi::ownsPoint(control,control->window(),point)) { return false; }
    } else if (controlId.startsWith("chat.")) {
        QJsonObject row;overte::e2e::appendChatControlObservation(row,control,controlId);
        const auto point=control->mapToScene(QPointF(control->width()/2,control->height()/2));
        if (controlId=="chat.page" || !row.value("inputReady").toBool()
                || overte::e2e::chatControlSource(control,controlId)!=_controls.value(controlId).source
                || !overte::e2e::NormalControlUi::ownsPoint(control,control->window(),point)) { return false; }
    } else if (controlId.startsWith("login.")) {
        const auto context=_loginReader ? _loginReader() : overte::e2e::LoginUiContext();
        QJsonObject row;overte::e2e::appendLoginControlObservation(row,control,controlId,context);
        const auto point=control->mapToScene(QPointF(control->width()/2,control->height()/2));
        if (!context.valid || controlId=="login.page" || !row.value("inputReady").toBool()
                || overte::e2e::loginControlSource(control,controlId,context)!=_controls.value(controlId).source
                || !overte::e2e::NormalControlUi::ownsPoint(control,control->window(),point)) { return false; }
    } else if (controlId.startsWith("graphics.") || (controlId == "settings.entry" && graphicsContext.valid)) {
        if (controlId == "graphics.page" || controlId == "graphics.scrollbar" || controlId == "graphics.resolution"
                || !graphicsContext.valid || overte::e2e::graphicsControlSource(control,controlId,graphicsContext) != _controls.value(controlId).source) { return false; }
        QJsonObject row;
        overte::e2e::appendGraphicsControlObservation(row,control,controlId,graphicsContext);
        const auto point=control->mapToScene(QPointF(control->width()/2,control->height()/2));
        if (!row.value("inputReady").toBool() || !overte::e2e::NormalControlUi::ownsPoint(control,control->window(),point)) { return false; }
    } else if (controlId.startsWith("audio.") || controlId == "settings.entry") {
        QJsonObject row;
        const auto context = _audioReader ? _audioReader() : overte::e2e::AudioUiContext();
        if (controlId == "audio.page" || controlId == "audio.scrollbar" || !context.valid
                || overte::e2e::audioControlSource(control, controlId, context) != _controls.value(controlId).source) { return false; }
        overte::e2e::appendAudioControlObservation(row, control, controlId, context);
        const auto point = control->mapToScene(QPointF(control->width()/2, control->height()/2));
        if (!row.value("inputReady").toBool() || !overte::e2e::NormalControlUi::ownsPoint(control, control->window(), point)) { return false; }
    }
#endif
    QPointer<QQuickWindow> window(control->window());
    const auto position = control->mapToScene(QPointF(control->width() / 2, control->height() / 2));
    QMouseEvent down(QEvent::MouseButtonPress, position, position, position,
        Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    const bool delivered = QCoreApplication::sendEvent(window, &down);
    if (window) {
        QMouseEvent up(QEvent::MouseButtonRelease, position, position, position,
            Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
        QCoreApplication::sendEvent(window, &up);
    }
    return delivered;
}

QJsonObject NormalUiInput::edit(const QJsonObject& command) {
    if (!guiThread()) { return {}; }
    const auto action = command.value("operation").toString();
    QSet<QString> expected { "schemaVersion", "commandId", "instance", "sequence", "observedElapsedMs", "fieldToken", "operation" };
    if (action == QStringLiteral("replace")) { expected.insert(QStringLiteral("text")); }
    if (action == QStringLiteral("select-index")) { expected.insert(QStringLiteral("index")); }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (action == "scroll") { expected.insert("direction"); }
    if (action == "set-value") { expected.insert("value"); }
#endif
    const auto keys = command.keys();
    qint64 sequence { 0 }, observed { 0 };
    const auto id = command.value("commandId").toString();
    QJsonObject result { { "schemaVersion", 1 }, { "commandId", id }, { "instance", _instance },
        { "sequence", command.value("sequence") }, { "performed", false },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) },
        { "sampleEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch()) } };
    if (QSet<QString>(keys.begin(), keys.end()) != expected || command.value("schemaVersion") != QJsonValue(1)
            || QUuid(id).isNull() || QUuid(id).toString(QUuid::WithoutBraces) != id
            || command.value("instance") != QJsonValue(_instance)
            || !integer(command.value("sequence"), sequence) || sequence != _sequence + 1
            || !integer(command.value("observedElapsedMs"), observed) || observed > _clock.elapsed()
            || _clock.elapsed() - observed > 5000 || (action != "replace" && action != "submit" && action != "select-index"
#if defined(OVERTE_E2E_FEATURE_TESTS)
                && action != "activate" && action != "scroll" && action != "set-value"
#endif
                )) { return result; }
    _sequence = sequence;
    const auto fieldToken = command.value("fieldToken").toString();
#if defined(OVERTE_E2E_FEATURE_TESTS)
    // One native sequence covers normal Places/Create/Chat pointer/key/IME input. The
    // original token resolves the item; no desired entity state is accepted.
    observe(_hud,_tablet,_tabletShown);
    QString errorId;
    for (auto it=_controls.cbegin();it!=_controls.cend();++it) {
        if (it.value().token==fieldToken && it.key().startsWith("navigation.error.")) {
            if (!errorId.isEmpty()) { return result; }errorId=it.key();
        }
    }
    if (!errorId.isEmpty()) {
        if (action=="activate" && errorId=="navigation.error.ok") { result["performed"]=press(errorId,fieldToken); }
        return result;
    }
    QString placesId;
    for (auto it=_controls.cbegin();it!=_controls.cend();++it) {
        if (it.value().token==fieldToken && overte::e2e::placesControlId(it.value().item)==it.key()) {
            if (!placesId.isEmpty()) { return result; } placesId=it.key();
        }
    }
    if (!placesId.isEmpty()) {
        auto target=item(placesId,fieldToken);
        if (!target || !enabled(target)) { return result; }
        const auto source=overte::e2e::placesControlSource(target,placesId);
        QJsonObject row;overte::e2e::appendPlacesControlObservation(row,target,placesId);
        if (source.isEmpty() || source!=_controls.value(placesId).source || placesId=="places.page"
                || !row.value("inputReady").toBool()) { return result; }
        const auto point=target->mapToScene(QPointF(target->width()/2,target->height()/2));
        if (!overte::e2e::NormalControlUi::ownsPoint(target,target->window(),point)) { return result; }
        if (action=="activate") { result["performed"]=press(placesId,fieldToken); }
        else if (action=="replace" && (placesId=="places.search" || placesId=="places.bookmark-name" || placesId=="places.server-url")
                && command.value("text").isString()) {
            const auto text=command.value("text").toString();bool valid=text.size()<=4096;
            for (auto character:text) { if (character.unicode()<32 || character.unicode()==127) { valid=false;break; } }
            if (valid) { result["performed"]=overte::ui::replaceFocusedField(target,target->window(),text); }
        }
        return result;
    }
    QString chatId;
    for (auto it=_controls.cbegin();it!=_controls.cend();++it) {
        if (it.value().token==fieldToken && it.key().startsWith("chat.")) {
            if (!chatId.isEmpty()) { return result; } chatId=it.key();
        }
    }
    if (!chatId.isEmpty()) {
        auto target=item(chatId,fieldToken);
        if (!target || !enabled(target)) { return result; }
        QJsonObject row;overte::e2e::appendChatControlObservation(row,target,chatId);
        if (!row.value("inputReady").toBool() || chatId=="chat.page"
                || overte::e2e::chatControlSource(target,chatId)!=_controls.value(chatId).source) { return result; }
        const auto point=target->mapToScene(QPointF(target->width()/2,target->height()/2));
        if (action=="activate" && overte::e2e::NormalControlUi::ownsPoint(target,target->window(),point)) {
            result["performed"]=press(chatId,fieldToken);
        } else if (chatId=="chat.input" && action=="replace" && command.value("text").isString()
                && overte::e2e::chatText(command.value("text").toString())
                && overte::e2e::NormalControlUi::ownsPoint(target,target->window(),point)) {
            result["performed"]=overte::ui::replaceFocusedField(target,target->window(),command.value("text").toString());
        } else if (chatId=="chat.input" && action=="submit") {
            result["performed"]=overte::ui::submitFocusedField(target,target->window());
        }
        return result;
    }
    QString createId;
    for (auto it=_controls.cbegin();it!=_controls.cend();++it) {
        if (it.value().token==fieldToken && (it.key().startsWith("create.") || it.key()=="tablet.home" || it.key().startsWith("tablet.page."))) {
            if (!createId.isEmpty()) { return result; } createId=it.key();
        }
    }
    if (!createId.isEmpty()) {
        auto target=item(createId,fieldToken);
        if (!target || !enabled(target)) { return result; }
        QJsonObject row;overte::e2e::appendCreateControlObservation(row,target,createId);
        if (!row.value("inputReady").toBool() || createId=="create.page"
                || (createId.startsWith("create.") && overte::e2e::createControlSource(target,createId)!=_controls.value(createId).source)) { return result; }
        const auto point=target->mapToScene(QPointF(target->width()/2,target->height()/2));
        if (action=="activate" && createId!="create.scrollbar"
                && overte::e2e::NormalControlUi::ownsPoint(target,target->window(),point)) {
            result["performed"]=press(createId,fieldToken);
        } else if (action=="replace" && overte::e2e::createField(createId) && command.value("text").isString()
                && overte::e2e::createText(command.value("text").toString())
                && overte::e2e::NormalControlUi::ownsPoint(target,target->window(),point)) {
            result["performed"]=overte::ui::replaceFocusedField(target,target->window(),command.value("text").toString());
        } else if (action=="select-index" && overte::e2e::createChoice(createId)) {
            qint64 index{0};if (integer(command.value("index"),index)) {
                result["performed"]=overte::e2e::NormalControlUi::selectCreateChoice(target,target->window(),index);
            }
        } else if (action=="scroll" && createId=="create.scrollbar") {
            QPointF scrollPoint;
            if (!overte::e2e::createScrollPoint(target,command.value("direction").toString(),scrollPoint)
                    || !overte::e2e::NormalControlUi::ownsPoint(target,target->window(),scrollPoint)) { return result; }
            QPointer<QQuickWindow> window(target->window());
            QMouseEvent down(QEvent::MouseButtonPress,scrollPoint,scrollPoint,scrollPoint,Qt::LeftButton,Qt::LeftButton,Qt::NoModifier);
            const bool delivered=QCoreApplication::sendEvent(window,&down);bool released{false};
            if (window) {
                QMouseEvent up(QEvent::MouseButtonRelease,scrollPoint,scrollPoint,scrollPoint,Qt::LeftButton,Qt::NoButton,Qt::NoModifier);
                released=QCoreApplication::sendEvent(window,&up);
            }
            result["performed"]=delivered && released;
        }
        return result;
    }
    if (action=="activate") { return result; } // No unbound pointer shortcut.
    if (action == "scroll" || action == "set-value") {
        QQuickItem* target {nullptr}; QPointF point;
        if (action == "scroll") {
            target = item(QStringLiteral("audio.scrollbar"),fieldToken);
            if (target && !overte::e2e::audioScrollPoint(target,command.value("direction").toString(),point)) { return result; }
            if (!target) {
                target = item(QStringLiteral("graphics.scrollbar"),fieldToken);
                if (target && !overte::e2e::graphicsScrollPoint(target,command.value("direction").toString(),point)) { return result; }
            }
        } else {
            target = item(QStringLiteral("graphics.resolution"),fieldToken);
            if (!command.value("value").isDouble() || (target && !overte::e2e::graphicsSliderPoint(target,command.value("value").toDouble(),point))) { return result; }
        }
        if (!target || !enabled(target)) { return result; }
        const auto graphicsId = overte::e2e::graphicsControlId(target);
        if (!graphicsId.isEmpty()) {
            const auto context = _graphicsReader ? _graphicsReader() : overte::e2e::GraphicsUiContext();
            QJsonObject row; overte::e2e::appendGraphicsControlObservation(row,target,graphicsId,context);
            if (!row.value("inputReady").toBool() || overte::e2e::graphicsControlSource(target,graphicsId,context) != _controls.value(graphicsId).source) { return result; }
        }
        if (!overte::e2e::NormalControlUi::ownsPoint(target,target->window(),point)) { return result; }
        QPointer<QQuickWindow> window(target->window());
        QMouseEvent down(QEvent::MouseButtonPress,point,point,point,Qt::LeftButton,Qt::LeftButton,Qt::NoModifier);
        const bool delivered = QCoreApplication::sendEvent(window,&down);
        bool released {false};
        if (window) {
            QMouseEvent up(QEvent::MouseButtonRelease,point,point,point,Qt::LeftButton,Qt::NoButton,Qt::NoModifier);
            released = QCoreApplication::sendEvent(window,&up);
        }
        result["performed"] = delivered && released;
        return result;
    }
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (action=="clear-login-username") {
        auto target=item("login.username",fieldToken);
        const auto context=_loginReader ? _loginReader() : overte::e2e::LoginUiContext();
        QJsonObject row;overte::e2e::appendLoginControlObservation(row,target,"login.username",context);
        if (!target || !enabled(target) || !target->hasActiveFocus() || !context.valid
                || !row.value("inputReady").toBool()
                || overte::e2e::loginControlSource(target,"login.username",context)!=_controls.value("login.username").source
                || !overte::e2e::NormalControlUi::ownsPoint(target,target->window(),
                    target->mapToScene(QPointF(target->width()/2,target->height()/2)))) { return result; }
        result["performed"]=overte::ui::replaceFocusedField(target,target->window(),QString());
        result["sampleEpochMs"]=static_cast<double>(QDateTime::currentMSecsSinceEpoch());
        return result;
    }
#endif
    auto field = item(QStringLiteral("address.field"), fieldToken);
    bool snapshotName { false };
    bool scriptUrl { false }, scriptFolder { false }, scriptPrimary { false };
    if (!field) {
        field = item(QStringLiteral("snapshot.name"), fieldToken);
        snapshotName = field != nullptr;
    }
    if (!field) {
        field = item(QStringLiteral("scripts.url.field"), fieldToken);
        scriptUrl = field != nullptr;
    }
    if (!field) {
        field = item(QStringLiteral("script-file.folder"), fieldToken);
        scriptFolder = field != nullptr;
    }
    if (!field) {
        field = item(QStringLiteral("script-file.primary"), fieldToken);
        scriptPrimary = field != nullptr;
    }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    bool loginServer {false};
    if (!field) { field=item("login.server",fieldToken);loginServer=field!=nullptr; }
    if (loginServer) {
        const auto context=_loginReader ? _loginReader() : overte::e2e::LoginUiContext();
        QJsonObject row;overte::e2e::appendLoginControlObservation(row,field,"login.server",context);
        if (!context.valid || !row.value("inputReady").toBool()
                || overte::e2e::loginControlSource(field,"login.server",context)!=_controls.value("login.server").source
                || action!="replace" || !command.value("text").isString()
                || !overte::e2e::accountOriginText(command.value("text").toString())) { return result; }
    }
#endif
    if (!field || !enabled(field)) { return result; }
    if (action == QStringLiteral("select-index")) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
        qint64 index { 0 };
        if (scriptPrimary && integer(command.value("index"), index) && index < 32) {
            result["performed"] = overte::e2e::ScriptFileUi::selectFocusedPrimary(field, field->window(), index);
        }
#endif
        return result;
    }
    if (scriptPrimary) { return result; }
    if (action == QStringLiteral("replace") && command.value("text").isString()) {
        if (scriptFolder && !overte::e2e::validScriptFolderPath(command.value("text").toString())) { return result; }
        if (scriptUrl && !overte::e2e::validScriptUrlText(command.value("text").toString())) { return result; }
        if (snapshotName) {
            static const QRegularExpression ownedName {
                QStringLiteral("\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)\\z") };
            const auto text = command.value("text").toString();
            if (text.size() > 48 || !ownedName.match(text).hasMatch()) { return result; }
        }
        result["performed"] = overte::ui::replaceFocusedField(field, field->window(), command.value("text").toString());
    } else if (action == QStringLiteral("submit") && !snapshotName && !scriptUrl) {
        result["performed"] = overte::ui::submitFocusedField(field, field->window());
    }
    return result;
}

#if defined(OVERTE_E2E_FEATURE_TESTS)
QJsonObject NormalUiInput::privateLoginEdit(const QJsonObject& command,const QString& origin) {
    if (!guiThread()) { return {}; }
    QJsonObject result{{"schemaVersion",1},{"commandId",command.value("commandId")},{"instance",_instance},
        {"sequence",command.value("sequence")},{"performed",false},
        {"processId",static_cast<double>(QCoreApplication::applicationPid())},
        {"sampleEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())}};
    const auto keys=command.keys();qint64 sequence{0},observed{0};
    const QSet<QString> expected{"schemaVersion","commandId","instance","sequence","observedElapsedMs","fieldToken","operation","text"};
    const auto id=command.value("commandId").toString();
    if (QSet<QString>(keys.begin(),keys.end())!=expected || command.value("schemaVersion")!=QJsonValue(1)
            || command.value("instance")!=QJsonValue(_instance) || command.value("operation")!=QJsonValue("replace")
            || QUuid(id).isNull() || QUuid(id).toString(QUuid::WithoutBraces)!=id
            || !integer(command.value("sequence"),sequence) || sequence!=_sequence+1
            || !integer(command.value("observedElapsedMs"),observed) || observed>_clock.elapsed() || _clock.elapsed()-observed>5000
            || !command.value("text").isString() || !overte::e2e::validLoginText(command.value("text").toString())
            || !overte::e2e::accountOriginText(origin)) { return result; }
    _sequence=sequence; // Consume intent before uncertain GUI input.
    const auto token=command.value("fieldToken").toString();QString controlId;
    QQuickItem* target=item("login.username",token);
    if (target) { controlId="login.username"; }
    else { target=item("login.password",token);controlId="login.password"; }
    if (!target || !enabled(target)) { return result; }
    const auto context=_loginReader ? _loginReader() : overte::e2e::LoginUiContext();
    QJsonObject row;overte::e2e::appendLoginControlObservation(row,target,controlId,context);
    if (!context.valid || !row.value("inputReady").toBool()
            || (context.endpoint!=overte::e2e::loginEndpointDigest(origin) && context.endpoint!=overte::e2e::loginEndpointDigest(origin+'/'))
            || overte::e2e::loginControlSource(target,controlId,context)!=_controls.value(controlId).source
            || !overte::e2e::NormalControlUi::ownsPoint(target,target->window(),
                target->mapToScene(QPointF(target->width()/2,target->height()/2)))) { return result; }
    result["performed"]=overte::ui::replaceFocusedField(target,target->window(),command.value("text").toString());
    result["sampleEpochMs"]=static_cast<double>(QDateTime::currentMSecsSinceEpoch());
    return result;
}
#endif

bool NormalUiInput::validRequest(const QJsonObject& command) {
    const auto operation = command.value("operation").toString();
    QSet<QString> expected { "schemaVersion", "commandId", "action", "operation" };
    if (operation == QStringLiteral("edit")) { expected.insert(QStringLiteral("input")); }
    const auto keys = command.keys();
    if (QSet<QString>(keys.begin(), keys.end()) != expected
            || command.value("schemaVersion") != QJsonValue(1)
            || command.value("action") != QJsonValue(QStringLiteral("normal-ui-input"))
            || !QRegularExpression(QStringLiteral("^ios-[0-9a-f]{32}$"))
                .match(command.value("commandId").toString()).hasMatch()
            || QJsonDocument(command).toJson(QJsonDocument::Compact).size() > 32768) { return false; }
    if (operation == QStringLiteral("observe")) { return true; }
    if (operation != QStringLiteral("edit") || !command.value("input").isObject()) { return false; }
    const auto input = command.value("input").toObject();
    const auto action = input.value("operation").toString();
    QSet<QString> inputKeys { "schemaVersion", "commandId", "instance", "sequence",
        "observedElapsedMs", "fieldToken", "operation" };
    if (action == QStringLiteral("replace")) { inputKeys.insert(QStringLiteral("text")); }
    if (action == QStringLiteral("select-index")) { inputKeys.insert(QStringLiteral("index")); }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (action == "scroll") { inputKeys.insert("direction"); }
    if (action == "set-value") { inputKeys.insert("value"); }
#endif
    const auto actual = input.keys();
    qint64 sequence { 0 }, observed { 0 };
    const auto uuid = [](const QJsonValue& value) {
        const auto id = value.toString();
        return !QUuid(id).isNull() && QUuid(id).toString(QUuid::WithoutBraces) == id;
    };
    if (QSet<QString>(actual.begin(), actual.end()) != inputKeys
            || input.value("schemaVersion") != QJsonValue(1)
            || !uuid(input.value("commandId")) || !uuid(input.value("instance"))
            || !uuid(input.value("fieldToken"))
            || !integer(input.value("sequence"), sequence) || sequence < 1
            || !integer(input.value("observedElapsedMs"), observed)) { return false; }
    if (action == QStringLiteral("select-index")) {
        qint64 index { 0 };
        return integer(input.value("index"), index) && index < 32;
    }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (action == "activate" || action == "clear-login-username") { return true; }
    if (action == "scroll") { return input.value("direction") == QJsonValue("up") || input.value("direction") == QJsonValue("down"); }
    if (action == "set-value") { return input.value("value").isDouble() && std::isfinite(input.value("value").toDouble())
        && input.value("value").toDouble() >= 0.1 && input.value("value").toDouble() <= 2.0; }
#endif
    if (action == QStringLiteral("submit")) { return true; }
    if (action != QStringLiteral("replace") || !input.value("text").isString()) { return false; }
    const auto text = input.value("text").toString();
    if (text.size() > 4096) { return false; }
    for (int index = 0; index < text.size(); ++index) {
        const auto character = text.at(index);
        if (character.unicode() < 32 || character.unicode() == 127 || character.isLowSurrogate()) { return false; }
        if (character.isHighSurrogate() && (++index >= text.size() || !text.at(index).isLowSurrogate())) { return false; }
    }
    return true;
}

QJsonObject NormalUiInput::request(const QJsonObject& command) {
    if (!guiThread() || !validRequest(command)) { return {}; }
    const auto operation = command.value("operation").toString();
    QJsonObject result { { "schemaVersion", 1 }, { "commandId", command.value("commandId") } };
    if (operation == QStringLiteral("observe")) { result["observation"] = observe(_hud, _tablet, _tabletShown); }
    else { result["status"] = edit(command.value("input").toObject()); }
    return result;
}

} // namespace overte::ios
