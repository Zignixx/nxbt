import json
import os
from threading import RLock
import time
from socket import gethostname
from datetime import datetime

from .cert import generate_cert
from ..nxbt import Nxbt, PRO_CONTROLLER
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import eventlet


app = Flask(__name__,
            static_url_path='',
            static_folder='static',)
nxbt = Nxbt()

# Data storage paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SWITCH_MAC_FILE = os.path.join(DATA_DIR, "switch_macs.json")
MACROS_FILE = os.path.join(DATA_DIR, "macros.json")

# Ensure data directory exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Configuring/retrieving secret key
secrets_path = os.path.join(
    os.path.dirname(__file__), "secrets.txt"
)
if not os.path.isfile(secrets_path):
    secret_key = os.urandom(24).hex()
    with open(secrets_path, "w") as f:
        f.write(secret_key)
else:
    secret_key = None
    with open(secrets_path, "r") as f:
        secret_key = f.read()
app.config['SECRET_KEY'] = secret_key

# Starting socket server with Flask app
sio = SocketIO(app, cookie=False)

user_info_lock = RLock()
USER_INFO = {}
RUNNING_MACROS = {}  # Track running macros: {session_id: {'macro_id': str, 'controller_index': int}}
ACTIVE_CONTROLLERS = {}  # Track active controllers: {controller_index: {'clients': set(), 'mac_address': str, 'created_at': str}}
SESSION_TO_CONTROLLER = {}  # Map session_id to controller_index for quick lookup


