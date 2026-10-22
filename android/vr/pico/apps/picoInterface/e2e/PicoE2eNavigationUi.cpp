// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "PicoE2eNavigationUi.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <algorithm>
#include <cmath>
#include <ui/NativeFieldInput.h>
#include "../../../../../../tests/device/native/NormalScriptControls.h"
#include "../../../../../../tests/device/native/NormalScriptFileControls.h"
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include "../../../../../../tests/device/native/ScriptFileUi.h"
#include "../../../../../../tests/device/native/NormalAccountMenuControls.h"
#include "../../../../../../tests/device/native/NormalPlacesControls.h"
#include "../../../../../../tests/device/native/NavigationFailureModals.h"
#include "../../../../../../tests/device/native/NavigationEnvironmentObservation.h"
#include "../../../../../../tests/device/native/NavigationDirectoryBridge.h"
#include "../../../../../../tests/device/native/NavigationPanelsObservation.h"
#include "../../../../../../tests/device/native/FeatureUiInventory.h"
#include "../../../../../../tests/device/native/NormalNavigationAddress.h"
#include "../../../../../../tests/device/native/TabletHttpObservation.h"
#include <AudioClient.h>
#include <AccountManager.h>
#include <Application.h>
#include <scripting/RenderScriptingInterface.h>
#endif

namespace overte::pico::e2e {
namespace {

QString token() { return QUuid::createUuid().toString(QUuid::WithoutBraces); }

bool visible(QQuickItem* item, QQuickWindow* window) {
    if (!item || !window || item->window() != window || !item->isVisible()
            || item->width() <= 0 || item->height() <= 0) { return false; }
    // TextInput's painted boundingRect can be just its empty cursor or glyphs.
    // Native pointer hit targets use the actual control width and height.
    auto rect = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
    const auto center = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
    if (!std::isfinite(rect.x()) || !std::isfinite(rect.y())
            || !std::isfinite(rect.width()) || !std::isfinite(rect.height())
            || !std::isfinite(center.x()) || !std::isfinite(center.y())) { return false; }
    rect = rect.intersected(QRectF(0, 0, window->width(), window->height()));
    for (auto parent = item; parent; parent = parent->parentItem()) {
        if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity() <= 0.01) {
            return false;
        }
        if (parent->clip()) {
            if (!parent->clipRect().contains(parent->mapFromScene(center))) { return false; }
            rect = rect.intersected(parent->mapRectToScene(parent->clipRect()));
        }
    }
    return !rect.isEmpty() && rect.contains(center);
}

bool enabled(QQuickItem* item) {
    const auto explicitEnabled = item->property("buttonEnabled");
    return item->isEnabled() && (!explicitEnabled.isValid() || explicitEnabled.toBool());
}

QString controlId(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
#if defined(ANDROID_APP_PICO_INTERFACE)
    const auto navigationError=overte::e2e::navigationFailureModals().controlId(item);
    if (!navigationError.isEmpty()) { return navigationError; }
    const auto places = overte::e2e::placesControlId(item);
    if (!places.isEmpty()) { return places; }
#endif
    const auto chat=overte::e2e::chatControlId(item);
    if (!chat.isEmpty()) { return chat; }
    const auto create=overte::e2e::createControlId(item);
    if (!create.isEmpty()) { return create; }
    const auto graphics = overte::e2e::graphicsControlId(item);
    if (!graphics.isEmpty()) { return graphics; }
    const auto audio = overte::e2e::audioControlId(item);
    if (!audio.isEmpty()) { return audio; }
    const auto accountMenu=overte::e2e::accountMenuControlId(item);
    if (!accountMenu.isEmpty()) { return accountMenu; }
    const auto login=overte::e2e::loginControlId(item);
    if (!login.isEmpty()) { return login; }
#endif
    const auto file = overte::e2e::scriptFileControlId(item);
    if (!file.isEmpty()) { return file; }
    const auto script = overte::e2e::scriptControlId(item);
    if (!script.isEmpty()) { return script; }
    static const QHash<QString, QString> names {
        { "tabletAddressLine", "navigation.address" },
        { "tabletAddressBack", "navigation.back" },
        { "tabletAddressForward", "navigation.forward" },
        { "nav.home", "tablet.home" },
        { "snapshotName", "snapshot.name" },
        { "snapshotMode", "snapshot.mode" },
        { "snapshotFormat", "snapshot.format" },
        { "snapshotCapture", "snapshot.capture" },
        { "snapshotCancelCapture", "snapshot.cancel" },
    };
    const auto name = item->objectName();
    if (names.contains(name)) { return names.value(name); }
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
    for (int page = 1; page <= 32; ++page) {
        if (name == QStringLiteral("tabletPage.%1").arg(page)) {
            return QStringLiteral("tablet.page.%1").arg(page);
        }
    }
    // Match the actual TabletButton, never its child caption Text item.
    if (item->metaObject()->indexOfSignal("clicked()") >= 0) {
        const auto caption = item->property("text").toString();
        if (caption == QStringLiteral("GOTO")) { return QStringLiteral("navigation.goto"); }
        if (caption == QStringLiteral("SNAP")) { return QStringLiteral("snapshot.entry"); }
    }
    return {};
}

bool integer(const QJsonValue& value, qint64& output) {
    if (!value.isDouble()) { return false; }
    const double number = value.toDouble();
    if (!std::isfinite(number) || number < 0 || number > 9007199254740991.0
            || std::floor(number) != number) { return false; }
    output = static_cast<qint64>(number);
    return true;
}

bool exactKeys(const QJsonObject& object, const QSet<QString>& expected) {
    const auto keys = object.keys();
    return QSet<QString>(keys.begin(), keys.end()) == expected;
}

} // namespace

