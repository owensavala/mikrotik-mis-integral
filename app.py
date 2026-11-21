import json
import os
from flask import Flask, render_template, request, jsonify
import routeros_api

base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, 'templates'),
    static_folder=os.path.join(base_dir, 'static'),
)

# On Vercel, the root filesystem is read-only. We use /tmp for runtime configs.
if os.environ.get('VERCEL'):
  CONFIG_PATH = '/tmp/config.json'
else:
  CONFIG_PATH = os.path.join(base_dir, 'config.json')


def load_config():
  default = {
      'host': os.environ.get('MIKROTIK_HOST', 'idn32.tunnel.id'),
      'port': int(os.environ.get('MIKROTIK_PORT', 3017)),
      'user': os.environ.get('MIKROTIK_USER', 'admin'),
      'password': os.environ.get('MIKROTIK_PASSWORD', ''),
  }

  # Check base config first if /tmp doesn't exist yet
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

  return default


def save_config(cfg):
  try:
    with open(CONFIG_PATH, 'w') as f:
      json.dump(cfg, f, indent=2)
  except Exception as e:
    print(f'Warning saving config: {e}')


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


@app.route('/')
def index():
  cfg = load_config()
  safe_cfg = {
      'host': cfg.get('host', 'idn32.tunnel.id'),
      'port': cfg.get('port', 3017),
      'user': cfg.get('user', 'admin'),
      'has_password': bool(cfg.get('password')),
  }
  return render_template('index.html', config=safe_cfg)


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
    active_users = api.get_resource('/ip/hotspot/active').get()

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
        'active_users_count': len(active_users),
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
      msg = (
          'Berhasil beralih ke MODE UJIAN! Hotspot dinonaktifkan dan pembagian'
          ' bandwidth PCQ aktif.'
      )
    else:
      for hs in hotspots:
        hs_res.set(id=hs['id'], disabled='false')
      for q in queues:
        q_name = q.get('name', '').lower()
        if 'terkunci' in q_name:
          queue_res.set(id=q['id'], disabled='true')
      msg = (
          'Berhasil beralih ke MODE HARIAN! Hotspot aktif (Akses khusus guru).'
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
    ifaces = ['ether1-indibiz', 'ether2-Orbit', 'ether3-LAN', 'terkunci']
    traffic_data = {}

    for iface in ifaces:
      try:
        mon = api.get_resource('/interface').call(
            'monitor-traffic', {'interface': iface, 'once': ''}
        )
        if mon:
          rx = mon[0].get('rx-bits-per-second', 0)
          tx = mon[0].get('tx-bits-per-second', 0)
          traffic_data[iface] = {
              'rx_formatted': format_bps(rx),
              'tx_formatted': format_bps(tx),
              'rx_raw': int(rx),
              'tx_raw': int(tx),
          }
      except Exception:
        traffic_data[iface] = {
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
# 2. ACTIVE USERS
# ----------------------------------------------------
@app.route('/api/users/active', methods=['GET'])
def get_active_users():
  pool = None
  try:
    pool, api = get_mikrotik_api()
    active_users = api.get_resource('/ip/hotspot/active').get()
    users_data = []
    for u in active_users:
      users_data.append({
          'id': u.get('id') or u.get('.id'),
          'user': u.get('user', '-'),
          'address': u.get('address', '-'),
          'mac': u.get('mac-address', '-'),
          'uptime': u.get('uptime', '-'),
          'bytes_in': u.get('bytes-in-nice', u.get('bytes-in', '-')),
          'bytes_out': u.get('bytes-out-nice', u.get('bytes-out', '-')),
      })
    return jsonify({'success': True, 'users': users_data})
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
  if not user_id:
    return jsonify({'success': False, 'error': 'ID user tidak ditemukan'}), 400

  pool = None
  try:
    pool, api = get_mikrotik_api()
    api.get_resource('/ip/hotspot/active').remove(id=user_id)
    return jsonify({'success': True, 'message': 'User berhasil dikeluarkan!'})
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
    api.get_resource('/system').call('reboot')
    return jsonify(
        {'success': True, 'message': 'Perintah reboot terkirim ke MikroTik!'}
    )
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

  if 'host' in data:
    cfg['host'] = data['host'].strip()
  if 'port' in data:
    cfg['port'] = int(data['port'])
  if 'user' in data:
    cfg['user'] = data['user'].strip()
  if 'password' in data and data['password'] != '':
    cfg['password'] = data['password']

  save_config(cfg)
  return jsonify(
      {'success': True, 'message': 'Pengaturan koneksi berhasil disimpan!'}
  )


if __name__ == '__main__':
  print('====================================================')
  print('  PANEL ADMIN MIKROTIK - MIS INTEGRAL TERNATE')
  print('  Akses Dashboard: http://localhost:5000')
  print('====================================================')
  app.run(host='0.0.0.0', port=5000, debug=True)