# Helper functions for data management
def load_switch_macs():
    """Load saved Switch MAC addresses from file"""
    if os.path.exists(SWITCH_MAC_FILE):
        with open(SWITCH_MAC_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_switch_macs(macs):
    """Save Switch MAC addresses to file"""
    with open(SWITCH_MAC_FILE, 'w') as f:
        json.dump(macs, f, indent=2)

def load_macros():
    """Load saved macros from file"""
    if os.path.exists(MACROS_FILE):
        with open(MACROS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_macros(macros):
    """Save macros to file"""
    with open(MACROS_FILE, 'w') as f:
        json.dump(macros, f, indent=2)


@app.route('/')
def index():
    return render_template('index.html')


@sio.on('connect')
def on_connect():
    with user_info_lock:
        USER_INFO[request.sid] = {}
    
    # Send list of active controllers to the new client
    emit('active_controllers', get_active_controllers_info())


@sio.on('state')
def on_state():
    state_proxy = nxbt.state.copy()
    state = {}
    for controller in state_proxy.keys():
        state[controller] = state_proxy[controller].copy()
    emit('state', state)


@sio.on('disconnect')
def on_disconnect():
    print("Disconnected")
    with user_info_lock:
        try:
            # Stop any running macros for this session
            if request.sid in RUNNING_MACROS:
                macro_info = RUNNING_MACROS[request.sid]
                nxbt.stop_macro(
                    macro_info['controller_index'],
                    macro_info['macro_id'],
                    block=False
                )
                del RUNNING_MACROS[request.sid]
            
            # Check if this session was controlling a controller
            if request.sid in SESSION_TO_CONTROLLER:
                controller_index = SESSION_TO_CONTROLLER[request.sid]
                
                # Remove this client from the controller's client list
                if controller_index in ACTIVE_CONTROLLERS:
                    ACTIVE_CONTROLLERS[controller_index]['clients'].discard(request.sid)
                    
                    # Only remove controller if no clients are left
                    if not ACTIVE_CONTROLLERS[controller_index]['clients']:
                        nxbt.remove_controller(controller_index)
                        del ACTIVE_CONTROLLERS[controller_index]
                        print(f"Removed controller {controller_index} - no clients left")
                    else:
                        print(f"Controller {controller_index} still has {len(ACTIVE_CONTROLLERS[controller_index]['clients'])} clients")
                
                del SESSION_TO_CONTROLLER[request.sid]
            
            # Clean up user info
            if request.sid in USER_INFO:
                del USER_INFO[request.sid]
        except KeyError as e:
            print(f"KeyError during disconnect: {e}")
            pass


@sio.on('shutdown')
def on_shutdown(index):
    nxbt.remove_controller(index)


@sio.on('web_create_pro_controller')
def on_create_controller(mac_address=None):
    print("Create Controller")

    try:
        reconnect_addresses = nxbt.get_switch_addresses()
        
        # If a specific MAC address is provided, use it
        if mac_address:
            reconnect_addresses = mac_address
        
        index = nxbt.create_controller(PRO_CONTROLLER, reconnect_address=reconnect_addresses)

        with user_info_lock:
            USER_INFO[request.sid]["controller_index"] = index
            USER_INFO[request.sid]["target_mac"] = mac_address
            
            # Register this controller as active
            ACTIVE_CONTROLLERS[index] = {
                'clients': {request.sid},
                'mac_address': mac_address,
                'created_at': datetime.now().isoformat(),
                'controller_type': 'Pro Controller'
            }
            SESSION_TO_CONTROLLER[request.sid] = index

        emit('create_pro_controller', index)
        
        # Broadcast updated active controllers to all clients
        sio.emit('active_controllers', get_active_controllers_info())
    except Exception as e:
        emit('error', str(e))


@sio.on('controller_connected')
def on_controller_connected(data):
    """Handle successful controller connection and save MAC address"""
    try:
        mac_address = data.get('mac_address')
        name = data.get('name', 'Unnamed Switch')
        
        if mac_address:
            macs = load_switch_macs()
            
            # Add or update MAC address
            if mac_address not in macs:
                macs[mac_address] = {
                    'name': name,
                    'first_connected': datetime.now().isoformat(),
                    'last_connected': datetime.now().isoformat()
                }
            else:
                macs[mac_address]['last_connected'] = datetime.now().isoformat()
            
            save_switch_macs(macs)
            emit('switch_macs_updated', macs)
    except Exception as e:
        print(f"Error saving MAC address: {e}")
        emit('error', str(e))


@sio.on('get_switch_macs')
def on_get_switch_macs():
    """Get all saved Switch MAC addresses"""
    try:
        macs = load_switch_macs()
        emit('switch_macs', macs)
    except Exception as e:
        emit('error', str(e))


@sio.on('delete_switch_mac')
def on_delete_switch_mac(mac_address):
    """Delete a saved Switch MAC address"""
    try:
        macs = load_switch_macs()
        if mac_address in macs:
            del macs[mac_address]
            save_switch_macs(macs)
            emit('switch_macs_updated', macs)
    except Exception as e:
        emit('error', str(e))


@sio.on('update_switch_name')
def on_update_switch_name(data):
    """Update the name of a saved Switch"""
    try:
        mac_address = data.get('mac_address')
        new_name = data.get('name')
        
        if mac_address and new_name:
            macs = load_switch_macs()
            if mac_address in macs:
                macs[mac_address]['name'] = new_name
                save_switch_macs(macs)
                emit('switch_macs_updated', macs)
    except Exception as e:
        emit('error', str(e))


@sio.on('get_macros')
def on_get_macros():
    """Get all saved macros"""
    try:
        macros = load_macros()
        emit('macros', macros)
    except Exception as e:
        emit('error', str(e))


@sio.on('save_macro')
def on_save_macro(data):
    """Save a new macro or update existing one"""
    try:
        macro_name = data.get('name')
        macro_content = data.get('content')
        
        if macro_name and macro_content:
            macros = load_macros()
            macros[macro_name] = {
                'content': macro_content,
                'created': datetime.now().isoformat(),
                'modified': datetime.now().isoformat()
            }
            save_macros(macros)
            emit('macros_updated', macros)
    except Exception as e:
        emit('error', str(e))


@sio.on('delete_macro')
def on_delete_macro(macro_name):
    """Delete a saved macro"""
    try:
        macros = load_macros()
        if macro_name in macros:
            del macros[macro_name]
            save_macros(macros)
            emit('macros_updated', macros)
    except Exception as e:
        emit('error', str(e))


@sio.on('update_macro')
def on_update_macro(data):
    """Update an existing macro"""
    try:
        old_name = data.get('old_name')
        new_name = data.get('new_name')
        content = data.get('content')
        
        macros = load_macros()
        
        if old_name in macros:
            # If name changed, delete old entry
            if old_name != new_name:
                created = macros[old_name].get('created', datetime.now().isoformat())
                del macros[old_name]
            else:
                created = macros[old_name].get('created', datetime.now().isoformat())
            
            macros[new_name] = {
                'content': content,
                'created': created,
                'modified': datetime.now().isoformat()
            }
            save_macros(macros)
            emit('macros_updated', macros)
    except Exception as e:
        emit('error', str(e))


def get_active_controllers_info():
    """Get information about all active controllers"""
    controllers_info = []
    for controller_index, info in ACTIVE_CONTROLLERS.items():
        # Get current controller state
        controller_state = nxbt.state.get(controller_index, {})
        
        controllers_info.append({
            'index': controller_index,
            'mac_address': info['mac_address'],
            'created_at': info['created_at'],
            'controller_type': info['controller_type'],
            'client_count': len(info['clients']),
            'state': controller_state.get('state', 'unknown'),
            'connected_switch': info['mac_address'] if info['mac_address'] else 'New Switch'
        })
    
    return controllers_info


@sio.on('get_active_controllers')
def on_get_active_controllers():
    """Get list of all active controllers"""
    emit('active_controllers', get_active_controllers_info())


@sio.on('join_controller_session')
def on_join_controller_session(controller_index):
    """Join an existing controller session"""
    try:
        controller_index = int(controller_index)
        
        with user_info_lock:
            if controller_index in ACTIVE_CONTROLLERS:
                # Add this session to the controller's client list
                ACTIVE_CONTROLLERS[controller_index]['clients'].add(request.sid)
                SESSION_TO_CONTROLLER[request.sid] = controller_index
                
                # Update user info
                USER_INFO[request.sid]["controller_index"] = controller_index
                USER_INFO[request.sid]["target_mac"] = ACTIVE_CONTROLLERS[controller_index]['mac_address']
                
                emit('joined_controller_session', {
                    'controller_index': controller_index,
                    'mac_address': ACTIVE_CONTROLLERS[controller_index]['mac_address'],
                    'created_at': ACTIVE_CONTROLLERS[controller_index]['created_at']
                })
                
                # Broadcast updated active controllers
                sio.emit('active_controllers', get_active_controllers_info())
            else:
                emit('error', 'Controller session not found')
    except Exception as e:
        emit('error', str(e))


@sio.on('leave_controller_session')
def on_leave_controller_session():
    """Leave the current controller session without removing the controller"""
    try:
        with user_info_lock:
            if request.sid in SESSION_TO_CONTROLLER:
                controller_index = SESSION_TO_CONTROLLER[request.sid]
                
                # Remove this client from the controller's client list
                if controller_index in ACTIVE_CONTROLLERS:
                    ACTIVE_CONTROLLERS[controller_index]['clients'].discard(request.sid)
                    
                    # Don't remove controller, just disconnect this session
                    print(f"Session {request.sid} left controller {controller_index}")
                
                del SESSION_TO_CONTROLLER[request.sid]
                
                # Clear user info controller data
                if "controller_index" in USER_INFO[request.sid]:
                    del USER_INFO[request.sid]["controller_index"]
                if "target_mac" in USER_INFO[request.sid]:
                    del USER_INFO[request.sid]["target_mac"]
                
                emit('left_controller_session', {'controller_index': controller_index})
                
                # Broadcast updated active controllers
                sio.emit('active_controllers', get_active_controllers_info())
    except Exception as e:
        emit('error', str(e))


@sio.on('force_remove_controller')
def on_force_remove_controller(controller_index):
    """Forcefully remove a controller session (admin action)"""
    try:
        controller_index = int(controller_index)
        
        with user_info_lock:
            if controller_index in ACTIVE_CONTROLLERS:
                # Notify all clients using this controller
                for client_id in ACTIVE_CONTROLLERS[controller_index]['clients'].copy():
                    sio.emit('controller_force_removed', {
                        'controller_index': controller_index
                    }, room=client_id)
                    
                    # Clean up session mappings
                    if client_id in SESSION_TO_CONTROLLER:
                        del SESSION_TO_CONTROLLER[client_id]
                    
                    # Clear user info
                    if client_id in USER_INFO:
                        USER_INFO[client_id].pop("controller_index", None)
                        USER_INFO[client_id].pop("target_mac", None)
                
                # Remove controller
                nxbt.remove_controller(controller_index)
                del ACTIVE_CONTROLLERS[controller_index]
                
                # Broadcast updated active controllers
                sio.emit('active_controllers', get_active_controllers_info())
                
                emit('controller_removed', {'controller_index': controller_index})
            else:
                emit('error', 'Controller not found')
    except Exception as e:
        emit('error', str(e))


@sio.on('input')
def handle_input(message):
    # print("Webapp Input", time.perf_counter())
    message = json.loads(message)
    index = message[0]
    input_packet = message[1]
    nxbt.set_controller_input(index, input_packet)


@sio.on('macro')
def handle_macro(message):
    message = json.loads(message)
    index = message[0]
    macro = message[1]
    
    # Start macro without blocking (non-blocking mode)
    macro_id = nxbt.macro(index, macro, block=False)
    
    # Track the running macro for this session
    with user_info_lock:
        RUNNING_MACROS[request.sid] = {
            'macro_id': macro_id,
            'controller_index': index,
            'macro_content': macro
        }
    
    # Emit macro started event
    emit('macro_started', {
        'macro_id': macro_id,
        'controller_index': index
    })
    
    # Start a background task to monitor macro completion
    sio.start_background_task(monitor_macro_completion, request.sid, index, macro_id)


@sio.on('stop_macro')
def handle_stop_macro():
    """Stop the currently running macro for this session"""
    try:
        with user_info_lock:
            if request.sid in RUNNING_MACROS:
                macro_info = RUNNING_MACROS[request.sid]
                macro_id = macro_info['macro_id']
                controller_index = macro_info['controller_index']
                
                # Stop the macro
                nxbt.stop_macro(controller_index, macro_id, block=False)
                
                # Clean up tracking
                del RUNNING_MACROS[request.sid]
                
                emit('macro_stopped', {
                    'macro_id': macro_id,
                    'controller_index': controller_index
                })
    except Exception as e:
        emit('error', str(e))


def monitor_macro_completion(session_id, controller_index, macro_id):
    """Background task to monitor when a macro completes"""
    try:
        while True:
            # Check if macro is finished
            if controller_index in nxbt.state:
                finished_macros = nxbt.state[controller_index].get('finished_macros', [])
                if macro_id in finished_macros:
                    # Macro completed
                    with user_info_lock:
                        if session_id in RUNNING_MACROS:
                            del RUNNING_MACROS[session_id]
                    
                    # Emit completion event to the specific client
                    sio.emit('macro_completed', {
                        'macro_id': macro_id,
                        'controller_index': controller_index
                    }, room=session_id)
                    break
            
            # Sleep for a short time before checking again
            sio.sleep(0.1)
    except Exception as e:
        print(f"Error monitoring macro completion: {e}")


@sio.on('get_macro_status')
def handle_get_macro_status():
    """Get the current macro status for this session"""
    with user_info_lock:
        if request.sid in RUNNING_MACROS:
            emit('macro_status', {
                'running': True,
                'macro_info': RUNNING_MACROS[request.sid]
            })
        else:
            emit('macro_status', {'running': False})


def start_web_app(ip='0.0.0.0', port=8000, usessl=False, cert_path=None):
    if usessl:
        if cert_path is None:
            # Store certs in the package directory
            cert_path = os.path.join(
                os.path.dirname(__file__), "cert.pem"
            )
            key_path = os.path.join(
                os.path.dirname(__file__), "key.pem"
            )
        else:
            # If specified, store certs at the user's preferred location
            cert_path = os.path.join(
                cert_path, "cert.pem"
            )
            key_path = os.path.join(
                cert_path, "key.pem"
            )
        if not os.path.isfile(cert_path) or not os.path.isfile(key_path):
            print(
                "\n"
                "-----------------------------------------\n"
                "---------------->WARNING<----------------\n"
                "The NXBT webapp is being run with self-\n"
                "signed SSL certificates for use on your\n"
                "local network.\n"
                "\n"
                "These certificates ARE NOT safe for\n"
                "production use. Please generate valid\n"
                "SSL certificates if you plan on using the\n"
                "NXBT webapp anywhere other than your own\n"
                "network.\n"
                "-----------------------------------------\n"
                "\n"
                "The above warning will only be shown once\n"
                "on certificate generation."
                "\n"
            )
            print("Generating certificates...")
            cert, key = generate_cert(gethostname())
            with open(cert_path, "wb") as f:
                f.write(cert)
            with open(key_path, "wb") as f:
                f.write(key)

        eventlet.wsgi.server(eventlet.wrap_ssl(eventlet.listen((ip, port)),
            certfile=cert_path, keyfile=key_path), app)
    else:
        eventlet.wsgi.server(eventlet.listen((ip, port)), app)


if __name__ == "__main__":
    start_web_app()
