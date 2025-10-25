# NXBT WebUI Update - Dokumentation

## Übersicht der implementierten Features

Diese Aktualisierung fügt dem NXBT WebUI zwei Hauptfunktionen hinzu:

### 1. Switch MAC-Adressen Verwaltung
- **Automatisches Speichern**: Wenn eine Verbindung zur Switch erfolgreich hergestellt wird, wird die MAC-Adresse automatisch gespeichert
- **Benennung**: Beim ersten Verbinden kann man der Switch einen Namen geben
- **Wiederverbinden**: Gespeicherte Switches werden auf der Hauptseite angezeigt und können direkt ausgewählt werden
- **Verwaltung**: MAC-Adressen können umbenannt und gelöscht werden

### 2. Makro-Verwaltungssystem
- **Speichern**: Makros können mit einem Namen gespeichert werden
- **Laden**: Gespeicherte Makros können in den Editor geladen werden
- **Editieren**: Bestehende Makros können bearbeitet werden
- **Löschen**: Nicht mehr benötigte Makros können gelöscht werden
- **Dropdown-Auswahl**: Schnelles Laden von Makros während des Spielens

## Geänderte Dateien

### Backend (Python)
**Datei**: `nxbt/web/app.py`
- Hinzugefügte Imports: `datetime`
- Neue Funktionen für Datenverwaltung:
  - `load_switch_macs()` - Lädt gespeicherte MAC-Adressen
  - `save_switch_macs()` - Speichert MAC-Adressen
  - `load_macros()` - Lädt gespeicherte Makros
  - `save_macros()` - Speichert Makros

- Neue SocketIO Endpoints:
  - `controller_connected` - Speichert MAC-Adresse nach erfolgreicher Verbindung
  - `get_switch_macs` - Ruft alle gespeicherten MAC-Adressen ab
  - `delete_switch_mac` - Löscht eine gespeicherte MAC-Adresse
  - `update_switch_name` - Aktualisiert den Namen einer Switch
  - `get_macros` - Ruft alle gespeicherten Makros ab
  - `save_macro` - Speichert ein neues Makro
  - `delete_macro` - Löscht ein Makro
  - `update_macro` - Aktualisiert ein bestehendes Makro

- Modifiziert:
  - `on_create_controller()` - Unterstützt jetzt optionale MAC-Adresse als Parameter

### Frontend (HTML)
**Datei**: `nxbt/web/templates/index.html`

Neue Sektionen:
1. **Saved Switches Container** - Zeigt alle gespeicherten Switches an
2. **Switch Management** - Verwaltungssektion für gespeicherte Switches
3. **Macro Management** - Komplette Makro-Verwaltungssektion

Neue Buttons:
- "Manage Switches" - Öffnet die Switch-Verwaltung
- "Manage Macros" - Öffnet die Makro-Verwaltung
- "Save Current Macro" - Speichert das aktuelle Makro im Editor

### Frontend (JavaScript)
**Datei**: `nxbt/web/static/js/main.js`

Neue globale Variablen:
- `SAVED_SWITCHES` - Speichert alle gespeicherten Switch-Daten
- `SAVED_MACROS` - Speichert alle gespeicherten Makro-Daten
- `CURRENT_EDITING_MACRO` - Verfolgt das aktuell bearbeitete Makro

Neue Funktionen für Switch-Verwaltung:
- `updateSavedSwitchesList()` - Aktualisiert die Liste der gespeicherten Switches
- `updateSwitchManagementList()` - Aktualisiert die Verwaltungsansicht
- `showNewSwitchOption()` - Zeigt Optionen für neue Verbindung
- `connectToSwitch(mac)` - Verbindet zu einer gespeicherten Switch
- `updateSwitchName(mac)` - Aktualisiert Switch-Namen
- `deleteSwitchMAC(mac)` - Löscht eine gespeicherte Switch
- `openSwitchManagement()` / `closeSwitchManagement()` - Öffnet/Schließt Verwaltung

