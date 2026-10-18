// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
(function () {
    if (window !== window.top || window.__overteEditor) { return; }
    var composing = null;
    function editable(element) {
        return element && !element.readOnly && !element.disabled
            && !(element.matches && element.matches(":disabled")) && (element instanceof HTMLTextAreaElement ||
            element instanceof HTMLInputElement && /^(text|search|email|url|tel|password|number)$/.test(element.type)
            || element.isContentEditable);
    }
    function current(element) {
        return document.activeElement === element && element.isConnected !== false && editable(element);
    }
    function value(element) { return element.value === undefined ? element.textContent : element.value; }
    function keydown(element, key, command) {
        var accepted = element.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, cancelable: true,
            key: key, shiftKey: command.shift === true || command.extend === true,
            isComposing: !!(composing && composing.element === element) })) !== false;
        if (!current(element)) { composing = null; publish(); return false; }
        if (!accepted) publish();
        return accepted;
    }
    function beforeinput(element, inputType, data, isComposing, text, selected) {
        var accepted = element.dispatchEvent(new InputEvent("beforeinput", { bubbles: true, cancelable: true,
            inputType: inputType, data: data, isComposing: isComposing })) !== false;
        if (!current(element)) { composing = null; publish(); return false; }
        // An application callback may replace the value or selection itself.
        // Never apply an older native edit over its newly chosen state.
        var now = selection(element);
        if (value(element) !== text || now[0] !== selected[0] || now[1] !== selected[1]) {
            composing = null; publish(); return false;
        }
        return accepted;
    }
    function enter(element, command) {
        if (!keydown(element, "Enter", command)) return;
        // The IME owns completion of its current preedit. Enter must not
        // submit it or replace it with a newline before the commit arrives.
        if (composing && composing.element === element) return;
        if (element instanceof HTMLInputElement) {
            if (command.shift || !element.form) return;
            var form = element.form, controls = document.querySelectorAll("button,input"), submitter = null;
            for (var i = 0; i < controls.length; ++i) {
                var candidate = controls[i];
                if (candidate.form === form && (candidate.type === "submit" || candidate.type === "image")) {
                    submitter = candidate; break;
                }
            }
            if (submitter && (submitter.disabled || submitter.matches(":disabled"))) return;
            if (!submitter) {
                var blockers = 0;
                for (var j = 0; j < form.elements.length; ++j) {
                    var control = form.elements[j];
                    if (control instanceof HTMLInputElement
                            && /^(text|search|url|tel|email|password|date|month|week|time|datetime-local|number)$/.test(control.type)) ++blockers;
                }
                if (blockers > 1) return;
            }
            // requestSubmit preserves validation, the default submitter and the
            // cancelable submit event; form.submit() would bypass all three.
            if (typeof form.requestSubmit === "function") {
                if (submitter) form.requestSubmit(submitter); else form.requestSubmit();
            }
            return;
        }
        var text = value(element), selected = selection(element);
        if (!beforeinput(element, "insertLineBreak", null, false, text, selected)) return;
        var emitted = replace(element, text, Math.min(selected[0], selected[1]), Math.max(selected[0], selected[1]), "\n");
        composing = null;
        if (!emitted) element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertLineBreak", data: null }));
        publish();
    }
    function selection(element) {
        if (typeof element.selectionStart === "number") {
            return element.selectionDirection === "backward" ? [element.selectionEnd, element.selectionStart] : [element.selectionStart, element.selectionEnd];
        }
        if (element instanceof HTMLInputElement && element.type === "number") { return [element.value.length, element.value.length]; }
        var selected = window.getSelection();
        if (!selected.rangeCount || !element.contains(selected.anchorNode) || !element.contains(selected.focusNode)) {
            return [0, 0];
        }
        function offset(node, index) {
            var range = document.createRange(); range.selectNodeContents(element);
            range.setEnd(node, index); return range.toString().length;
        }
        return [offset(selected.anchorNode, selected.anchorOffset), offset(selected.focusNode, selected.focusOffset)];
    }
    function publish() {
        var element = document.activeElement;
        if (!editable(element)) { composing = null; window.__overteEditorTransport.editor({ active: false }); return; }
        var sensitive = element.type === "password", text = element.value === undefined ? element.textContent : element.value;
        var selected = selection(element), start = Math.max(0, selected[1] - 8192), bounds = element.getBoundingClientRect();
        // Password contents never cross the DOM/native boundary.
        window.__overteEditorTransport.editor({ active: true, sensitive: sensitive,
            text: sensitive ? "" : text.slice(start, start + 16384), cursor: selected[1] - start, anchor: selected[0] - start, absoluteCursor: selected[1],
            x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height,
            kind: element.type || "text" });
    }
    function boundary(text, index) {
        return index >= 0 && index <= text.length && !(index > 0 && index < text.length
            && text.charCodeAt(index - 1) >= 0xD800 && text.charCodeAt(index - 1) <= 0xDBFF
            && text.charCodeAt(index) >= 0xDC00 && text.charCodeAt(index) <= 0xDFFF);
    }
    function point(element, offset) {
        var walk = document.createTreeWalker(element, NodeFilter.SHOW_TEXT), node;
        while ((node = walk.nextNode())) {
            if (offset <= node.length) { return [node, offset]; }
            offset -= node.length;
        }
        return [element, element.childNodes.length];
    }
    function select(element, start, end) {
        if (typeof element.setSelectionRange === "function") { element.setSelectionRange(Math.min(start, end), Math.max(start, end), start > end ? "backward" : "forward"); return; }
        var left = point(element, start), right = point(element, end), range = document.createRange();
        var selected = window.getSelection();
        if (selected.setBaseAndExtent) { selected.setBaseAndExtent(left[0], left[1], right[0], right[1]); return; }
        range.setStart(left[0], left[1]); range.setEnd(right[0], right[1]);
        selected.removeAllRanges(); selected.addRange(range);
    }
    function replace(element, text, start, end, insertion) {
        // execCommand on rich text may emit its own native input event. Plain
        // input/textarea setRangeText does not; report each edit only once.
        var emitted = false, observe = function () { emitted = true; };
        element.addEventListener("input", observe, true);
        try {
            if (element instanceof HTMLInputElement && element.type === "number") element.value = text.slice(0, start) + insertion + text.slice(end);
            else if (typeof element.setRangeText === "function") element.setRangeText(insertion, start, end, "end");
            else { select(element, start, end); document.execCommand("insertText", false, insertion); }
        } finally { element.removeEventListener("input", observe, true); }
        return emitted;
    }
    function ime(element, command, text, selected) {
        var previous = composing && composing.element === element, left = previous ? composing.start : Math.min(selected[0], selected[1]);
        var right = previous ? composing.end : Math.max(selected[0], selected[1]);
        var base = text.slice(0, left) + text.slice(right), start = left + command.replaceStart, end = start + command.replaceLength;
        if (!boundary(base, start) || !boundary(base, end) || start > end) return;
        var commit = command.commit || "", preedit = command.preedit || "";
        var committed = base.slice(0, start) + commit + base.slice(end), position = start + commit.length;
        if (command.selection) {
            var requested = command.selection.start;
            if (boundary(committed, requested)) position = requested;
        }
        var result = committed.slice(0, position) + preedit + committed.slice(position);
        // Replace only the changed DOM range so surrounding rich text retains its nodes.
        var first = 0, oldEnd = text.length, newEnd = result.length;
        while (first < oldEnd && first < newEnd && text.charAt(first) === result.charAt(first)) ++first;
        while (oldEnd > first && newEnd > first && text.charAt(oldEnd - 1) === result.charAt(newEnd - 1)) { --oldEnd; --newEnd; }
        if (!boundary(text, first) || !boundary(result, first)) --first;
        if (!boundary(text, oldEnd)) ++oldEnd;
        if (!boundary(result, newEnd)) ++newEnd;
        var entering = preedit.length > 0, completed = previous && (commit.length > 0 || !entering);
        var inputType = entering ? "insertCompositionText" : "insertText";
        if (!beforeinput(element, inputType, commit + preedit, entering, text, selected)) return;
        if (completed) element.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true, data: commit }));
        if (entering && (!previous || completed)) element.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true, data: "" }));
        if (!current(element) || value(element) !== text) { composing = null; publish(); return; }
        var emitted = replace(element, text, first, oldEnd, result.slice(first, newEnd));
        composing = entering ? { element: element, start: position, end: position + preedit.length } : null;
        var caret = position + Math.max(0, Math.min(preedit.length, command.cursor));
        if (boundary(result, caret)) select(element, caret, caret);
        if (!entering && command.selection && boundary(result, position + command.selection.length)) select(element, position, position + command.selection.length);
        if (entering) element.dispatchEvent(new CompositionEvent("compositionupdate", { bubbles: true, data: preedit }));
        if (!emitted) element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: inputType, data: commit + preedit, isComposing: entering }));
        publish();
    }
    window.__overteEditor = {
        publish: publish,
        edit: function (command) {
            var element = document.activeElement;
            if (!current(element)) { composing = null; publish(); return; }
            if (command.action === "enter") { enter(element, command); return; }
            var text = value(element), selected = selection(element);
            if (command.action === "ime") { ime(element, command, text, selected); return; }
            if (command.action !== "selection" && !command.composing) {
                var keys = { backspace: "Backspace", delete: "Delete", left: "ArrowLeft", right: "ArrowRight", home: "Home", end: "End" };
                var key = keys[command.action] || command.text;
                if (key && !keydown(element, key, command)) return;
                text = value(element); selected = selection(element);
            }
            var start = Math.min(selected[0], selected[1]), end = Math.max(selected[0], selected[1]);
            if (composing && composing.element === element) { start = composing.start; end = composing.end; }
            if (command.replaceStart || command.replaceLength) {
                var base = composing && composing.element === element ? composing.start : selected[1];
                start = base + command.replaceStart; end = start + command.replaceLength;
                // Qt replacements count committed text, skipping the old preedit range.
                if (composing && composing.element === element) {
                    if (start > composing.start) { start += composing.end - composing.start; }
                    if (end >= composing.start) { end += composing.end - composing.start; }
                }
            }
            if (command.action === "backspace" && start === end && start > 0) {
                --start; if (!boundary(text, start)) { --start; }
            }
            if (command.action === "delete" && start === end && end < text.length) {
                ++end; if (!boundary(text, end)) { ++end; }
            }
            if (!boundary(text, start) || !boundary(text, end) || start > end) { return; }
            if (command.action === "left" || command.action === "right" || command.action === "home" || command.action === "end") {
                var next = selected[1];
                if (command.action === "home") next = text.lastIndexOf("\n", next - 1) + 1;
                else if (command.action === "end") { next = text.indexOf("\n", next); if (next < 0) next = text.length; }
                else { next = Math.max(0, Math.min(text.length, next + (command.action === "left" ? -1 : 1))); if (!boundary(text, next)) next += command.action === "left" ? -1 : 1; }
                select(element, command.extend ? selected[0] : next, next); composing = null; publish(); return;
            }
            if (command.action === "selection") {
                if (boundary(text, command.start) && boundary(text, command.start + command.length)) {
                    select(element, command.start, command.start + command.length); composing = null; publish();
                }
                return;
            }
            var insertion = command.text || "";
            var wasComposing = composing && composing.element === element;
            var inputType = command.composing ? "insertCompositionText" :
                command.action === "backspace" ? "deleteContentBackward" :
                command.action === "delete" ? "deleteContentForward" : "insertText";
            if (!beforeinput(element, inputType, insertion, command.composing === true, text, selected)) return;
            if (command.composing && !wasComposing) element.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true, data: "" }));
            if (!current(element) || value(element) !== text) { composing = null; publish(); return; }
            var emitted = replace(element, text, start, end, insertion);
            if (command.composing) element.dispatchEvent(new CompositionEvent("compositionupdate", { bubbles: true, data: insertion }));
            else if (wasComposing) element.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true, data: insertion }));
            composing = command.composing ? { element: element, start: start, end: start + insertion.length } : null;
            if (!emitted) element.dispatchEvent(new InputEvent("input", { bubbles: true,
                inputType: inputType, data: insertion,
                isComposing: command.composing === true }));
            if (command.composing && typeof command.cursor === "number") {
                var caret = start + Math.max(0, Math.min(insertion.length, command.cursor));
                if (boundary(element.value === undefined ? element.textContent : element.value, caret)) select(element, caret, caret);
            }
            publish();
        },
        blur: function () { composing = null; if (document.activeElement) { document.activeElement.blur(); } publish(); }
    };
    ["focusin", "focusout", "input", "selectionchange", "compositionend"].forEach(function (name) {
        document.addEventListener(name, publish, true);
    });
}());
