# NXBT WebUI - Makro-Status Update Dokumentation

## Übersicht

Dieses Update behebt das Problem, dass das WebUI während der Makro-Ausführung einfriert und fügt folgende Features hinzu:

### Neue Features

1. **Non-Blocking Makro-Ausführung**
   - Makros werden jetzt im Hintergrund ausgeführt
   - Das UI bleibt während der Makro-Ausführung reaktionsfähig
   - Benutzer können weiterhin mit der Anwendung interagieren

2. **Visueller Makro-Status-Indikator**
   - Zeigt deutlich an, wenn ein Makro läuft
   - Animierter Spinner für visuelle Rückmeldung
   - Pulsierende Rahmenanimation
   - Statustext mit Details

3. **Makro Stoppen**
   - Roter "Stop Macro" Button während der Ausführung
   - Sofortiges Stoppen des laufenden Makros
   - Automatisches Aufräumen der Ressourcen

4. **Intelligente UI-Kontrollen**
   - "Run Macro" Button wird deaktiviert während ein Makro läuft
   - Verhindert versehentliches Starten mehrerer Makros gleichzeitig
   - Automatische Reaktivierung nach Makro-Abschluss

## Technische Implementierung

### Backend-Änderungen (app.py)

#### Neue globale Variable
```python
RUNNING_MACROS = {}  # Tracking: {session_id: {'macro_id': str, 'controller_index': int}}
```

#### Modifizierte Funktionen

**`handle_macro(message)`**
- Verwendet jetzt `block=False` für non-blocking Ausführung
- Trackt laufende Makros pro Session
- Emittiert `macro_started` Event
- Startet Background-Task für Completion-Monitoring

**`handle_stop_macro()`** *(NEU)*
- Stoppt das aktuell laufende Makro für die Session
- Verwendet `nxbt.stop_macro()` mit `block=False`
- Räumt Tracking-Datenstrukturen auf
- Emittiert `macro_stopped` Event

**`monitor_macro_completion(session_id, controller_index, macro_id)`** *(NEU)*
- Background-Task der prüft wann ein Makro fertig ist
- Pollt `nxbt.state` alle 0.1 Sekunden
- Emittiert `macro_completed` Event bei Abschluss
- Räumt Tracking automatisch auf

**`handle_get_macro_status()`** *(NEU)*
- Gibt aktuellen Makro-Status für die Session zurück
- Wird beim Page-Load aufgerufen

**`on_disconnect()`** *(MODIFIZIERT)*
- Stoppt automatisch laufende Makros bei Disconnect
- Verhindert "Zombie"-Makros

### Frontend-Änderungen

#### HTML (index.html)

Neuer Makro-Status-Indikator:
```html
<div id="macro-status-indicator" class="hidden surface-lighter macro-status">
    <div class="macro-status-content">
        <div class="macro-status-icon">
            <div class="spinner"></div>
        </div>
        <div class="macro-status-text">
            <strong>Macro Running...</strong>
            <p id="macro-status-details">Executing macro commands</p>
        </div>
    </div>
    <button onclick="stopRunningMacro()" class="stop-macro-btn">Stop Macro</button>
</div>
```

- ID für "Run Macro" Button hinzugefügt: `id="run-macro-btn"`
- Positioniert oberhalb der Makro-Textarea

#### JavaScript (main.js)

**Neue Variablen:**
```javascript
let CURRENT_MACRO_ID = null;
let HTML_MACRO_STATUS = document.getElementById('macro-status-indicator');
let HTML_RUN_MACRO_BTN = document.getElementById('run-macro-btn');
```

**Neue Socket Event Handlers:**
- `socket.on('macro_started')` - Zeigt Status-Indikator
- `socket.on('macro_completed')` - Versteckt Status-Indikator
- `socket.on('macro_stopped')` - Versteckt Status-Indikator
- `socket.on('macro_status')` - Initialer Status beim Load

