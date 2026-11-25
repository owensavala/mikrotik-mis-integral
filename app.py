import json
import os
import datetime
import urllib.parse
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect
import routeros_api

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, 'templates'),
    static_folder=os.path.join(base_dir, 'static'),
)

# Secret key & Session security (HttpOnly, SameSite)
app.secret_key = os.environ.get('SECRET_KEY', 'mis-integral-admin-secret-2026-auth-key-!#')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=12),
)

# Vercel Serverless WSGI Path Middleware
class VercelPathFixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get('QUERY_STRING', '')
        if '__vercel_path=' in qs:
            parsed = urllib.parse.parse_qs(qs)
            if '__vercel_path' in parsed:
                real_path = parsed['__vercel_path'][0]
                if not real_path.startswith('/'):
                    real_path = '/' + real_path
                while '//' in real_path:
                    real_path = real_path.replace('//', '/')
                environ['PATH_INFO'] = real_path
                
                cleaned = {k: v for k, v in parsed.items() if k != '__vercel_path'}
                environ['QUERY_STRING'] = urllib.parse.urlencode(cleaned, doseq=True)
                return self.wsgi_app(environ, start_response)

        forwarded = (
            environ.get('HTTP_X_FORWARDED_PATH') or
            environ.get('HTTP_X_MATCHED_PATH') or
            environ.get('HTTP_X_ORIGINAL_URL') or
            environ.get('RAW_URI') or
            environ.get('REQUEST_URI')
        )
        if forwarded:
            path = forwarded.split('?')[0]
            if path in ['/api/index', '/api']:
                path = '/'
            environ['PATH_INFO'] = path
        else:
            path = environ.get('PATH_INFO', '')
            if path in ['/api/index', '/api']:
                environ['PATH_INFO'] = '/'
                
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

# On Vercel, the root filesystem is read-only. We use /tmp for runtime configs.
if os.environ.get('VERCEL'):
  CONFIG_PATH = '/tmp/config.json'
else:
  CONFIG_PATH = os.path.join(base_dir, 'config.json')


_in_memory_config = {
    "host": os.environ.get("MIKROTIK_HOST", "idn32.tunnel.id"),
    "port": int(os.environ.get("MIKROTIK_PORT", 3017)),
    "user": os.environ.get("MIKROTIK_USER", "admin"),
    "password": os.environ.get("MIKROTIK_PASSWORD", "0020913463"),
    "admin_user": os.environ.get("ADMIN_USER", "admin"),
    "admin_password": os.environ.get("ADMIN_PASSWORD", "admin123")
}

def load_config():
    default = dict(_in_memory_config)
    
    # Check base config first
    base_config_file = os.path.join(base_dir, 'config.json')
    if os.path.exists(base_config_file):
        try:
            with open(base_config_file, 'r') as f:
                file_cfg = json.load(f)
                default.update(file_cfg)
        except Exception:
            pass
            
    if os.path.exists(CONFIG_PATH) and CONFIG_PATH != base_config_file:
        try:
            with open(CONFIG_PATH, 'r') as f:
                file_cfg = json.load(f)
                default.update(file_cfg)
        except Exception:
            pass
            
    # Server Environment Variables take precedence over local files
    if os.environ.get("MIKROTIK_HOST"):
        default["host"] = os.environ.get("MIKROTIK_HOST")
    if os.environ.get("MIKROTIK_PORT"):
        try:
            default["port"] = int(os.environ.get("MIKROTIK_PORT"))
        except ValueError:
            pass
    if os.environ.get("MIKROTIK_USER"):
        default["user"] = os.environ.get("MIKROTIK_USER")
    if os.environ.get("MIKROTIK_PASSWORD"):
        default["password"] = os.environ.get("MIKROTIK_PASSWORD")
    if os.environ.get("ADMIN_USER"):
        default["admin_user"] = os.environ.get("ADMIN_USER")
    if os.environ.get("ADMIN_PASSWORD"):
        default["admin_password"] = os.environ.get("ADMIN_PASSWORD")
            
    _in_memory_config.update(default)
    return default

