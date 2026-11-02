import QtQuick 2.0
import Hifi 1.0

import "../../dialogs"
import "../../controls"
import stylesUit 1.0

Rectangle {
    HifiConstants { id: hifi; }
    id: tabletRoot
    objectName: "tabletRoot"
    color: hifi.colors.baseGray
    property string username: "Unknown user"
    property string usernameShort: "Unknown user"
    property var rootMenu;
    property var openModal: null;
    property var openMessage: null;
    property var openBrowser: null;
    property string subMenu: ""
    signal showDesktop();
    signal screenChanged(var type, var url);
    property bool shown: true
    property int currentApp: -1;
    property alias tabletApps: tabletApps
    property var _inlineSources: ({})
    property var _webLoadTicket: null
    property var _activeInlineSource: null

    function _suspendInlineSource() {
        if (_activeInlineSource) { _activeInlineSource.suspend(); }
        _activeInlineSource = null;
    }
    Component.onDestruction: _retireInlineSources()

    function _retireInlineSources() {
        _webLoadTicket = {};
        _suspendInlineSource();
        Object.keys(_inlineSources).forEach(function(identity) {
            var source = _inlineSources[identity];
            if (source) { source.retire(); }
        });
        _inlineSources = ({});
    }

    function setOption(value) {
        option = value;
    }

    Component { id: inputDialogBuilder; TabletQueryDialog { } }
    function inputDialog(properties) {
        openModal = inputDialogBuilder.createObject(tabletRoot, properties);
        return openModal;
    }
    Component { id: messageBoxBuilder; TabletMessageBox { } }
    function messageBox(properties) {
        openMessage  = messageBoxBuilder.createObject(tabletRoot, properties);
        return openMessage;
    }

    function customInputDialog(properties) {
        // These optional dialogs still transitively depend on Qt 5-era QML in
        // parts of the tree. Load them only when requested so one unavailable
        // dialog cannot invalidate TabletRoot and every unrelated tablet app.
        var customInputDialogBuilder = Qt.createComponent("../../dialogs/TabletCustomQueryDialog.qml");
        if (customInputDialogBuilder.status !== Component.Ready) {
            console.warn("Unable to load TabletCustomQueryDialog: " + customInputDialogBuilder.errorString());
            return null;
        }
        openModal = customInputDialogBuilder.createObject(tabletRoot, properties);
        return openModal;
    }

    function fileDialog(properties) {
        var fileDialogBuilder = Qt.createComponent("../../dialogs/TabletFileDialog.qml");
        if (fileDialogBuilder.status !== Component.Ready) {
            console.warn("Unable to load TabletFileDialog: " + fileDialogBuilder.errorString());
            return null;
        }
        openModal = fileDialogBuilder.createObject(tabletRoot, properties);
        return openModal;
    }

    function assetDialog(properties) {
        var assetDialogBuilder = Qt.createComponent("../../dialogs/TabletAssetDialog.qml");
        if (assetDialogBuilder.status !== Component.Ready) {
            console.warn("Unable to load TabletAssetDialog: " + assetDialogBuilder.errorString());
            return null;
        }
        openModal = assetDialogBuilder.createObject(tabletRoot, properties);
        return openModal;
    }

    function setMenuProperties(rootMenu, subMenu) {
        tabletRoot.rootMenu = rootMenu;
        tabletRoot.subMenu = subMenu;
    }

    function isDialogOpen() {
        if (openMessage !== null || openModal !== null) {
            return true;
        }

        return false;
    }

    function closeDialog() {
        if (openMessage != null) {
            openMessage.destroy();
            openMessage = null;
        }

        if (openModal != null) {
            openModal.destroy();
            openModal = null;
        }
    }

    function isUrlLoaded(url) {
        if (currentApp >= 0) {
            var currentAppUrl = tabletApps.get(currentApp).appUrl;
            if (currentAppUrl === url) {
                return true;
            }
        }
        return false;
    }

    function loadSource(url) {
        _retireInlineSources();
        tabletApps.clear();
        tabletApps.append({"appUrl": url, "isWebUrl": false, "scriptUrl": "", "appWebUrl": "", "inlineIdentity": ""});
        loader.load(url)
    }

    function loadQMLOnTop(url) {
        if (!isUrlLoaded(url)) {
            _webLoadTicket = {};
            _suspendInlineSource();
            tabletApps.append({"appUrl": url, "isWebUrl": false, "scriptUrl": "", "appWebUrl": "", "inlineIdentity": ""});
            loader.load(tabletApps.get(currentApp).appUrl, function(){
	            if (loader.item.hasOwnProperty("gotoPreviousApp")) {
	                loader.item.gotoPreviousApp = true;
	            }

                if (loader.item.hasOwnProperty("gotoPreviousAppFromScript")) {
                    loader.item.gotoPreviousAppFromScript = true;
                }
            });
        }
    }

    function loadWebContent(source, url, injectJavaScriptUrl, nativeSource, restoring) {
        _suspendInlineSource();
        _activeInlineSource = nativeSource || null;
        var ticket = {};
        _webLoadTicket = ticket;
        var identity = nativeSource ? nativeSource.sourceIdentity : "";
        if (!restoring) {
            tabletApps.append({"appUrl": source, "isWebUrl": true, "scriptUrl": injectJavaScriptUrl,
                               "appWebUrl": url, "inlineIdentity": identity});
            if (identity.length) { _inlineSources[identity] = nativeSource; }
        }
        loader.load(source, function() {
            // The native surface may invoke this callback before visual
            // parenting and completeCreate. Wait for real ancestry, while the
            // page URL remains empty and cannot create a native navigation.
            Qt.callLater(function() {
                if (_webLoadTicket !== ticket) { return; }
                if (nativeSource && loader.item.hasOwnProperty("inlineDocument")) {
                    loader.item.sourceIdentity = nativeSource.sourceIdentity;
                    if (nativeSource.bind(loader.item)) {
                        loader.item.inlineDocument = Qt.binding(function() { return nativeSource.document; });
                    }
                }
                loader.item.scriptURL = injectJavaScriptUrl;
                loader.item.url = url;
                if (loader.item.hasOwnProperty("gotoPreviousApp")) {
                    loader.item.gotoPreviousApp = true;
                }
                screenChanged("Web", url)
            });
        });
    }

    function loadWebBase(url, injectJavaScriptUrl, nativeSource) {
        loadWebContent("hifi/tablet/TabletWebView.qml", url, injectJavaScriptUrl, nativeSource, false);
    }

    function loadTabletWebBase(url, injectJavaScriptUrl, nativeSource) {
        loadWebContent("hifi/tablet/BlocksWebView.qml", url, injectJavaScriptUrl, nativeSource, false);
    }

    function returnToPreviousApp() {
        if (currentApp < 0) { return; }
        _webLoadTicket = {};
        _suspendInlineSource();
        var oldIdentity = tabletApps.get(currentApp).inlineIdentity;
        if (oldIdentity && _inlineSources[oldIdentity]) {
            _inlineSources[oldIdentity].retire();
            delete _inlineSources[oldIdentity];
        }
        tabletApps.remove(currentApp);
        if (currentApp < 0) { loadSource("hifi/tablet/TabletHome.qml"); return; }
        var isWebPage = tabletApps.get(currentApp).isWebUrl;
        if (isWebPage) {
            var previous = tabletApps.get(currentApp);
            loadWebContent(previous.appUrl, previous.appWebUrl, previous.scriptUrl,
                           _inlineSources[previous.inlineIdentity], true);
        } else {
        	loader.load(tabletApps.get(currentApp).appUrl);
        }
    }

    function openBrowserWindow(request, profile) {
        var component = Qt.createComponent("../../controls/TabletWebView.qml");
        var newWindow = component.createObject(tabletRoot);
        newWindow.remove = true;
        newWindow.profile = profile;
        request.openIn(newWindow.webView);
        tabletRoot.openBrowser = newWindow;
    }

    // used to send a message from qml to interface script.
    signal sendToScript(var message);

    // used to receive messages from interface script
    function fromScript(message) {
        if (loader.item.hasOwnProperty("fromScript")) {
            loader.item.fromScript(message);
        }
    }

    SoundEffect {
        id: buttonClickSound
        volume: 0.1
        source: "../../../sounds/Gamemaster-Audio-button-click.wav"
    }

    function playButtonClickSound() {
        // Because of the asynchronous nature of initalization, it is possible for this function to be
        // called before the C++ has set the globalPosition context variable.
        if (typeof globalPosition !== 'undefined') {
            buttonClickSound.play(globalPosition);
        }
    }

    function setUsername(newUsername) {
        username = newUsername;
        usernameShort = newUsername.substring(0, 14);

        if (newUsername.length > 14) {
             usernameShort = usernameShort + "..."
        }
    }

    ListModel {
        id: tabletApps
        onCountChanged: {
            currentApp = count - 1
        }
    }

    // Hook up callback for clara.io download from the marketplace.
    Connections {
        id: eventBridgeConnection
        target: eventBridge
        function onWebEventReceived(message) {
            if (typeof message === "string" && message.slice(0, 17) === "CLARA.IO DOWNLOAD") {
                ApplicationInterface.addAssetToWorldFromURL(message.slice(18));
            }
        }
    }

	Item {
		id: loader
        objectName: "loader";
        anchors.fill: parent;
    	property string source: "";
    	property var item: null;
        property var loadTicket: null;
    	signal loaded;

		onWidthChanged: {
    		if (loader.item) {
	        	loader.item.width = loader.width;
    		}
		}

    	onHeightChanged: {
    		if (loader.item) {
	        	loader.item.height = loader.height;
    		}
		}

    	function load(newSource, callback) {
            var ticket = {};
            loader.loadTicket = ticket;
            loader.source = newSource;

            if (loader.item) {
                loader.item.destroy();
                loader.item = null;
            }

	        QmlSurface.load(newSource, loader, function(newItem) {
                if (loader.loadTicket !== ticket) {
                    if (newItem) { newItem.destroy(); }
                    return;
                }
                if (!newItem) { return; }
	        	loader.item = newItem;
	        	loader.item.width = loader.width;
	        	loader.item.height = loader.height;
	        	loader.loaded();
	            if (loader.item.hasOwnProperty("sendToScript")) {
	                loader.item.sendToScript.connect(tabletRoot.sendToScript);
	            }
	            if (loader.item.hasOwnProperty("setRootMenu")) {
	                loader.item.setRootMenu(tabletRoot.rootMenu, tabletRoot.subMenu);
	            }
                Qt.callLater(function() {
                    if (loader.item === newItem) { newItem.forceActiveFocus(); }
                });

	            if (openModal) {
	                openModal.canceled();
	                openModal.destroy();
	                openModal = null;
	            }

	            if (openBrowser) {
	                openBrowser.destroy();
	                openBrowser = null;
	            }

	            if (callback) {
	            	callback();
	            }

                var type = "Unknown";
                if (newSource === "") {
                    type = "Closed";
                } else if (newSource === "hifi/tablet/TabletMenu.qml") {
                    type = "Menu";
                } else if (newSource === "hifi/tablet/TabletHome.qml") {
                    type = "Home";
                } else if (newSource === "hifi/tablet/TabletWebView.qml") {
                    // Handled in `callback()`
                    return;
                } else if (newSource.toLowerCase().indexOf(".qml") > -1) {
                    type = "QML";
                } else {
                    console.log("newSource is of unknown type!");
                }

                screenChanged(type, newSource);
	        });
    	}
	}

    width: 480
    height: 706

    function setShown(value) {
        if (value === false) { _retireInlineSources(); }
        if (typeof HMD === "undefined" || !HMD) {
            return
        }
        if (value === true) {
            HMD.openTablet(HMD.tabletContextualMode) // pass in current contextual mode flag to maintain flag (otherwise uses default false argument)
        } else {
            HMD.closeTablet()
        }
    }
}
