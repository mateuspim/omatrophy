import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons as Commons

// The bar panel's content, a trophy cabinet: your totals, the games nearest
// platinum, then the settings (trophy style, preview tiles that fire real
// toasts through the running service, position and sound). Reads and writes
// the same ~/.config/omatrophy/config.json the service watches, through
// `omatrophy.py set`, so a choice applies to the next toast.
Column {
  id: root
  property color foreground: Commons.Color.popups.text

  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("omatrophy.py")).replace(/^file:\/\//, ""))
  readonly property var styles: [
    { id: "omarchy", name: "Omarchy" },
    { id: "vector", name: "Faceted" },
    { id: "painted", name: "Painted" }
  ]
  readonly property var metals: ["bronze", "silver", "gold", "platinum"]
  readonly property var metalColors: ({ bronze: "#e9a46b", silver: "#dfe6ee", gold: "#f3cf4a", platinum: "#e2eaff" })

  property string iconSet: "omarchy"
  property string position: "top-center"
  property bool sound: true
  property string chimes: "omatrophy"

  // From `omatrophy.py cabinet`; null until it answers.
  property var cabinet: null

  function set(key, value) {
    if (key === "icons") iconSet = value
    if (key === "position") position = value
    if (key === "sound") {
      sound = value !== "off"
      if (value !== "on" && value !== "off") chimes = value
    }
    runner.exec(["python3", helperPath, "set", key, value])
  }

  function preview(kind) {
    runner.exec(["python3", helperPath, "test", kind])
  }

  spacing: Commons.Style.space(8)

  FileView {
    path: Quickshell.env("HOME") + "/.config/omatrophy/config.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var c = {}
      try { c = JSON.parse(text()) } catch (e) { return }
      if (c.icons) root.iconSet = c.icons
      if (c.position) root.position = c.position
      if (typeof c.sound === "boolean") root.sound = c.sound
      if (c.chimes) root.chimes = c.chimes
    }
  }

  Process { id: runner }

  Process {
    running: true
    command: ["python3", root.helperPath, "cabinet"]
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.cabinet = JSON.parse(text) } catch (e) {}
      }
    }
  }

  // One trophy, drawn the way the cards draw it (the omarchy set's inlay
  // painted in the theme accent).
  component Thumb: Item {
    id: thumb
    property string style: "omarchy"
    property string metal: "bronze"
    width: 28
    height: 28
    Image {
      anchors.fill: parent
      source: Qt.resolvedUrl("assets/" + thumb.style + "/trophy-" + thumb.metal + (thumb.style === "painted" ? ".png" : ".svg"))
      sourceSize: Qt.size(128, 128)
      smooth: thumb.style !== "omarchy"
      mipmap: thumb.style === "painted"
    }
    Item {
      anchors.fill: parent
      visible: thumb.style === "omarchy"
      Rectangle { id: paint; anchors.fill: parent; color: Commons.Color.accent; visible: false; layer.enabled: true }
      Image {
        id: inlay
        anchors.fill: parent
        source: thumb.style === "omarchy" ? Qt.resolvedUrl("assets/omarchy/trophy-accent.svg") : ""
        sourceSize: Qt.size(128, 128)
        visible: false
      }
      MultiEffect { anchors.fill: parent; source: paint; maskEnabled: true; maskSource: inlay }
    }
  }

  // A big number over its label.
  component Stat: Column {
    property string value: ""
    property string label: ""
    property color tint: root.foreground
    spacing: Commons.Style.space(1)
    Text {
      text: parent.value
      color: parent.tint
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.display
      font.bold: true
    }
    Text {
      text: parent.label
      color: root.foreground
      opacity: 0.55
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.caption
      font.letterSpacing: 1.5
    }
  }

  // The totals, led by a platinum trophy in your style.
  Item {
    width: root.width
    height: Commons.Style.space(60)

    Thumb {
      id: heroTrophy
      anchors.verticalCenter: parent.verticalCenter
      style: root.iconSet
      metal: "platinum"
      width: 52
      height: 52
    }
    Row {
      anchors.left: heroTrophy.right
      anchors.leftMargin: Commons.Style.space(18)
      anchors.verticalCenter: parent.verticalCenter
      spacing: Commons.Style.space(22)
      Stat {
        value: root.cabinet ? root.cabinet.trophies.toLocaleString(Qt.locale(), "f", 0) : "–"
        label: "TROPHIES"
      }
      Stat {
        value: root.cabinet ? root.cabinet.platinums : "–"
        label: "PLATINUM"
        tint: root.metalColors.platinum
      }
      Stat {
        value: root.cabinet ? root.cabinet.games : "–"
        label: "GAMES"
      }
    }
  }

  PanelSectionHeader {
    visible: nearest.count > 0
    text: "CLOSEST TO PLATINUM"
    foreground: root.foreground
  }

  Repeater {
    id: nearest
    model: root.cabinet ? root.cabinet.nearest : []
    delegate: Item {
      id: game
      required property var modelData
      readonly property int remaining: modelData.total - modelData.unlocked
      width: root.width
      height: Commons.Style.space(46)

      Rectangle {
        id: art
        anchors.verticalCenter: parent.verticalCenter
        // Steam's header art is 460 × 215.
        width: Math.round(height * 460 / 215)
        height: parent.height
        color: Qt.alpha(root.foreground, 0.06)
        radius: Commons.Style.cornerRadius
        clip: true
        Image {
          anchors.fill: parent
          source: game.modelData.header || ""
          fillMode: Image.PreserveAspectCrop
          asynchronous: true
          sourceSize.width: 200
        }
      }

      Column {
        anchors.left: art.right
        anchors.leftMargin: Commons.Style.space(12)
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: Commons.Style.space(4)

        Text {
          width: parent.width
          text: game.modelData.game
          color: root.foreground
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
          font.bold: true
          elide: Text.ElideRight
        }
        Rectangle {
          width: parent.width
          height: 4
          color: Qt.alpha(root.foreground, 0.1)
          Rectangle {
            width: parent.width * game.modelData.unlocked / game.modelData.total
            height: parent.height
            color: Commons.Color.accent
          }
        }
        Item {
          width: parent.width
          height: count.height
          Text {
            id: count
            text: game.modelData.unlocked + " / " + game.modelData.total
            color: root.foreground
            opacity: 0.6
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.caption
          }
          Text {
            anchors.right: parent.right
            text: game.remaining + " to go"
            color: root.foreground
            opacity: 0.6
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.caption
          }
        }
      }
    }
  }

  Item { width: 1; height: Commons.Style.space(2) }
  PanelSectionHeader { text: "TROPHY STYLE"; foreground: root.foreground }

  Row {
    id: styleCards
    spacing: Commons.Style.space(6)
    readonly property real cardWidth: (root.width - spacing * (root.styles.length - 1)) / root.styles.length
    Repeater {
      model: root.styles
      // A card per style: its gold trophy and name. The chosen one carries
      // the accent edge.
      delegate: Rectangle {
        id: styleCard
        required property var modelData
        readonly property bool chosen: root.iconSet === modelData.id
        width: styleCards.cardWidth
        height: Commons.Style.space(70)
        radius: Commons.Style.cornerRadius
        color: chosen ? Commons.Style.selectedFill : (pick.containsMouse ? Commons.Style.hoverFill : Qt.alpha(root.foreground, 0.04))
        border.width: 1
        border.color: chosen ? Commons.Color.accent : Qt.alpha(root.foreground, 0.12)
        Accessible.role: Accessible.Button
        Accessible.name: modelData.name + " trophies" + (chosen ? ", in use" : "")

        MouseArea {
          id: pick
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: root.set("icons", styleCard.modelData.id)
        }
        Column {
          anchors.centerIn: parent
          spacing: Commons.Style.space(5)
          Thumb {
            anchors.horizontalCenter: parent.horizontalCenter
            style: styleCard.modelData.id
            metal: "gold"
            width: 34
            height: 34
          }
          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: styleCard.modelData.name
            color: root.foreground
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.caption
            font.bold: styleCard.chosen
          }
        }
      }
    }
  }

  // Settings as label + control rows, so they read as one compact block.
  component SettingRow: Item {
    property string label: ""
    default property alias control: slot.data
    width: root.width
    height: Math.max(labelText.height, slot.childrenRect.height)
    Text {
      id: labelText
      anchors.verticalCenter: parent.verticalCenter
      text: parent.label
      color: root.foreground
      opacity: 0.6
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.caption
      font.letterSpacing: 1.5
    }
    Item {
      id: slot
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      width: childrenRect.width
      height: childrenRect.height
    }
  }

  Item { width: 1; height: Commons.Style.space(2) }

  SettingRow {
    label: "PREVIEW"
    Row {
      spacing: Commons.Style.space(6)
      Repeater {
        model: root.metals
        // A tile per metal that fires a real toast; its edge is the metal.
        delegate: Rectangle {
          id: tile
          required property string modelData
          width: Commons.Style.space(40)
          height: Commons.Style.space(34)
          radius: Commons.Style.cornerRadius
          color: fire.pressed ? Qt.alpha(root.metalColors[modelData], 0.22)
                 : (fire.containsMouse ? Qt.alpha(root.metalColors[modelData], 0.12) : Qt.alpha(root.foreground, 0.04))
          border.width: 1
          border.color: Qt.alpha(root.metalColors[modelData], fire.containsMouse ? 0.8 : 0.35)
          Accessible.role: Accessible.Button
          Accessible.name: "Show a " + modelData + " toast now"

          MouseArea {
            id: fire
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.preview(tile.modelData)
          }
          Thumb {
            anchors.centerIn: parent
            style: root.iconSet
            metal: tile.modelData
            width: 22
            height: 22
          }
        }
      }
    }
  }

  SettingRow {
    label: "POSITION"
    ButtonGroup {
      options: [
        { value: "top-left", label: "Left" },
        { value: "top-center", label: "Center" },
        { value: "top-right", label: "Right" }
      ]
      value: root.position
      foreground: root.foreground
      fontSize: Commons.Style.font.bodySmall
      onChanged: value => root.set("position", value)
    }
  }

  SettingRow {
    label: "SOUND"
    ButtonGroup {
      options: [
        { value: "omatrophy", label: "OmaTrophy" },
        { value: "classic", label: "Classic" },
        { value: "off", label: "Silent" }
      ]
      value: root.sound ? root.chimes : "off"
      foreground: root.foreground
      fontSize: Commons.Style.font.bodySmall
      onChanged: value => root.set("sound", value)
    }
  }
}