def save_config(cfg):
    _in_memory_config.update(cfg)
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Warning saving config: {e}")


def get_mikrotik_api():
  cfg = load_config()
  pool = routeros_api.RouterOsApiPool(
      cfg.get('host', 'idn32.tunnel.id'),
      username=cfg.get('user', 'admin'),
      password=cfg.get('password', ''),
      port=int(cfg.get('port', 3017)),
      plaintext_login=True,
      use_ssl=False,
  )
  return pool, pool.get_api()


def format_bps(bps):
  try:
    val = float(bps)
    if val >= 1000000:
      return f'{val / 1000000:.2f} Mbps'
    elif val >= 1000:
      return f'{val / 1000:.1f} Kbps'
    return f'{val:.0f} bps'
  except Exception:
    return '0 bps'


# ----------------------------------------------------
# AUTHENTICATION & ACCESS CONTROL MIDDLEWARE
# ----------------------------------------------------
@app.before_request
def require_authentication():
  # Public routes that do not require login
  allowed_routes = ['/login', '/api/login']
  if request.path.startswith('/static/') or request.path in allowed_routes:
    return None

  if not session.get('logged_in'):
    if request.path.startswith('/api/'):
      return jsonify({
          'success': False,
          'error': 'Akses ditolak. Sesi login telah berakhir atau belum login.',
          'unauthorized': True
      }), 401
    return redirect('/login')


@app.route('/login', methods=['GET'])
def login_page():
  if session.get('logged_in'):
    return redirect('/')
  return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
  data = request.json or {}
  username = data.get('username', '').strip()
  password = data.get('password', '')

  cfg = load_config()
  valid_user = cfg.get('admin_user', 'admin')
  valid_pass = cfg.get('admin_password', 'admin123')

  if username == valid_user and password == valid_pass:
    session.permanent = True
    session['logged_in'] = True
    session['admin_user'] = username
    return jsonify({'success': True, 'message': 'Login berhasil!'})
  
  return jsonify({'success': False, 'error': 'Username atau password admin salah!'}), 401


@app.route('/logout', methods=['GET'])
@app.route('/api/logout', methods=['POST', 'GET'])
def logout():
  session.clear()
  if request.path.startswith('/api/'):
    return jsonify({'success': True, 'message': 'Logout berhasil!'})
  return redirect('/login')


@app.route('/')
def index():
  cfg = load_config()
  has_env = bool(os.environ.get('MIKROTIK_HOST') or os.environ.get('MIKROTIK_PASSWORD'))
  safe_cfg = {
      'host': cfg.get('host', 'idn32.tunnel.id'),
      'port': cfg.get('port', 3017),
      'user': cfg.get('user', 'admin'),
      'has_password': bool(cfg.get('password')),
      'has_env': has_env,
      'admin_user': session.get('admin_user', 'admin'),
  }
  return render_template('index.html', config=safe_cfg)


@app.route('/static/<path:filename>')
def serve_static(filename):
  return send_from_directory(os.path.join(base_dir, 'static'), filename)