Neue Funktionen für Makro-Verwaltung:
- `updateMacrosList()` - Aktualisiert die Makro-Liste
- `updateMacroDropdown()` - Aktualisiert das Makro-Dropdown
- `openMacroManagement()` / `closeMacroManagement()` - Öffnet/Schließt Verwaltung
- `showNewMacroForm()` - Zeigt das Formular für neue Makros
- `editMacro(macroName)` - Bearbeitet ein bestehendes Makro
- `saveMacroForm()` - Speichert Makro aus dem Formular
- `cancelMacroForm()` - Bricht die Makro-Bearbeitung ab
- `deleteMacro(macroName)` - Löscht ein Makro
- `loadMacroToEditor(macroName)` - Lädt Makro in den Editor
- `loadSelectedMacro()` - Lädt ausgewähltes Makro aus Dropdown
- `saveCurrentMacro()` - Speichert aktuelles Makro mit Namensabfrage

Modifizierte Funktionen:
- `createProController()` - Neu implementiert zur Unterstützung von MAC-Auswahl
- `checkForLoad()` - Speichert jetzt automatisch MAC-Adressen nach erfolgreicher Verbindung

### Styling (CSS)
**Datei**: `nxbt/web/static/css/main.css`

Neue CSS-Klassen für:
- Switch-Karten (`.switch-card`)
- Switch-Verwaltung (`.switch-management-item`)
- Makro-Karten (`.macro-card`)
- Makro-Formular (`#macro-form`)
- Makro-Vorschau (`.macro-preview`)
- Buttons (`.new-switch-btn`, `.delete-btn`)
- Und viele weitere Styling-Elemente

### Datenverzeichnis
**Neues Verzeichnis**: `nxbt/web/data/`
- Enthält JSON-Dateien für persistente Datenspeicherung
- `switch_macs.json` - Speichert MAC-Adressen und Metadaten
- `macros.json` - Speichert Makros und Metadaten
- `.gitignore` - Verhindert das Committen von Benutzerdaten

## Datenformat

### Switch MACs (switch_macs.json)
```json
{
  "AA:BB:CC:DD:EE:FF": {
    "name": "Meine Switch",
    "first_connected": "2025-10-25T10:30:00",
    "last_connected": "2025-10-25T15:45:00"
  }
}
```

### Macros (macros.json)
```json
{
  "Makro Name": {
    "content": "A 0.1s\\n0.5s\\nB 0.1s",
    "created": "2025-10-25T10:30:00",
    "modified": "2025-10-25T15:45:00"
  }
}
```

## Benutzerfluss

### Neue Switch Verbindung
1. Benutzer öffnet WebUI
2. Klickt auf "New Switch Console"
3. Wählt Controller-Typ (z.B. Pro Controller)
4. Geht ins "Change Grip/Order" Menü auf der Switch
5. Verbindung wird hergestellt
6. Benutzer wird nach einem Namen für die Switch gefragt
7. MAC-Adresse wird automatisch gespeichert

### Wiederverbindung
1. Benutzer öffnet WebUI
2. Sieht Liste der gespeicherten Switches
3. Klickt auf "Connect" bei der gewünschten Switch
4. Verbindung wird automatisch hergestellt (kein Menü nötig)

### Makro-Verwaltung
1. Benutzer klickt auf "Manage Macros"
2. Kann neue Makros erstellen, bestehende bearbeiten oder löschen
3. Makros können direkt in den Editor geladen werden
4. Oder über das Dropdown während des Spielens schnell geladen werden

## Vorteile der Implementierung

1. **Benutzerfreundlichkeit**: Keine manuelle MAC-Adressen-Verwaltung mehr nötig
2. **Zeitersparnis**: Schnelles Wiederverbinden ohne Menü-Navigation
3. **Organisation**: Makros können benannt und organisiert werden
4. **Persistenz**: Alle Daten bleiben nach Neustart erhalten
5. **Flexibilität**: Mehrere Switches und Makros können verwaltet werden

## Kompatibilität

Die Änderungen sind vollständig rückwärtskompatibel:
- Bestehende Funktionalität bleibt erhalten
- Keine Breaking Changes in der API
- Optional: Benutzer können weiterhin manuelle Verbindungen herstellen
