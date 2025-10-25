# NXBT WebUI - Shared Sessions Update Dokumentation

## Übersicht

Dieses Update ermöglicht es mehreren Browser-Tabs/Fenstern, dieselbe Controller-Session zu teilen und gemeinsam zu nutzen.

### Neue Features

1. **Aktive Session-Übersicht**
   - Zeigt alle derzeit laufenden Controller-Sessions an
   - Anzeige von Session-Status, verbundener Switch, Client-Anzahl
   - Echtzeit-Updates über alle Clients hinweg

2. **Session Beitreten**
   - Möglichkeit, bestehende Sessions zu "joinen"
   - Mehrere Clients können denselben Controller kontrollieren
   - Keine Interferenz zwischen verschiedenen Sessions

3. **Intelligentes Session Management**
   - Reference Counting: Controller werden nur entfernt wenn alle Clients disconnected sind
   - Session-Übernahme ohne Controller-Neustart
   - Automatisches Cleanup bei Disconnect

4. **Session-Kontrollen**
   - "Leave Session" - Trennt nur diesen Client
   - "Remove Controller" - Entfernt den Controller für alle Clients
   - Session-Info zeigt aktuelle Verbindungsdetails

## Technische Implementierung

### Backend-Änderungen (app.py)

#### Neue Datenstrukturen

```python
ACTIVE_CONTROLLERS = {
    # controller_index: {
    #     'clients': set(),           # Alle verbundenen Clients
    #     'mac_address': str,         # MAC der verbundenen Switch
    #     'created_at': str,          # ISO Timestamp der Erstellung
    #     'controller_type': str      # z.B. 'Pro Controller'
    # }
}

SESSION_TO_CONTROLLER = {
    # session_id: controller_index   # Schnelle Zuordnung
}
```

#### Neue Endpoints

**`get_active_controllers_info()`** *(Hilfsfunktion)*
- Sammelt alle aktiven Controller-Informationen
- Kombiniert NXBT-State mit Session-Metadaten
- Gibt strukturierte Daten für Frontend zurück

**`on_get_active_controllers`**
- GET-Endpoint für aktive Sessions
- Emittiert `active_controllers` Event

**`on_join_controller_session(controller_index)`**
- Fügt Client zu bestehender Session hinzu
- Validiert Session-Existenz
- Aktualisiert Reference Counts
- Emittiert `joined_controller_session` Event

**`on_leave_controller_session()`**
- Entfernt nur diesen Client aus der Session
- Controller bleibt für andere Clients aktiv
- Emittiert `left_controller_session` Event

**`on_force_remove_controller(controller_index)`**
- Admin-Funktion zum Entfernen ganzer Sessions
- Benachrichtigt alle betroffenen Clients
- Räumt alle Datenstrukturen auf
- Emittiert `controller_force_removed` Event

#### Modifizierte Funktionen

**`on_connect()`**
- Sendet aktive Sessions an neuen Client
- Initialisiert Client ohne Controller-Bindung

**`on_disconnect()`**
- Reference Counting: Controller nur entfernen wenn letzter Client
- Cleanup von Session-Mappings
- Automatische Macro-Stopps

**`on_create_controller()`**
- Registriert neue Controller in ACTIVE_CONTROLLERS
- Setzt initialen Reference Count auf 1
- Broadcast an alle Clients über neue Session

### Frontend-Änderungen

#### HTML (index.html)

**Neue Section: Active Sessions**
```html
<div id="active-sessions-container" class="surface">
    <h2>Active Controller Sessions</h2>
    <div id="active-sessions-list"></div>
    <button onclick="refreshActiveSessions()">🔄 Refresh Sessions</button>
</div>
```

**Session Management im Controller Config**
```html
<div id="current-session-info" class="surface-lighter">
    <strong>Current Session:</strong>
    <span id="session-controller-index">-</span> | 
    <span id="session-switch-name">Unknown</span> |
    <span id="session-client-count">0 clients</span>
</div>
<button onclick="leaveControllerSession()">Leave Session</button>
<button onclick="forceRemoveController()">Remove Controller (All Clients)</button>
```

#### JavaScript (main.js)

**Neue Variablen:**
```javascript
let ACTIVE_SESSIONS = [];        // Liste aller aktiven Sessions
let CURRENT_SESSION_INDEX = null; // Aktuell verbundene Session
```

**Neue Socket Events:**
- `active_controllers` - Empfängt Session-Updates
- `joined_controller_session` - Session erfolgreich beigetreten
- `left_controller_session` - Session erfolgreich verlassen  
- `controller_force_removed` - Session wurde von Admin entfernt

**Neue Funktionen:**
- `updateActiveSessionsList()` - Rendert Session-Karten
- `updateCurrentSessionInfo()` - Aktualisiert Session-Details
- `joinControllerSession(index)` - Tritt Session bei
- `leaveControllerSession()` - Verlässt aktuelle Session
- `forceRemoveController(index?)` - Entfernt Controller-Session
- `refreshActiveSessions()` - Lädt Sessions neu

#### CSS (main.css)

**Neue Styling-Klassen:**
- `.session-card` - Container für Session-Anzeige
- `.session-status` - Farbcodierte Status-Badges  
- `.status-connected`, `.status-connecting`, `.status-error` - Status-Farben
- `.current-session-indicator` - Hervorhebung der aktuellen Session
- `.refresh-sessions-btn` - Blauer Refresh-Button

## Socket.IO Events

