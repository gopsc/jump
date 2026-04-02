from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import paramiko
import threading
import json
import time
import uuid
import os
import logging
import websockets
from websockets.sync.server import serve

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ==================== 初始化应用 ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'bastion-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bastion.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 启用 CORS
CORS(app, 
     supports_credentials=True,
     origins=['*'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD'],
     allow_headers=['*'])

# 初始化扩展
db = SQLAlchemy(app)

# ==================== 数据库模型 ====================
class Server(db.Model):
    __tablename__ = 'servers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, default=22)
    username = db.Column(db.String(80), nullable=False)
    password = db.Column(db.String(255))
    ssh_key = db.Column(db.Text)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SessionLog(db.Model):
    __tablename__ = 'session_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, default='unknown')
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    session_id = db.Column(db.String(100), unique=True)
    start_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    end_time = db.Column(db.DateTime)
    commands = db.Column(db.Text, default='[]')
    ip_address = db.Column(db.String(45), default='unknown')

# ==================== SSH连接管理 ====================
class SSHConnection:
    def __init__(self, server, session_id, username, websocket):
        self.server = server
        self.session_id = session_id
        self.username = username
        self.websocket = websocket
        self.client = None
        self.channel = None
        self.is_connected = False
        self.running = True
        
    def connect(self):
        try:
            logger.info(f"正在连接到服务器 {self.server.host}:{self.server.port} 用户 {self.server.username}")
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_kwargs = {
                'hostname': self.server.host,
                'port': self.server.port,
                'username': self.server.username,
                'timeout': 10,
                'allow_agent': False,
                'look_for_keys': False
            }
            
            if self.server.password:
                connect_kwargs['password'] = self.server.password
                logger.info("使用密码认证")
            
            self.client.connect(**connect_kwargs)
            logger.info(f"SSH连接成功，正在创建shell会话")
            
            self.channel = self.client.invoke_shell(term='xterm-256color', width=120, height=40)
            self.channel.settimeout(0.1)
            self.is_connected = True
            
            output_thread = threading.Thread(target=self._read_output, daemon=True)
            output_thread.start()
            logger.info(f"SSH会话创建成功，session_id: {self.session_id}")
            
            return True, "连接成功"
        except Exception as e:
            logger.error(f"连接错误: {e}")
            return False, str(e)
    
    def _read_output(self):
        logger.info(f"开始读取输出，session_id: {self.session_id}")
        while self.running and self.is_connected:
            try:
                if self.channel and self.channel.recv_ready():
                    output = self.channel.recv(65535).decode('utf-8', errors='ignore')
                    if output:
                        logger.debug(f"收到输出: {len(output)} 字节")
                        response = json.dumps({
                            'type': 'output',
                            'session_id': self.session_id,
                            'data': output
                        })
                        try:
                            self.websocket.send(response)
                        except Exception as e:
                            logger.error(f"发送输出失败: {e}")
                            break
                else:
                    time.sleep(0.05)
            except Exception as e:
                if self.running:
                    logger.error(f"读取输出错误: {e}")
                break
        logger.info(f"停止读取输出，session_id: {self.session_id}")
    
    def execute_command(self, command):
        if not self.is_connected or not self.channel:
            return False, "连接已断开"
        
        try:
            logger.debug(f"执行命令: {command[:50]}...")
            self.channel.send(command)
            return True, None
        except Exception as e:
            logger.error(f"命令执行错误: {e}")
            return False, str(e)
    
    def resize_pty(self, width, height):
        if self.channel:
            try:
                logger.debug(f"调整终端大小: {width}x{height}")
                self.channel.resize_pty(width=width, height=height)
            except Exception as e:
                logger.error(f"调整终端大小错误: {e}")
    
    def close(self):
        logger.info(f"关闭SSH连接，session_id: {self.session_id}")
        self.running = False
        self.is_connected = False
        if self.channel:
            try:
                self.channel.close()
            except:
                pass
        if self.client:
            try:
                self.client.close()
            except:
                pass

class SSHManager:
    def __init__(self):
        self.connections = {}
        self.lock = threading.Lock()
        
    def create_connection(self, server, username, websocket):
        session_id = str(uuid.uuid4())
        conn = SSHConnection(server, session_id, username, websocket)
        with self.lock:
            self.connections[session_id] = conn
        logger.info(f"创建SSH连接记录，session_id: {session_id}")
        return session_id, conn
    
    def get_connection(self, session_id):
        with self.lock:
            return self.connections.get(session_id)
    
    def close_connection(self, session_id):
        with self.lock:
            if session_id in self.connections:
                logger.info(f"关闭SSH连接，session_id: {session_id}")
                self.connections[session_id].close()
                del self.connections[session_id]

ssh_manager = SSHManager()

# ==================== 辅助函数 ====================
def get_username_from_request():
    username = request.headers.get('X-Proxy-User')
    if username:
        return username
    username = session.get('bastion_username')
    if username:
        return username
    return 'admin'

def set_username(username):
    session['bastion_username'] = username

# ==================== API 接口 ====================
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username', '')
        
        if not username or not username.strip():
            return jsonify({'error': '用户名不能为空'}), 400
        
        set_username(username)
        
        return jsonify({
            'message': '登录成功',
            'user': {'username': username, 'is_admin': True}
        })
    except Exception as e:
        return jsonify({'error': f'登录失败: {str(e)}'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': '登出成功'})

@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    username = get_username_from_request()
    return jsonify({
        'username': username,
        'is_admin': True,
        'authenticated': True
    })

@app.route('/api/servers', methods=['GET'])
def get_servers():
    try:
        servers = Server.query.all()
        result = [{
            'id': s.id,
            'name': s.name,
            'host': s.host,
            'port': s.port,
            'username': s.username,
            'description': s.description
        } for s in servers]
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取服务器列表失败: {str(e)}")
        return jsonify([])

@app.route('/api/servers', methods=['POST'])
def create_server():
    try:
        data = request.json
        
        required_fields = ['name', 'host', 'username']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'字段 {field} 不能为空'}), 400
        
        server = Server(
            name=data['name'],
            host=data['host'],
            port=data.get('port', 22),
            username=data['username'],
            password=data.get('password'),
            description=data.get('description', '')
        )
        
        db.session.add(server)
        db.session.commit()
        
        return jsonify({'message': '服务器创建成功', 'id': server.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'创建失败: {str(e)}'}), 500

@app.route('/api/servers/<int:server_id>', methods=['GET'])
def get_server(server_id):
    try:
        server = db.session.get(Server, server_id)
        if not server:
            return jsonify({'error': '服务器不存在'}), 404
        
        return jsonify({
            'id': server.id,
            'name': server.name,
            'host': server.host,
            'port': server.port,
            'username': server.username,
            'description': server.description
        })
    except Exception as e:
        return jsonify({'error': f'获取服务器信息失败: {str(e)}'}), 500

@app.route('/api/servers/<int:server_id>', methods=['PUT'])
def update_server(server_id):
    try:
        server = db.session.get(Server, server_id)
        if not server:
            return jsonify({'error': '服务器不存在'}), 404
        
        data = request.json
        
        if 'name' in data and data['name']:
            server.name = data['name']
        if 'host' in data and data['host']:
            server.host = data['host']
        if 'port' in data:
            server.port = data['port']
        if 'username' in data and data['username']:
            server.username = data['username']
        if 'password' in data and data['password']:
            server.password = data['password']
        if 'description' in data:
            server.description = data['description']
        
        db.session.commit()
        
        return jsonify({'message': '服务器更新成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新失败: {str(e)}'}), 500

@app.route('/api/servers/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    try:
        server = db.session.get(Server, server_id)
        if not server:
            return jsonify({'error': '服务器不存在'}), 404
        
        to_delete = []
        for session_id, conn in list(ssh_manager.connections.items()):
            if conn.server.id == server_id:
                conn.close()
                to_delete.append(session_id)
        
        for session_id in to_delete:
            ssh_manager.close_connection(session_id)
        
        SessionLog.query.filter_by(server_id=server_id).delete()
        db.session.delete(server)
        db.session.commit()
        
        return jsonify({'message': '服务器删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'删除失败: {str(e)}'}), 500

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    try:
        username = get_username_from_request()
        
        try:
            if username and username != 'admin':
                sessions = SessionLog.query.filter_by(username=username).order_by(SessionLog.start_time.desc()).all()
            else:
                sessions = SessionLog.query.order_by(SessionLog.start_time.desc()).all()
        except Exception as e:
            logger.warning(f"查询会话失败: {e}")
            return jsonify([])
        
        result = []
        for s in sessions:
            server = db.session.get(Server, s.server_id)
            server_name = server.name if server else '未知服务器'
            
            result.append({
                'id': s.id,
                'username': s.username,
                'server_name': server_name,
                'server_id': s.server_id,
                'start_time': s.start_time.isoformat() if s.start_time else None,
                'end_time': s.end_time.isoformat() if s.end_time else None,
                'session_id': s.session_id
            })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        return jsonify([])

@app.route('/api/sessions/<session_id>', methods=['GET'])
def get_session_detail(session_id):
    try:
        log = SessionLog.query.filter_by(session_id=session_id).first()
        if not log:
            return jsonify({'error': '会话不存在'}), 404
        
        server = db.session.get(Server, log.server_id)
        
        commands = []
        if log.commands:
            try:
                commands = json.loads(log.commands)
            except:
                commands = []
        
        return jsonify({
            'id': log.id,
            'username': log.username,
            'server': server.name if server else '未知服务器',
            'server_id': log.server_id,
            'start_time': log.start_time.isoformat() if log.start_time else None,
            'end_time': log.end_time.isoformat() if log.end_time else None,
            'commands': commands
        })
    except Exception as e:
        return jsonify({'error': f'获取会话详情失败: {str(e)}'}), 500

# ==================== WebSocket 处理 ====================
def handle_websocket(websocket):
    """处理 WebSocket 连接 - 保持长连接"""
    client_id = str(uuid.uuid4())[:8]
    logger.info(f'WebSocket 客户端连接: {client_id}')
    
    try:
        # 发送欢迎消息
        websocket.send(json.dumps({'type': 'info', 'message': 'WebSocket connected'}))
        logger.info(f'已发送欢迎消息到 {client_id}')
        
        # 持续接收消息
        while True:
            try:
                message = websocket.recv()
                if message is None:
                    logger.info(f'WebSocket 客户端 {client_id} 断开')
                    break
                
                logger.info(f'收到消息 [{client_id}]: {message[:200]}')
                
                try:
                    msg = json.loads(message)
                    msg_type = msg.get('type')
                    
                    if msg_type == 'connect_server':
                        server_id = msg.get('server_id')
                        username = msg.get('username', 'admin')
                        cols = msg.get('cols', 80)
                        rows = msg.get('rows', 24)
                        
                        logger.info(f'连接服务器请求: server_id={server_id}, username={username}')
                        
                        # 获取服务器信息
                        with app.app_context():
                            server = db.session.get(Server, server_id)
                        
                        if not server:
                            error_msg = json.dumps({'type': 'error', 'message': f'服务器不存在: {server_id}'})
                            websocket.send(error_msg)
                            continue
                        
                        session_id, conn = ssh_manager.create_connection(server, username, websocket)
                        success, message = conn.connect()
                        
                        if success:
                            try:
                                conn.resize_pty(cols, rows)
                            except:
                                pass
                            
                            with app.app_context():
                                log = SessionLog(
                                    username=username,
                                    server_id=server_id,
                                    session_id=session_id,
                                    start_time=datetime.now(timezone.utc),
                                    ip_address='websocket'
                                )
                                db.session.add(log)
                                db.session.commit()
                            
                            logger.info(f'用户 {username} 成功连接到服务器 {server.name}')
                            
                            response = json.dumps({
                                'type': 'connected',
                                'session_id': session_id,
                                'message': '连接成功'
                            })
                            websocket.send(response)
                            logger.info(f'已发送连接成功响应')
                        else:
                            error_msg = json.dumps({'type': 'error', 'message': f'连接失败: {message}'})
                            websocket.send(error_msg)
                            
                    elif msg_type == 'command':
                        session_id = msg.get('session_id')
                        command = msg.get('command')
                        
                        conn = ssh_manager.get_connection(session_id)
                        if not conn:
                            error_msg = json.dumps({'type': 'error', 'message': '连接已断开'})
                            websocket.send(error_msg)
                            continue
                        
                        success, error = conn.execute_command(command)
                        if not success:
                            error_msg = json.dumps({'type': 'error', 'message': f'命令执行失败: {error}'})
                            websocket.send(error_msg)
                        
                    elif msg_type == 'resize':
                        session_id = msg.get('session_id')
                        cols = msg.get('cols', 80)
                        rows = msg.get('rows', 24)
                        
                        conn = ssh_manager.get_connection(session_id)
                        if conn:
                            conn.resize_pty(cols, rows)
                            
                    elif msg_type == 'disconnect_server':
                        session_id = msg.get('session_id')
                        if session_id:
                            ssh_manager.close_connection(session_id)
                            with app.app_context():
                                log = SessionLog.query.filter_by(session_id=session_id).first()
                                if log and not log.end_time:
                                    log.end_time = datetime.now(timezone.utc)
                                    db.session.commit()
                            response = json.dumps({'type': 'disconnected', 'message': '连接已断开'})
                            websocket.send(response)
                            
                except json.JSONDecodeError as e:
                    logger.error(f'JSON 解析错误: {e}')
                except Exception as e:
                    logger.error(f"处理消息错误: {e}", exc_info=True)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.info(f'WebSocket 连接已关闭: {client_id}')
                break
            except Exception as e:
                logger.error(f"WebSocket 接收错误: {e}")
                break
                
    except Exception as e:
        logger.error(f'WebSocket 处理错误: {client_id}, {e}')
    finally:
        # 关闭所有相关连接
        to_delete = []
        for session_id, conn in list(ssh_manager.connections.items()):
            if hasattr(conn, 'websocket') and conn.websocket == websocket:
                conn.close()
                to_delete.append(session_id)
        for session_id in to_delete:
            ssh_manager.close_connection(session_id)
        
        logger.info(f'WebSocket 客户端清理完成: {client_id}')

def start_websocket_server():
    """启动 WebSocket 服务器"""
    try:
        with serve(handle_websocket, "0.0.0.0", 5002) as server:
            logger.info("WebSocket 服务器启动在端口 5002")
            server.serve_forever()
    except Exception as e:
        logger.error(f"WebSocket 服务器启动失败: {e}")

# ==================== 根路径 ====================
@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': 'Bastion Server Running', 'websocket': 'ws://localhost:5002'})

# ==================== 启动应用 ====================
if __name__ == '__main__':
    with app.app_context():
        db_path = 'bastion.db'
        if os.path.exists(db_path):
            logger.info(f"删除旧的数据库文件: {db_path}")
            os.remove(db_path)
        
        db.create_all()
        
        if Server.query.count() == 0:
            logger.info("数据库已初始化，添加测试服务器")
            test_server = Server(
                name='测试服务器',
                host='127.0.0.1',
                port=22,
                username='root',
                description='测试用服务器，请修改配置'
            )
            db.session.add(test_server)
            db.session.commit()
            logger.info("已添加测试服务器")
    
    print('=' * 60)
    print('堡垒机后端启动成功')
    print('HTTP API: http://localhost:5001')
    print('WebSocket: ws://localhost:5002')
    print('=' * 60)
    
    # 启动 WebSocket 服务器线程
    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()
    
    # 启动 HTTP 服务器
    app.run(host='127.0.0.1', port=5001, debug=True, threaded=True, use_reloader=False)