NavigationUi::NavigationUi() : _bridgeId(token()), _generation(token()) { _clock.start(); }

QJsonObject NavigationUi::observe(QQuickItem* root, QQuickWindow* window, bool open) {
    // This object belongs to the GUI timer. Reject foreign-thread calls before
    // reading the scene graph, including otherwise valid stale pointers.
    const bool gui = qApp && QThread::currentThread() == qApp->thread();
    if (!gui) { return {}; }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    // Observe roots at the original normal-control read before a possible
    // close/replacement, even if no passive publisher has polled yet.
    overte::e2e::graphicsUiInventory().observe(root,window);
    overte::e2e::ensureTabletHttpProvider(root);
#endif
    if (_root != root || _window != window || _open != open) {
        _generation = token();
        _controls.clear();
        _root = root;
        _window = window;
        _open = open;
    }
    bool ready = open && root && window && root->thread() == qApp->thread()
        && window->thread() == qApp->thread() && root->window() == window;
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
    overte::e2e::navigationFailureModals().observeRoot(root,window,open,_bridgeId,_generation,_lastCommandSequence,_clock.elapsed());
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
    overte::e2e::GraphicsUiContext graphicsContext;
    if (QCoreApplication::arguments().contains("--testScript")) {
        auto render = RenderScriptingInterface::getInstance();
        graphicsContext = overte::e2e::GraphicsUiContext::fromNative(render->getViewportResolutionScale(),
            render->getHazeEnabled(),render->getMirrorsEnabled());
    }
    overte::e2e::AudioUiContext audioContext;
    if (DependencyManager::isSet<AudioClient>() && QCoreApplication::arguments().contains("--testScript")) {
        const auto audio = DependencyManager::get<AudioClient>();
        QVariantMap voice; bool muted {false}, echo {false};
        const auto read = [&] { voice = audio->featureRecordedVoiceObservation(); muted = audio->isMuted(); echo = audio->getLocalEcho(); };
        bool readOkay {true};
        if (QThread::currentThread() == audio->thread()) { read(); }
        else { readOkay = QMetaObject::invokeMethod(audio.data(), read, Qt::BlockingQueuedConnection); }
        if (readOkay) { audioContext = overte::e2e::AudioUiContext::fromNative(voice, muted, echo, qApp->isHMDMode()); }
    }
#endif
#if defined(OVERTE_E2E_FEATURE_TESTS)
    overte::e2e::LoginUiContext loginContext;
    overte::e2e::AccountMenuUiContext accountMenuContext;
    if (DependencyManager::isSet<AccountManager>() && QCoreApplication::arguments().contains("--testScript")) {
        const auto account=DependencyManager::get<AccountManager>();QVariantMap original;
        const auto read=[&] { original=account->featureAccountObservation(); };
        bool okay {true};
        if (QThread::currentThread()==account->thread()) { read(); }
        else { okay=QMetaObject::invokeMethod(account.data(),read,Qt::BlockingQueuedConnection); }
        if (okay) {
            loginContext=overte::e2e::LoginUiContext::fromNative(original);
            accountMenuContext=overte::e2e::AccountMenuUiContext::fromNative(original);
        }
    }
#endif
    QHash<QString, Control> controls;
    bool ambiguous { false };
    int count { 0 };
    std::function<void(QQuickItem*, int)> walk = [&](QQuickItem* item, int depth) {
        if (!item || ambiguous) { return; }
        if (++count > 4096 || depth > 128) { ambiguous = true; return; }
        if (visible(item, window)
#if defined(OVERTE_E2E_FEATURE_TESTS)
                || overte::e2e::graphicsObservable(item)
#endif
                ) {
            const auto id = controlId(item);
            if (!id.isEmpty()) {
                if (controls.contains(id)) { ambiguous = true; return; }
                const auto previous = _controls.value(id);
                const auto fileSource = overte::e2e::scriptFileControlSource(item);
                auto source = fileSource.isEmpty() ? overte::e2e::scriptRowSource(item) : fileSource;
#if defined(OVERTE_E2E_FEATURE_TESTS)
#if defined(ANDROID_APP_PICO_INTERFACE)
                if (id.startsWith("navigation.error.ok.")) {
                    source=overte::e2e::navigationFailureModals().controlSource(item,id);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (id.startsWith("places.")) {
                    source=overte::e2e::placesControlSource(item,id);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else
#endif
                if (id=="navigation.address") {
                    source=overte::e2e::navigationLookupControlSource(item,id);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (id=="navigation.goto" || id.startsWith("tablet.page.")) {
                    source=overte::e2e::navigationLookupControlSource(item,id);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (id.startsWith("chat.")) {
                    source=overte::e2e::chatControlSource(item,id);
                    if (source.isEmpty()) { ambiguous=true;return; }
                } else if (id.startsWith("create.")) {
                    source=overte::e2e::createControlSource(item,id);
                } else if (id.startsWith("account-menu.")) {
                    if (!accountMenuContext.login.valid) { return; }
                    source=overte::e2e::accountMenuSource(item,id,accountMenuContext);
                } else if (id.startsWith("login.")) {
                    if (!loginContext.valid) { return; }
                    source=overte::e2e::loginControlSource(item,id,loginContext);
                } else if (id.startsWith("graphics.") || (id == "settings.entry" && graphicsContext.valid)) {
                    if (!graphicsContext.valid) { return; }
                    source = overte::e2e::graphicsControlSource(item,id,graphicsContext);
                } else if (id.startsWith("audio.") || id == "settings.entry") {
                    if (!audioContext.valid) { return; }
                    source = overte::e2e::audioControlSource(item, id, audioContext);
                }
#endif
                controls.insert(id, { item, previous.item == item && previous.source == source ? previous.token : token(), source });
            }
        }
        const auto children = item->childItems();
        for (auto child : children) { walk(child, depth + 1); }
    };
    if (ready) {
        walk(root, 0);
        // Controls popups are rendered in this window's Qt overlay beside the
        // complete tablet root. Never discover arbitrary or foreign siblings.
        if (root->parentItem() == window->contentItem()) {
            for (auto layer : window->contentItem()->childItems()) {
                if (layer != root && layer->inherits("QQuickOverlay")) { walk(layer, 0); }
            }
        }
    }
    if (controls.contains(QStringLiteral("scripts.url.field"))) {
        for (const auto& id : controls.keys()) {
            if (!id.startsWith(QStringLiteral("scripts.url."))) { controls.remove(id); }
        }
    }
    bool filePicker {false};
    for (const auto& id : controls.keys()) { filePicker = filePicker || id.startsWith(QStringLiteral("script-file.")); }
    if (filePicker) {
        for (const auto& id : controls.keys()) {
            if (!id.startsWith(QStringLiteral("script-file."))) { controls.remove(id); }
        }
    }
    if (ambiguous || !ready || controls.size() > 384) { controls.clear(); ready = false; }
    _controls = controls;
    auto ids = controls.keys();
    std::sort(ids.begin(), ids.end());
    QJsonArray observed;
    for (const auto& id : ids) {
        const auto control = controls.value(id);
        QJsonObject row { { "id", id }, { "token", control.token },
            { "enabled", enabled(control.item) }, { "focused", control.item->hasActiveFocus() } };
        if (id.startsWith(QStringLiteral("snapshot.mode.")) || id.startsWith(QStringLiteral("snapshot.format."))) {
            row["checked"] = control.item->property("checked").toBool();
        }
        overte::e2e::appendScriptControlObservation(row, control.item, id);
        overte::e2e::appendScriptFileObservation(row, control.item, id);
#if defined(OVERTE_E2E_FEATURE_TESTS)
#if defined(ANDROID_APP_PICO_INTERFACE)
        if (id.startsWith("navigation.error.ok.")) {
            overte::e2e::navigationFailureModals().appendControl(row,control.item,id);
        } else if (id.startsWith("places.")) {
            overte::e2e::appendPlacesObservation(row,control.item,id);
        } else
#endif
        if (id=="navigation.address") {
            const auto original=overte::e2e::navigationAddressObservation(control.item);
            for (auto item=original.begin();item!=original.end();++item) { row[item.key()]=item.value(); }
        } else if (id.startsWith("chat.")) {
            overte::e2e::appendChatControlObservation(row,control.item,id);
        } else if (id.startsWith("create.")) {
            overte::e2e::appendCreateControlObservation(row,control.item,id);
        } else if (id.startsWith("account-menu.")) {
            overte::e2e::appendAccountMenuObservation(row,control.item,id,accountMenuContext);
        } else if (id.startsWith("login.")) {
            overte::e2e::appendLoginControlObservation(row,control.item,id,loginContext);
        } else if (id.startsWith("graphics.") || (id == "settings.entry" && graphicsContext.valid)) {
            overte::e2e::appendGraphicsControlObservation(row,control.item,id,graphicsContext);
        } else if (id.startsWith("audio.") || id == "settings.entry") {
            overte::e2e::appendAudioControlObservation(row, control.item, id, audioContext);
        }
#endif
        observed.append(row);
    }
    QJsonObject result { { "schemaVersion", 1 }, { "bridgeId", _bridgeId }, { "generation", _generation },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) },
        { "elapsedMs", static_cast<double>(_clock.elapsed()) },
        { "updatedEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch()) },
        { "lastCommandSequence", static_cast<double>(_lastCommandSequence) },
        { "open", open }, { "ready", ready }, { "controls", observed } };
#if defined(OVERTE_E2E_FEATURE_TESTS)
    result["featureControlsVersion"] = 1;
    result["createControlsVersion"] = 1;
    result["chatControlsVersion"] = 2;
    result["fileControlsVersion"] = 1;
    if (audioContext.valid) { result["audioControlsVersion"] = 1; }
    if (graphicsContext.valid) { result["graphicsControlsVersion"] = 1; }
    if (loginContext.valid) { result["loginControlsVersion"]=2; }
    if (accountMenuContext.login.valid) { result["accountMenuControlsVersion"]=1; }
    result["navigationAddressVersion"]=1;
#if defined(ANDROID_APP_PICO_INTERFACE)
    result["placesControlsVersion"]=1;
    result["navigationErrorControlsVersion"]=1;
    result["navigationOriginControlsVersion"]=1;
    result["navigationLookupControlsVersion"]=1;
    overte::e2e::navigationPanelsObservation().observe(root,window,result);
    overte::e2e::navigationEnvironmentObservation().observe(result,controls.value("login.server").item,controls.value("login.page").item);
    const auto directoryProvider=overte::e2e::navigationDirectoryProvider();
    if (directoryProvider.watch) { directoryProvider.watch(controls.value("places.page").item,result); }
#endif
#endif
    return result;
}

QJsonObject NavigationUi::apply(QQuickItem* root, QQuickWindow* window, bool open,
                               const QJsonObject& command,
                               const std::function<bool(QQuickItem*)>& pointerClick,
                               const std::function<bool(QQuickItem*, const QPointF&)>& pointerAt) {
    if (!qApp || QThread::currentThread() != qApp->thread()) { return {}; }
    const auto current = observe(root, window, open);
    const auto id = command.value("commandId").toString();
    QJsonObject result { { "schemaVersion", 1 }, { "bridgeId", _bridgeId },
        { "commandId", id }, { "sequence", command.value("sequence") },
        { "performed", false }, { "error", QStringLiteral("invalid-command") },
        { "processId", static_cast<double>(QCoreApplication::applicationPid()) },
        { "updatedEpochMs", static_cast<double>(QDateTime::currentMSecsSinceEpoch()) } };
    const auto action = command.value("action").toString();
    QSet<QString> expected { "schemaVersion", "commandId", "bridgeId", "generation",
        "sequence", "observedElapsedMs", "controlId", "controlToken", "action" };
    if (action == "replace") { expected.insert("text"); }
    if (action == "select-index") { expected.insert("index"); }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if (action == "scroll") { expected.insert("direction"); }
    if (action == "set-value") { expected.insert("value"); }
#endif
    qint64 sequence { 0 }, observedAt { 0 };
    const auto uuid = QUuid(id);
    if (!exactKeys(command, expected) || command.value("schemaVersion") != QJsonValue(1)
            || uuid.isNull() || uuid.toString(QUuid::WithoutBraces) != id
            || !integer(command.value("sequence"), sequence)
            || sequence != _lastCommandSequence + 1
            || command.value("bridgeId") != QJsonValue(_bridgeId)
            || command.value("generation") != QJsonValue(_generation)
            || !integer(command.value("observedElapsedMs"), observedAt)
            || observedAt > _clock.elapsed() || _clock.elapsed() - observedAt > 5000
            || (action != "activate" && action != "replace" && action != "submit" && action != "select-index"
#if defined(OVERTE_E2E_FEATURE_TESTS)
                && action != "scroll" && action != "set-value"
#endif
                )) { return result; }
    // Consume an admitted sequence before any input. An uncertain result may
    // be read again but can never replay a pointer/key/IME mutation.
    _lastCommandSequence = sequence;
    const auto controlId = command.value("controlId").toString();
    const auto control = _controls.value(controlId);
    if (!current.value("ready").toBool() || !control.item
            || command.value("controlToken") != QJsonValue(control.token)
            || !enabled(control.item) || !visible(control.item, window)) {
        result["error"] = QStringLiteral("control-unavailable");
        return result;
    }
    bool delivered { false };
#if defined(OVERTE_E2E_FEATURE_TESTS)
#if defined(ANDROID_APP_PICO_INTERFACE)
    if (controlId.startsWith("navigation.error.ok.")) {
        QJsonObject row;overte::e2e::navigationFailureModals().appendControl(row,control.item,controlId);
        const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
        if (current.value("navigationErrorControlsVersion")==QJsonValue(1) && row.value("inputReady").toBool()
                && action=="activate" && pointerClick && overte::e2e::NormalControlUi::ownsPoint(control.item,window,point)) {
            delivered=pointerClick(control.item);
        }
    } else if (controlId.startsWith("places.")) {
        QJsonObject row;overte::e2e::appendPlacesObservation(row,control.item,controlId);
        if (current.value("placesControlsVersion")!=QJsonValue(1) || !row.value("inputReady").toBool()) { return result; }
        const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
        if (!overte::e2e::NormalControlUi::ownsPoint(control.item,window,point)) { return result; }
        if (action=="activate" && controlId!="places.page" && !controlId.startsWith("places.scroll.") && pointerClick) {
            delivered=pointerClick(control.item);
        } else if (action=="replace" && overte::e2e::placesField(controlId) && command.value("text").isString()
                && overte::e2e::placesText(command.value("text").toString())) {
            delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
        } else if (action=="scroll" && controlId.startsWith("places.scroll.") && pointerAt) {
            QPointF scrollPoint;
            if (overte::e2e::placesScrollPoint(control.item,command.value("direction").toString(),scrollPoint)
                    && overte::e2e::NormalControlUi::ownsPoint(control.item,window,scrollPoint)) { delivered=pointerAt(control.item,scrollPoint); }
        }
    } else
#endif
    if (controlId.startsWith("account-menu.")) {
        const auto rows=current.value("controls").toArray();bool ready {false};
        for (const auto& value:rows) {
            const auto row=value.toObject();
            if (row.value("id")==QJsonValue(controlId)) { ready=row.value("inputReady").toBool(); }
        }
        const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
        if (current.value("accountMenuControlsVersion")==QJsonValue(1) && ready && action=="activate"
                && pointerClick && overte::e2e::NormalControlUi::ownsPoint(control.item,window,point)) { delivered=pointerClick(control.item); }
    } else if (controlId.startsWith("chat.")) {
        QJsonObject row;overte::e2e::appendChatControlObservation(row,control.item,controlId);
        if (current.value("chatControlsVersion")!=QJsonValue(2) || !row.value("inputReady").toBool()) { return result; }
        const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
        if (action=="activate" && controlId!="chat.page" && pointerClick
                && overte::e2e::NormalControlUi::ownsPoint(control.item,window,point)) { delivered=pointerClick(control.item); }
        else if (controlId=="chat.input" && action=="replace" && command.value("text").isString()
                && overte::e2e::chatText(command.value("text").toString())
                && overte::e2e::NormalControlUi::ownsPoint(control.item,window,point)) {
            delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
        } else if (controlId=="chat.input" && action=="submit") {
            delivered=overte::ui::submitFocusedField(control.item,window);
        }
    } else if (controlId.startsWith("create.")) {
        QJsonObject row;overte::e2e::appendCreateControlObservation(row,control.item,controlId);
        if (current.value("createControlsVersion")!=QJsonValue(1) || !row.value("inputReady").toBool()) { return result; }
        const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
        if (action=="activate" && controlId!="create.page" && controlId!="create.scrollbar" && pointerClick
                && overte::e2e::NormalControlUi::ownsPoint(control.item,window,point)) { delivered=pointerClick(control.item); }
        else if (action=="replace" && overte::e2e::createField(controlId) && command.value("text").isString()
                && overte::e2e::createText(command.value("text").toString())
                && overte::e2e::NormalControlUi::ownsPoint(control.item,window,point)) {
            delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
        } else if (action=="select-index" && overte::e2e::createChoice(controlId)) {
            qint64 index{0};if (integer(command.value("index"),index)) {
                delivered=overte::e2e::NormalControlUi::selectCreateChoice(control.item,window,index);
            }
        } else if (action=="scroll" && controlId=="create.scrollbar") {
            QPointF scrollPoint;
            if (overte::e2e::createScrollPoint(control.item,command.value("direction").toString(),scrollPoint)
                    && overte::e2e::NormalControlUi::ownsPoint(control.item,window,scrollPoint) && pointerAt) { delivered=pointerAt(control.item,scrollPoint); }
        }
    } else if (controlId.startsWith("login.")) {
        QJsonObject row;
        for (const auto& value:current.value("controls").toArray()) {
            const auto candidate=value.toObject();if (candidate.value("id").toString()==controlId) { row=candidate; }
        }
        if (current.value("loginControlsVersion")!=QJsonValue(2) || !row.value("inputReady").toBool()) { return result; }
        if (action=="activate" && controlId!="login.page") {
            const auto point=control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
            if (overte::e2e::NormalControlUi::ownsPoint(control.item,window,point) && pointerClick) { delivered=pointerClick(control.item); }
        } else if (action=="replace" && (controlId=="login.username" || controlId=="login.password" || controlId=="login.server")
                && command.value("text").isString() && overte::e2e::validLoginText(command.value("text").toString())) {
            delivered=overte::ui::replaceFocusedField(control.item,window,command.value("text").toString());
        } else if (action=="submit" && (controlId=="login.password"
#if defined(ANDROID_APP_PICO_INTERFACE)
                || controlId=="login.server" && current.value("navigationOriginControlsVersion")==QJsonValue(1)
#endif
                )) {
            delivered=overte::ui::submitFocusedField(control.item,window);
        }
    } else if (controlId.startsWith("graphics.") || (controlId == "settings.entry" && current.contains("graphicsControlsVersion"))) {
        QJsonObject row;
        for (const auto& value : current.value("controls").toArray()) {
            const auto candidate = value.toObject(); if (candidate.value("id").toString() == controlId) { row = candidate; }
        }
        if (!row.value("inputReady").toBool()) { return result; }
        QPointF point;
        if (action == "set-value" && controlId == "graphics.resolution" && command.value("value").isDouble()) {
            if (overte::e2e::graphicsSliderPoint(control.item,command.value("value").toDouble(),point)
                    && overte::e2e::NormalControlUi::ownsPoint(control.item,window,point) && pointerAt) {
                delivered = pointerAt(control.item,point);
            }
        } else if (action == "scroll" && controlId == "graphics.scrollbar") {
            if (overte::e2e::graphicsScrollPoint(control.item,command.value("direction").toString(),point)
                    && overte::e2e::NormalControlUi::ownsPoint(control.item,window,point) && pointerAt) {
                delivered = pointerAt(control.item,point);
            }
        } else if (action == "activate" && controlId != "graphics.page" && controlId != "graphics.scrollbar" && controlId != "graphics.resolution") {
            point = control.item->mapToScene(QPointF(control.item->width()/2,control.item->height()/2));
            if (overte::e2e::NormalControlUi::ownsPoint(control.item,window,point) && pointerClick) { delivered = pointerClick(control.item); }
        }
    } else if (controlId.startsWith("audio.") || controlId == "settings.entry") {
        QJsonObject row;
        for (const auto& value : current.value("controls").toArray()) {
            const auto candidate = value.toObject(); if (candidate.value("id").toString() == controlId) { row = candidate; }
        }
        if (!row.value("inputReady").toBool()) { return result; }
        if (action == "scroll" && controlId == "audio.scrollbar") {
            QPointF point;
            if (overte::e2e::audioScrollPoint(control.item, command.value("direction").toString(), point)
                    && overte::e2e::NormalControlUi::ownsPoint(control.item, window, point) && pointerAt) {
                delivered = pointerAt(control.item, point);
            }
        } else if (action == "activate" && controlId != "audio.page" && controlId != "audio.scrollbar") {
            const auto point = control.item->mapToScene(QPointF(control.item->width()/2, control.item->height()/2));
            if (overte::e2e::NormalControlUi::ownsPoint(control.item, window, point) && pointerClick) { delivered = pointerClick(control.item); }
        }
    } else
#endif
    if (action == "activate") {
        delivered = pointerClick && pointerClick(control.item);
#if defined(OVERTE_E2E_FEATURE_TESTS)
    } else if (controlId == QStringLiteral("script-file.folder")) {
        if (action == "replace" && command.value("text").isString()
                && overte::e2e::validScriptFolderPath(command.value("text").toString())) {
            delivered = overte::ui::replaceFocusedField(control.item, window, command.value("text").toString());
        } else if (action == "submit") {
            delivered = overte::ui::submitFocusedField(control.item, window);
        }
    } else if (controlId == QStringLiteral("script-file.primary") && action == "select-index") {
        qint64 index {0};
        if (integer(command.value("index"), index)) {
            delivered = overte::e2e::ScriptFileUi::selectFocusedPrimary(control.item, window, index);
        }
#endif
    } else if (controlId == QStringLiteral("navigation.address")) {
        if (action == "replace" && command.value("text").isString()) {
            delivered = overte::ui::replaceFocusedField(control.item, window, command.value("text").toString());
        } else if (action == "submit") {
            delivered = overte::ui::submitFocusedField(control.item, window);
        }
    } else if (controlId == QStringLiteral("scripts.url.field") && action == "replace"
            && command.value("text").isString()
            && overte::e2e::validScriptUrlText(command.value("text").toString())) {
        delivered = overte::ui::replaceFocusedField(control.item, window, command.value("text").toString());
    } else if (controlId == QStringLiteral("snapshot.name") && action == "replace"
            && command.value("text").isString()) {
        const auto text = command.value("text").toString();
        static const QRegularExpression ownedName {
            QStringLiteral("\\Aparity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)\\z") };
        if (text.size() <= 48 && ownedName.match(text).hasMatch()) {
            delivered = overte::ui::replaceFocusedField(control.item, window, text);
        }
    }
    result["performed"] = delivered;
    result["error"] = delivered ? QString() : QStringLiteral("input-delivery-failed");
    return result;
}

} // namespace overte::pico::e2e