### Client → Server

| Event | Parameter | Beschreibung |
|-------|-----------|--------------|
| `get_active_controllers` | - | Fragt alle aktiven Sessions ab |
| `join_controller_session` | `controller_index` | Tritt bestehender Session bei |
| `leave_controller_session` | - | Verlässt aktuelle Session |
| `force_remove_controller` | `controller_index` | Entfernt Controller komplett |

### Server → Client

| Event | Parameter | Beschreibung |
|-------|-----------|--------------|
| `active_controllers` | `[{index, mac_address, ...}]` | Liste aktiver Sessions |
| `joined_controller_session` | `{controller_index, mac_address, created_at}` | Session-Beitritt erfolgreich |
| `left_controller_session` | `{controller_index}` | Session verlassen |
| `controller_force_removed` | `{controller_index}` | Session wurde entfernt |

## Benutzerfluss

### Neue Session erstellen
1. Benutzer sieht "Active Sessions" (leer) und "Create New Controller"
2. Erstellt neuen Controller wie gewohnt
3. Session wird in "Active Sessions" angezeigt
4. Andere Browser sehen diese Session sofort

### Bestehende Session beitreten
1. Benutzer öffnet WebUI in neuem Tab/Browser
2. Sieht aktive Session in der Liste
3. Klickt "Join Session"
4. Übernimmt sofort die Kontrolle über denselben Controller
5. Kann Inputs senden und Makros starten
6. Session-Info zeigt "2 clients" an

### Session verlassen
1. **Leave Session**: Nur dieser Client trennt sich, Controller bleibt aktiv
2. **Remove Controller**: Alle Clients werden getrennt, Controller wird beendet

### Multi-Client Scenario
```
Browser A: Erstellt Controller → Session 1 aktiv
Browser B: Tritt Session 1 bei → 2 clients
Browser C: Tritt Session 1 bei → 3 clients
Browser A: Verlässt Session → 2 clients (B & C können weiter spielen)
Browser B: Entfernt Controller → Session beendet, C wird benachrichtigt
```

## Reference Counting System

### Controller Lifecycle
1. **Erstellen**: `ACTIVE_CONTROLLERS[index]['clients'] = {session_1}`
2. **Join**: `clients.add(session_2)` → `{session_1, session_2}`
3. **Leave**: `clients.discard(session_1)` → `{session_2}`
4. **Auto-Cleanup**: Wenn `len(clients) == 0` → Controller entfernen

### Session Tracking
```python
# Beim Connect
ACTIVE_CONTROLLERS[index]['clients'].add(session_id)
SESSION_TO_CONTROLLER[session_id] = index

# Beim Disconnect  
ACTIVE_CONTROLLERS[index]['clients'].discard(session_id)
del SESSION_TO_CONTROLLER[session_id]

# Cleanup-Check
if not ACTIVE_CONTROLLERS[index]['clients']:
    nxbt.remove_controller(index)
    del ACTIVE_CONTROLLERS[index]
```

## Fehlerbehandlung & Edge Cases

### Client Crash/Browser schließt
- `on_disconnect()` automatisch aufgerufen
- Reference Count wird dekrementiert
- Controller bleibt für andere Clients aktiv

### Netzwerk-Probleme
- Reconnect führt automatisch `get_active_controllers` aus
- Client sieht aktuelle Session-Liste

### Admin-Entfernung
- Alle betroffenen Clients erhalten `controller_force_removed`
- Alert-Nachricht mit Erklärung
- Automatisches Zurücksetzen zur Controller-Auswahl

### Race Conditions
- Alle Session-Modifikationen sind thread-safe (user_info_lock)
- Atomic Updates der Datenstrukturen

## Sicherheit & Isolation

### Session-Isolation
- Jede Session hat eigene `USER_INFO[session_id]`
- Makro-Tracking pro Session (`RUNNING_MACROS[session_id]`)
- Keine Cross-Session-Interferenz

### Controller-Sharing
- Mehrere Clients können denselben Controller kontrollieren
- Letzter Input gewinnt (normales NXBT-Verhalten)
- Makros können von jedem Client gestoppt werden

### Cleanup-Garantien
- Controller werden nie "verwaist"
- Automatische Bereinigung bei allen Disconnect-Szenarien
- Konsistente Datenstrukturen

## Performance & Skalierung

### Broadcast-Optimierung
- Nur bei Änderungen werden Updates gesendet
- Effiziente Set-Operationen für Client-Tracking
- Minimaler Memory Overhead pro Session

### UI-Updates
- Echtzeit-Updates über WebSocket
- Keine Polling erforderlich
- Responsive UI auch bei vielen Sessions

## Vorteile

1. ✅ **Multi-Tab-Support** - Ein Controller, mehrere Browser-Fenster
2. ✅ **Kollaboration** - Mehrere Personen können denselben Controller nutzen
3. ✅ **Session-Persistenz** - Controller bleiben aktiv wenn ein Tab geschlossen wird
4. ✅ **Sichtbarkeit** - Klare Übersicht über alle aktiven Sessions
5. ✅ **Flexibilität** - Join/Leave nach Belieben
6. ✅ **Robustheit** - Reference Counting verhindert versehentliches Schließen

## Kompatibilität

- Vollständig rückwärtskompatibel
- Bestehende Single-Session-Nutzung funktioniert weiterhin
- Keine Breaking Changes in der API
- Alte Makros und Funktionen bleiben unverändert