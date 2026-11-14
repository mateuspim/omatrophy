import QtQuick
import Quickshell.Io

// Builds a sibling QML file from its current text, so edits to the cards,
// the panel content and the tracker show on the next open without restarting
// the shell (ADR 5, ADR 10).
//
// Omarchy's Quickshell (the OmarchyLoadPatch pragma) serves plugin files as
// qs:// URLs from a cache filled on first load and ignores a ?v= query, so a
// Loader keeps the copy from shell start. A file:// URL does reload, but
// makes Quickshell watch the file and reload the whole shell when it changes,
// which can upset a running game (ADR 8). Compiling the text read fresh does
// neither.
Item {
  id: root

  // The object built by load(); null until then and after clear().
  property var item: null
  // Keep the built object while its file's text is unchanged: load()
  // returns it again and sets `reused`, for a caller that resets it itself.
  // Compiling TrackerView.qml (100 KB) took 70-135 ms of every open of the
  // tracker, which the owner felt on the Guide key.
  property bool keep: false
  property bool reused: false
  property string builtName: ""
  property string builtHash: ""
  // name -> { hash, component }: each file's text compiled once, built from
  // on every open until the text changes. Qt.createQmlObject recompiles its
  // whole text on every call, even at the same URL, and StylePicker.qml
  // (200 KB by 2026-11-12) took 250-330 ms of every panel open; building
  // from a compiled Component takes 25-75 ms. A replaced Component stays
  // parented here (a card built from it may still be up), so each edit
  // leaks one until the shell restarts, which only matters while developing.
  property var compiled: ({})

  FileView {
    id: source
    blockLoading: true
    printErrors: false
  }

  // Builds `name` (a .qml file in this folder) under this item, replacing the
  // previous one. Returns the object, or null when the file doesn't compile.
  function load(name) {
    var url = Qt.resolvedUrl(name)
    source.path = decodeURIComponent(String(url).replace(/^(qs|file):\/\//, ""))
    source.reload()
    source.waitForJob()
    var sum = hash(source.text())
    root.reused = keep && root.item !== null && name === builtName && sum === builtHash
    if (root.reused) return root.item
    clear()
    builtName = name
    builtHash = sum
    // A sibling URL that is never a file, so the engine compiles this text
    // instead of reusing a cached type for the real one. Relative paths in
    // the file resolve as before; errors name it `<name>.live-<hash>.qml`.
    // The URL carries a hash of the text: the engine keeps the inline
    // components (`component X: ...`) of the first text it built at a URL,
    // so an edit that adds one failed as "X is not a type" until a restart
    // (seen 2026-11-04 on Quickshell 0.3.2, Qt 6.12). Unchanged text keeps
    // its URL, so reopening doesn't pile up types.
    var component = compile(name, url, sum, source.text())
    if (!component) return null
    root.item = component.createObject(root)
    if (!root.item) console.warn("omatrophy: " + name + " failed to build, fix it and reopen:", component.errorString())
    return root.item
  }

  // The file's text compiled as a Component, from this item's cache while
  // the text hashes the same. Null when it doesn't compile.
  function compile(name, url, sum, text) {
    var cached = root.compiled[name]
    if (cached && cached.hash === sum) return cached.component
    var live = String(url).replace(/\.qml$/, ".live-" + sum + ".qml")
    try {
      var component = Qt.createQmlObject(asComponent(text), root, live)
      root.compiled[name] = { hash: sum, component: component }
      return component
    } catch (e) {
      console.warn("omatrophy: " + name + " failed to build, fix it and reopen:", JSON.stringify(e.qmlErrors || String(e)))
      return null
    }
  }

  // Wraps a file's root object in `Component { }`, on the root's own line,
  // so the line numbers in errors still match the file. Empty text, which
  // fails to compile, when no line starts a root object.
  function asComponent(text) {
    var start = /^[A-Za-z][\w.]*\s*\{/m.exec(text)
    if (!start) return ""
    return text.slice(0, start.index) + "Component { " + text.slice(start.index) + "\n}\n"
  }

  // A short hex hash of a file's text (djb2), enough to tell edits apart.
  function hash(text) {
    var h = 5381
    for (var i = 0; i < text.length; i++) h = ((h * 33) ^ text.charCodeAt(i)) >>> 0
    return h.toString(16)
  }

  function clear() {
    if (root.item) root.item.destroy()
    root.item = null
    builtHash = ""
  }
}