**Neue Funktionen:**
- `showMacroRunning()` - Zeigt Indikator, deaktiviert Run-Button
- `hideMacroRunning()` - Versteckt Indikator, aktiviert Run-Button
- `stopRunningMacro()` - Emittiert stop_macro Event

**Modifizierte Funktionen:**
- `sendMacro()` - Validiert dass Makro-Text vorhanden ist

#### CSS (main.css)

**Neue Klassen:**
- `.macro-status` - Container mit pulsierendem Rahmen
- `.macro-status-content` - Flex-Layout für Icon und Text
- `.spinner` - Rotierender Lade-Indikator
- `.stop-macro-btn` - Roter Stop-Button
- Animationen: `@keyframes pulse-border` und `@keyframes spin`

## Socket.IO Events

### Client → Server

| Event | Parameter | Beschreibung |
|-------|-----------|--------------|
| `macro` | `[index, macro]` | Startet Makro-Ausführung |
| `stop_macro` | - | Stoppt laufendes Makro |
| `get_macro_status` | - | Fragt aktuellen Status ab |

### Server → Client

| Event | Parameter | Beschreibung |
|-------|-----------|--------------|
| `macro_started` | `{macro_id, controller_index}` | Makro wurde gestartet |
| `macro_completed` | `{macro_id, controller_index}` | Makro ist fertig |
| `macro_stopped` | `{macro_id, controller_index}` | Makro wurde gestoppt |
| `macro_status` | `{running, macro_info?}` | Aktueller Status |

## Benutzerfluss

### Makro Starten
1. Benutzer gibt Makro in Textarea ein
2. Klickt auf "Run Macro"
3. Status-Indikator erscheint mit Animation
4. "Run Macro" Button wird deaktiviert
5. Makro läuft im Hintergrund
6. UI bleibt reaktionsfähig

### Makro Stoppen
1. Während Makro läuft: "Stop Macro" Button ist sichtbar
2. Benutzer klickt auf "Stop Macro"
3. Makro wird sofort gestoppt
4. Status-Indikator verschwindet
5. "Run Macro" Button wird wieder aktiviert

### Makro Auto-Abschluss
1. Makro läuft bis zum Ende
2. Backend erkennt Abschluss automatisch
3. `macro_completed` Event wird gesendet
4. Status-Indikator verschwindet automatisch
5. "Run Macro" Button wird wieder aktiviert

## Fehlerbehandlung

- **Disconnect während Makro läuft**: Makro wird automatisch gestoppt
- **Leeres Makro**: Alert-Nachricht, kein Start
- **Mehrfache Makros**: Verhindert durch deaktivierten Button

## Session-Management

- Jede Browser-Session trackt ihr eigenes laufendes Makro
- Keine Interferenz zwischen mehreren Benutzern
- Automatisches Cleanup bei Disconnect

## Performance

- **Polling-Intervall**: 0.1 Sekunden (100ms)
- **Non-blocking**: Kein Einfrieren des Event-Loops
- **Effizient**: Nur aktive Sessions werden gemonitored

## Visuelle Gestaltung

- **Farben**: Grün für "Running" Status (#4caf50)
- **Animationen**: Sanfte, professionelle Übergänge
- **Konsistent**: Passt zum bestehenden NXBT-Design
- **Responsive**: Funktioniert auf verschiedenen Bildschirmgrößen

## Vorteile

1. ✅ **Keine UI-Freezes mehr** - Volle Reaktionsfähigkeit während Makros
2. ✅ **Bessere UX** - Visuelles Feedback über Makro-Status
3. ✅ **Kontrolle** - Makros können jederzeit gestoppt werden
4. ✅ **Sicherheit** - Verhindert mehrfache gleichzeitige Makros
5. ✅ **Robust** - Automatisches Cleanup bei Fehlern/Disconnects

## Kompatibilität

- Vollständig rückwärtskompatibel
- Keine Breaking Changes
- Funktioniert mit allen bestehenden Makros
- Keine zusätzlichen Dependencies erforderlich
