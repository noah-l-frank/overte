// Deterministic avatar assignment used only by the ephemeral E2E domain.
(function () {
    "use strict";

    var elapsed = 0.0;
    var updates = 0;
    var origin = { x: 2.0, y: 0.0, z: 2.0 };
    var chatInputEnabled = typeof Messages !== "undefined" && typeof Messages.featureChatActorInput === "function";
    var chatHeld = null;
    Agent.isListeningToAudioStream = false;
    Agent.isAvatar = true;
    Avatar.displayName = "OVERTE_E2E_PEER";
    Avatar.position = origin;

    function chatInput() {
        if (!chatInputEnabled) return false;
        var command = Messages.featureChatActorInput();
        if (!command || !command.operation) return false;
        // This private native path already admitted a one-shot fixture INPUT.
        // Read actual Avatar.position at the operation, never a requested
        // coordinate copied into an observation or a receive result.
        if (command.operation === "hold") {
            if (chatHeld !== null) return false;
            chatHeld = { position: Avatar.position, elapsed: elapsed };
            Avatar.position = command.position;
        } else if (command.operation === "send") {
            Messages.sendMessage("chat", JSON.stringify({ position: Avatar.position,
                message: command.textKey + "-" + command.runId, displayName: Avatar.displayName,
                channel: command.channel, action: "send_chat_message" }));
        } else if (command.operation === "restore") {
            if (chatHeld === null) return false;
            Avatar.position = chatHeld.position;
            elapsed = chatHeld.elapsed;
            chatHeld = null;
            return true; // Preserve the exact original position for this tick.
        } else if (command.operation === "release" && chatHeld === null) {
            chatInputEnabled = false;
        }
        return false;
    }

    function update(deltaTime) {
        updates += 1;
        if (chatInput() || chatHeld !== null) return;
        elapsed += Number(deltaTime);
        Avatar.position = {
            x: origin.x + 0.75 * Math.sin(elapsed),
            y: origin.y,
            z: origin.z
        };
    }

    function reportState() {
        // The first identity packet can precede the active mixer socket. Keep
        // the real agent identity announced after connection and reconnection;
        // receivers must still independently observe this avatar and movement.
        Avatar.displayName = "OVERTE_E2E_PEER";
        var request = new XMLHttpRequest();
        request.open("POST", Script.resolvePath("peer-state"), true);
        request.setRequestHeader("Content-Type", "application/json");
        request.send(JSON.stringify({ schemaVersion: 1,
            avatarEnabled: Boolean(Agent.isAvatar),
            displayName: String(Avatar.displayName), updates: updates }));
    }

    var reportTimer = Script.setInterval(reportState, 1000);
    Script.update.connect(update);
    Script.scriptEnding.connect(function () {
        chatInputEnabled = false;
        if (chatHeld !== null) {
            Avatar.position = chatHeld.position;
            elapsed = chatHeld.elapsed;
            chatHeld = null;
        }
        Script.clearInterval(reportTimer);
        Script.update.disconnect(update);
        Agent.isAvatar = false;
    });
}());