# ----------------------------------------------------
# 1. SYSTEM STATUS & CONTROL
# ----------------------------------------------------
@app.route('/api/status', methods=['GET'])
def get_status():
  pool = None
  try:
    pool, api = get_mikrotik_api()

    # System resources
    res = api.get_resource('/system/resource').get()
    system_info = res[0] if res else {}

    # Router Identity
    ident = api.get_resource('/system/identity').get()
    identity = ident[0].get('name', 'MikroTik') if ident else 'MikroTik'

    # Hotspot server status
    hs_list = api.get_resource('/ip/hotspot').get()
    hotspot_enabled = True
    if hs_list:
      disabled_val = hs_list[0].get('disabled', 'false')
      hotspot_enabled = disabled_val in ['false', False]

    # Active Hotspot Users
    active_users = []
    try:
      active_users = api.get_resource('/ip/hotspot/active').get()
    except Exception:
      pass

    # Active DHCP Leases (Klien Ujian ether3-LAN)
    exam_clients = []
    try:
      leases = api.get_resource('/ip/dhcp-server/lease').get()
      exam_clients = [
          l for l in leases
          if l.get('server') == 'dhcp1'
          or l.get('status') == 'bound'
          or l.get('address', '').startswith('192.168.100.')
      ]
    except Exception:
      pass

    # Total Registered Hotspot Users
    all_users = api.get_resource('/ip/hotspot/user').get()

    # Total Hotspot Profiles
    all_profiles = api.get_resource('/ip/hotspot/user/profile').get()

    # Interfaces status (Indibiz & Orbit)
    interfaces = api.get_resource('/interface').get()
    wan_status = {'indibiz': False, 'orbit': False}
    for iface in interfaces:
      name = iface.get('name', '').lower()
      running = iface.get('running') in ['true', True]
      if 'indibiz' in name or 'ether1' in name:
        wan_status['indibiz'] = running
      elif 'orbit' in name or 'ether2' in name:
        wan_status['orbit'] = running

    current_mode = 'HARIAN' if hotspot_enabled else 'UJIAN'
    hotspot_active_count = len(active_users)
    exam_active_count = len(exam_clients)
    active_users_count = exam_active_count if current_mode == 'UJIAN' else hotspot_active_count

    return jsonify({
        'success': True,
        'identity': identity,
        'mode': current_mode,
        'hotspot_enabled': hotspot_enabled,
        'cpu_load': system_info.get('cpu-load', '0') + '%',
        'free_memory': (
            str(int(system_info.get('free-memory', 0)) // 1024 // 1024) + ' MB'
        ),
        'total_memory': (
            str(int(system_info.get('total-memory', 0)) // 1024 // 1024) + ' MB'
        ),
        'uptime': system_info.get('uptime', '-'),
        'version': system_info.get('version', '-'),
        'board_name': system_info.get('board-name', '-'),
        'active_users_count': active_users_count,
        'hotspot_active_count': hotspot_active_count,
        'exam_active_count': exam_active_count,
        'total_users_count': len(all_users),
        'total_profiles_count': len(all_profiles),
        'wan': wan_status,
    })

  except Exception as e:
    return (
        jsonify({
            'success': False,
            'error': str(e),
            'message': (
                'Gagal terhubung ke MikroTik. Periksa pengaturan koneksi'
                ' host/port/user/password.'
            ),
        }),
        500,
    )
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/switch-mode', methods=['POST'])
def switch_mode():
  data = request.json or {}
  target_mode = data.get('mode', '').upper()
  if target_mode not in ['HARIAN', 'UJIAN']:
    return jsonify({'success': False, 'error': 'Mode tidak valid'}), 400

  pool = None
  try:
    pool, api = get_mikrotik_api()
    hs_res = api.get_resource('/ip/hotspot')
    queue_res = api.get_resource('/queue/simple')

    hotspots = hs_res.get()
    queues = queue_res.get()

    if target_mode == 'UJIAN':
      for hs in hotspots:
        hs_res.set(id=hs['id'], disabled='true')
      for q in queues:
        q_name = q.get('name', '').lower()
        if 'terkunci' in q_name or 'limitet' in q_name:
          queue_res.set(id=q['id'], disabled='false')
      # Clear active hotspot sessions & cookies if any
      for path in ['/ip/hotspot/active', '/ip/hotspot/cookie']:
        try:
          res = api.get_resource(path)
          for item in res.get():
            try:
              res.remove(id=item['id'])
            except Exception:
              pass
        except Exception:
          pass
      msg = (
          'Berhasil beralih ke MODE UJIAN! Hotspot dinonaktifkan dan pembagian'
          ' bandwidth PCQ aktif.'
      )
    else:
      # 1. Enable Hotspot server(s)
      for hs in hotspots:
        hs_res.set(id=hs['id'], disabled='false')
      # 2. Disable exam PCQ queue so teachers get Hotspot Profile speed
      for q in queues:
        q_name = q.get('name', '').lower()
        if 'terkunci' in q_name or 'limitet' in q_name:
          queue_res.set(id=q['id'], disabled='true')
      # 3. Force logout all existing hotspot sessions, cookies, hosts & flush
      #    active firewall connections directly on MikroTik (instant, zero timeout)
      flush_script = (
          '/ip hotspot active remove [find]; '
          '/ip hotspot cookie remove [find]; '
          '/ip hotspot host remove [find bypassed=no]; '
          '/ip firewall connection remove [find src-address~"^192\\\\.168\\\\.100\\\\."]; '
          '/ip firewall connection remove [find src-address~"^192\\\\.168\\\\.200\\\\."]'
      )
      try:
        api.get_resource('/').call('execute', {'script': flush_script})
      except Exception:
        # Fallback: remove active hotspot sessions via resource API
        for path in ['/ip/hotspot/active', '/ip/hotspot/cookie']:
          try:
            res = api.get_resource(path)
            for item in res.get():
              try:
                res.remove(id=item['id'])
              except Exception:
                pass
          except Exception:
            pass
      msg = (
          'Berhasil beralih ke MODE HARIAN! Hotspot aktif & semua sesi koneksi'
          ' lama telah diputus (wajib login ulang).'
      )

    return jsonify({'success': True, 'mode': target_mode, 'message': msg})
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/traffic', methods=['GET'])
def get_traffic():
  pool = None
  try:
    pool, api = get_mikrotik_api()
    # Detect actual WAN 1 interface name (ether1-Telkom or ether1-indibiz)
    all_ifaces = [i.get('name', '') for i in api.get_resource('/interface').get()]
    wan1_name = next((n for n in all_ifaces if n.lower().startswith('ether1')), 'ether1-Telkom')
    wan2_name = next((n for n in all_ifaces if n.lower().startswith('ether2')), 'ether2-Orbit')
    lan_name = next((n for n in all_ifaces if n.lower().startswith('ether3')), 'ether3-LAN')

    iface_map = {
        'ether1-indibiz': wan1_name,
        'ether2-Orbit': wan2_name,
        'ether3-LAN': lan_name,
        'terkunci': 'terkunci',
    }
    traffic_data = {}

    for key_name, real_iface in iface_map.items():
      try:
        mon = api.get_resource('/interface').call(
            'monitor-traffic', {'interface': real_iface, 'once': ''}
        )
        if mon:
          rx = mon[0].get('rx-bits-per-second', 0)
          tx = mon[0].get('tx-bits-per-second', 0)
          traffic_data[key_name] = {
              'rx_formatted': format_bps(rx),
              'tx_formatted': format_bps(tx),
              'rx_raw': int(rx),
              'tx_raw': int(tx),
          }
      except Exception:
        traffic_data[key_name] = {
            'rx_formatted': '0 bps',
            'tx_formatted': '0 bps',
            'rx_raw': 0,
            'tx_raw': 0,
        }

    return jsonify({'success': True, 'traffic': traffic_data})
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


# ----------------------------------------------------
# 2. ACTIVE USERS & EXAM CLIENTS
# ----------------------------------------------------
@app.route('/api/users/active', methods=['GET'])
def get_active_users():
  pool = None
  try:
    pool, api = get_mikrotik_api()

    # 1. Determine current network mode
    hs_list = api.get_resource('/ip/hotspot').get()
    hotspot_enabled = True
    if hs_list:
      disabled_val = hs_list[0].get('disabled', 'false')
      hotspot_enabled = disabled_val in ['false', False]
    current_mode = 'HARIAN' if hotspot_enabled else 'UJIAN'

    # Filter parameter: 'auto' (default), 'dhcp' (klien ujian), 'hotspot' (guru), 'all'
    view_type = request.args.get('type', 'auto').lower()
    if view_type == 'auto':
      target_type = 'dhcp' if current_mode == 'UJIAN' else 'hotspot'
    else:
      target_type = view_type

    # 2. Fetch Hotspot Active Users
    hotspot_users = []
    try:
      hs_active = api.get_resource('/ip/hotspot/active').get()
      for u in hs_active:
        hotspot_users.append({
            'id': u.get('id') or u.get('.id'),
            'type': 'hotspot',
            'user': u.get('user', '-'),
            'name': u.get('user', '-'),
            'address': u.get('address', '-'),
            'mac': u.get('mac-address', '-'),
            'uptime': u.get('uptime', '-'),
            'bytes_in': u.get('bytes-in-nice', u.get('bytes-in', '-')),
            'bytes_out': u.get('bytes-out-nice', u.get('bytes-out', '-')),
            'server': 'terkunci (Hotspot)',
            'status': 'Aktif Login',
        })
    except Exception:
      pass

    # 3. Fetch DHCP Leases & ARP for Exam Clients (ether3-LAN)
    dhcp_clients = []
    try:
      dhcp_leases = api.get_resource('/ip/dhcp-server/lease').get()
      arp_list = api.get_resource('/ip/arp').get()
      arp_active_ips = {a.get('address'): a for a in arp_list if a.get('complete') in ['true', True]}

      for l in dhcp_leases:
        status = l.get('status', 'bound')
        addr = l.get('address', l.get('active-address', '-'))
        mac = l.get('mac-address', l.get('active-mac-address', '-'))
        hostname = l.get('host-name', '').strip()
        server = l.get('server', l.get('active-server', 'dhcp1'))

        # Only list bound/active leases or ether3-LAN leases
        if status in ['bound', 'waiting', 'busy'] or addr.startswith('192.168.100.'):
          display_name = hostname if hostname else f'Perangkat Ujian ({addr})'
          server_label = 'ether3-LAN (dhcp1)' if server == 'dhcp1' else f'{server} (Hotspot)'
          is_online = addr in arp_active_ips

          dhcp_clients.append({
              'id': l.get('id') or l.get('.id'),
              'type': 'dhcp',
              'user': display_name,
              'name': display_name,
              'hostname': hostname or '-',
              'address': addr,
              'mac': mac,
              'uptime': l.get('age', l.get('last-seen', '-')),
              'expires_after': l.get('expires-after', '-'),
              'last_seen': l.get('last-seen', '-'),
              'server': server_label,
              'status': 'Aktif (Online)' if is_online else f'Lease ({status})',
              'bytes_in': '-',
              'bytes_out': '-',
          })
    except Exception:
      pass

    if target_type == 'dhcp':
      result_users = dhcp_clients
    elif target_type == 'hotspot':
      result_users = hotspot_users
    else:  # 'all'
      result_users = hotspot_users + dhcp_clients

    return jsonify({
        'success': True,
        'mode': current_mode,
        'target_type': target_type,
        'hotspot_count': len(hotspot_users),
        'exam_count': len(dhcp_clients),
        'total_count': len(result_users),
        'users': result_users,
    })
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/users/kick', methods=['POST'])
def kick_user():
  data = request.json or {}
  user_id = data.get('id')
  user_type = data.get('type', 'hotspot')
  if not user_id:
    return jsonify({'success': False, 'error': 'ID user tidak ditemukan'}), 400

  pool = None
  try:
    pool, api = get_mikrotik_api()
    if user_type == 'dhcp':
      api.get_resource('/ip/dhcp-server/lease').remove(id=user_id)
      return jsonify({
          'success': True,
          'message': 'Sesi lease DHCP perangkat ujian berhasil di-reset!',
      })
    else:
      api.get_resource('/ip/hotspot/active').remove(id=user_id)
      return jsonify({'success': True, 'message': 'User hotspot berhasil dikeluarkan!'})
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass



# ----------------------------------------------------
# 3. HOTSPOT USERS CRUD (/ip/hotspot/user)
# ----------------------------------------------------
@app.route('/api/hotspot/users', methods=['GET'])
def list_hotspot_users():
  pool = None
  try:
    pool, api = get_mikrotik_api()
    users = api.get_resource('/ip/hotspot/user').get()
    result = []
    for u in users:
      result.append({
          'id': u.get('id') or u.get('.id'),
          'name': u.get('name', ''),
          'password': u.get('password', '******'),
          'profile': u.get('profile', 'default'),
          'comment': u.get('comment', ''),
          'uptime': u.get('uptime', '0s'),
          'bytes_in': u.get('bytes-in', '0'),
          'bytes_out': u.get('bytes-out', '0'),
          'disabled': u.get('disabled') in ['true', True],
      })
    return jsonify({'success': True, 'users': result})
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/hotspot/users/add', methods=['POST'])
def add_hotspot_user():
  data = request.json or {}
  name = data.get('name', '').strip()
  password = data.get('password', '').strip()
  profile = data.get('profile', 'default')
  comment = data.get('comment', '').strip()

  if not name:
    return jsonify({'success': False, 'error': 'Username wajib diisi!'}), 400

  pool = None
  try:
    pool, api = get_mikrotik_api()
    params = {'name': name, 'profile': profile, 'server': 'hotspot1'}
    if password:
      params['password'] = password
    if comment:
      params['comment'] = comment

    api.get_resource('/ip/hotspot/user').add(**params)
    return jsonify(
        {'success': True, 'message': f'Pengguna {name} berhasil ditambahkan!'}
    )
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/hotspot/users/edit', methods=['POST'])
def edit_hotspot_user():
  data = request.json or {}
  user_id = data.get('id')
  name = data.get('name', '').strip()
  password = data.get('password', '').strip()
  profile = data.get('profile', 'default')
  comment = data.get('comment', '').strip()

  if not user_id or not name:
    return jsonify({'success': False, 'error': 'ID dan Nama wajib diisi!'}), 400

  pool = None
  try:
    pool, api = get_mikrotik_api()
    params = {'id': user_id, 'name': name, 'profile': profile}
    if password:
      params['password'] = password
    params['comment'] = comment

    api.get_resource('/ip/hotspot/user').set(**params)
    return jsonify(
        {'success': True, 'message': f'Data user {name} berhasil diperbarui!'}
    )
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/hotspot/users/delete', methods=['POST'])
def delete_hotspot_user():
  data = request.json or {}
  user_id = data.get('id')
  if not user_id:
    return jsonify({'success': False, 'error': 'ID user tidak ditemukan'}), 400

  pool = None
  try:
    pool, api = get_mikrotik_api()
    api.get_resource('/ip/hotspot/user').remove(id=user_id)
    return jsonify({'success': True, 'message': 'User berhasil dihapus!'})
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


# ----------------------------------------------------
# 4. HOTSPOT USER PROFILES CRUD (/ip/hotspot/user/profile)
# ----------------------------------------------------
@app.route('/api/hotspot/profiles', methods=['GET'])
def list_hotspot_profiles():
  pool = None
  try:
    pool, api = get_mikrotik_api()
    profiles = api.get_resource('/ip/hotspot/user/profile').get()
    result = []
    for p in profiles:
      result.append({
          'id': p.get('id') or p.get('.id'),
          'name': p.get('name', ''),
          'rate_limit': p.get('rate-limit', 'Unlimited'),
          'shared_users': p.get('shared-users', '1'),
          'default': p.get('default') in ['true', True],
      })
    return jsonify({'success': True, 'profiles': result})
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/hotspot/profiles/add', methods=['POST'])
def add_hotspot_profile():
  data = request.json or {}
  name = data.get('name', '').strip()
  rate_limit = data.get('rate_limit', '').strip()
  shared_users = str(data.get('shared_users', 1)).strip()

  if not name:
    return jsonify({'success': False, 'error': 'Nama profil wajib diisi!'}), 400

  pool = None
  try:
    pool, api = get_mikrotik_api()
    params = {'name': name, 'shared-users': shared_users}
    if rate_limit:
      params['rate-limit'] = rate_limit

    api.get_resource('/ip/hotspot/user/profile').add(**params)
    return jsonify(
        {'success': True, 'message': f'Profil {name} berhasil ditambahkan!'}
    )
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/hotspot/profiles/edit', methods=['POST'])
def edit_hotspot_profile():
  data = request.json or {}
  prof_id = data.get('id')
  name = data.get('name', '').strip()
  rate_limit = data.get('rate_limit', '').strip()
  shared_users = str(data.get('shared_users', 1)).strip()

  if not prof_id or not name:
    return (
        jsonify({'success': False, 'error': 'ID dan Nama profil wajib diisi!'}),
        400,
    )

  pool = None
  try:
    pool, api = get_mikrotik_api()
    params = {'id': prof_id, 'name': name, 'shared-users': shared_users}
    if rate_limit:
      params['rate-limit'] = rate_limit

    api.get_resource('/ip/hotspot/user/profile').set(**params)
    return jsonify(
        {'success': True, 'message': f'Profil {name} berhasil diperbarui!'}
    )
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/hotspot/profiles/delete', methods=['POST'])
def delete_hotspot_profile():
  data = request.json or {}
  prof_id = data.get('id')
  if not prof_id:
    return (
        jsonify({'success': False, 'error': 'ID profil tidak ditemukan'}),
        400,
    )

  pool = None
  try:
    pool, api = get_mikrotik_api()
    api.get_resource('/ip/hotspot/user/profile').remove(id=prof_id)
    return jsonify({'success': True, 'message': 'Profil berhasil dihapus!'})
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


# ----------------------------------------------------
# 5. CONFIGURATION & MAINTENANCE
# ----------------------------------------------------
@app.route('/api/reboot', methods=['POST'])
def reboot_router():
  pool = None
  try:
    pool, api = get_mikrotik_api()
    # Use a 2-second self-cleaning scheduler so API responds cleanly before router drops socket
    sched_res = api.get_resource('/system/scheduler')
    for s in sched_res.get():
      if s.get('name') == 'web-reboot':
        try:
          sched_res.remove(id=s['id'])
        except Exception:
          pass
    sched_res.add(
        name='web-reboot',
        interval='00:00:02',
        **{
            'on-event': (
                '/system scheduler remove [find name=web-reboot]; /system'
                ' reboot'
            )
        },
    )
    return jsonify({
        'success': True,
        'message': (
            'Perintah reboot berhasil dijadwalkan! Router MikroTik akan'
            ' restart dalam 2 detik.'
        ),
    })
  except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500
  finally:
    if pool:
      try:
        pool.disconnect()
      except Exception:
        pass


@app.route('/api/save-config', methods=['POST'])
def save_settings():
  data = request.json or {}
  cfg = load_config()

  if 'host' in data and data['host'].strip():
    cfg['host'] = data['host'].strip()
  if 'port' in data and str(data['port']).strip():
    try:
      cfg['port'] = int(data['port'])
    except ValueError:
      pass
  if 'user' in data and data['user'].strip():
    cfg['user'] = data['user'].strip()
  if 'password' in data and data['password'] != '':
    cfg['password'] = data['password']
  if 'admin_password' in data and data['admin_password'].strip() != '':
    cfg['admin_password'] = data['admin_password'].strip()

  save_config(cfg)
  return jsonify(
      {'success': True, 'message': 'Pengaturan berhasil disimpan!'}
  )



if __name__ == '__main__':
  print('====================================================')
  print('  PANEL ADMIN MIKROTIK - MIS INTEGRAL TERNATE')
  print('  Akses Dashboard: http://localhost:5000')
  print('====================================================')
  app.run(host='0.0.0.0', port=5000, debug=True)
