# Jump Server (Bastion Host) - 堡垒机/跳板机系统

一个基于 Python Flask 和 WebSocket 实现的轻量级堡垒机系统，提供 SSH 会话管理和 Web 终端访问能力。

## 功能特性

- 🔐 **用户认证** - 简单的用户名认证机制
- 🖥️ **服务器管理** - 支持添加、编辑、删除目标服务器
- 🔌 **SSH 连接** - 通过 SSH 协议连接到远程服务器
- 🌐 **Web 终端** - 基于 WebSocket 的实时终端访问
- 📊 **会话审计** - 记录用户会话和操作历史
- 🔑 **多认证方式** - 支持密码认证和密钥认证（预留接口）

## 技术栈

- **后端框架**: Flask + Flask-SQLAlchemy
- **实时通信**: WebSocket (websockets)
- **SSH 连接**: Paramiko
- **数据库**: SQLite
- **跨域支持**: Flask-CORS

## 系统架构

```
┌─────────────────┐     HTTP API      ┌─────────────┐
│   Web 前端       │ ◄──────────────► │  Flask App  │
│  (smn 项目)      │                    │  (Port 5001) │
│                 │                    └──────┬──────┘
│                 │                           │
│                 │     WebSocket             │
│                 │ ◄────────────────────────► │
└─────────────────┘                    ┌──────▼──────┐
                                       │  WebSocket  │
                                       │  (Port 5002) │
                                       └──────┬──────┘
                                              │ SSH
                                        ┌─────▼─────┐
                                        │  Target   │
                                        │  Servers  │
                                        └───────────┘
```

> 📌 **前端说明**：本项目的 Web 终端界面由 [SMN 项目](https://github.com/gopsc/smn) 托管提供。SMN 是一个功能完善的 Web 文件管理工具，支持用户认证、文件操作和代理功能，与本跳板机后端配合使用可提供完整的堡垒机解决方案。

## 快速开始

### 环境要求

- Python 3.8+
- pip
- Git（用于克隆前端项目）

### 一键安装环境

使用提供的 `_set.sh` 脚本自动安装所有依赖：

```bash
chmod +x _set.sh
./_set.sh
```

该脚本会自动完成：
- 检查 Python 环境
- 安装 Python 依赖包（flask, flask-cors, flask-sqlalchemy, paramiko, websockets）
- 创建必要的目录结构
- 初始化数据库

### 运行服务

使用 `_run.sh` 脚本启动服务：

```bash
chmod +x _run.sh
./_run.sh
```

服务启动后会显示：

```
============================================================
堡垒机后端启动成功
HTTP API: http://localhost:5001
WebSocket: ws://localhost:5002
============================================================
```

### 手动安装（备选）

如果自动脚本失败，可以手动执行：

```bash
# 安装依赖
pip install flask flask-cors flask-sqlalchemy paramiko websockets

# 启动服务
python jump_server.py
```

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SECRET_KEY` | Flask 会话密钥 | `bastion-secret-key-change-in-production` |

### 端口配置

| 服务 | 端口 | 说明 |
|------|------|------|
| HTTP API | 5001 | RESTful API 服务 |
| WebSocket | 5002 | WebSocket 终端服务 |

## API 接口文档

### 认证相关

#### 用户登录

```http
POST /api/auth/login
Content-Type: application/json

{
    "username": "admin"
}
```

**响应**：
```json
{
    "message": "登录成功",
    "user": {
        "username": "admin",
        "is_admin": true
    }
}
```

#### 用户登出

```http
POST /api/auth/logout
```

#### 获取当前用户

```http
GET /api/auth/me
```

### 服务器管理

#### 获取服务器列表

```http
GET /api/servers
```

#### 添加服务器

```http
POST /api/servers
Content-Type: application/json

{
    "name": "生产服务器",
    "host": "192.168.1.100",
    "port": 22,
    "username": "root",
    "password": "your_password",
    "description": "生产环境主服务器"
}
```

#### 获取服务器详情

```http
GET /api/servers/{server_id}
```

#### 更新服务器

```http
PUT /api/servers/{server_id}
Content-Type: application/json

{
    "name": "新名称",
    "host": "新IP"
}
```

#### 删除服务器

```http
DELETE /api/servers/{server_id}
```

### 会话管理

#### 获取会话列表

```http
GET /api/sessions
```

#### 获取会话详情

```http
GET /api/sessions/{session_id}
```

## WebSocket 协议

### 连接地址

```
ws://localhost:5002
```

### 消息格式

所有消息均为 JSON 格式。

#### 1. 连接服务器

```json
{
    "type": "connect_server",
    "server_id": 1,
    "username": "admin",
    "cols": 120,
    "rows": 40
}
```

#### 2. 执行命令

```json
{
    "type": "command",
    "session_id": "uuid-string",
    "command": "ls -la\n"
}
```

#### 3. 调整终端大小

```json
{
    "type": "resize",
    "session_id": "uuid-string",
    "cols": 120,
    "rows": 40
}
```

#### 4. 断开连接

```json
{
    "type": "disconnect_server",
    "session_id": "uuid-string"
}
```

### 服务端消息

#### 输出数据

```json
{
    "type": "output",
    "session_id": "uuid-string",
    "data": "command output here..."
}
```

#### 连接成功

```json
{
    "type": "connected",
    "session_id": "uuid-string",
    "message": "连接成功"
}
```

#### 错误消息

```json
{
    "type": "error",
    "message": "错误描述"
}
```

## 数据库模型

### servers 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| name | String(100) | 服务器名称 |
| host | String(255) | 主机地址 |
| port | Integer | SSH 端口 |
| username | String(80) | 登录用户名 |
| password | String(255) | 登录密码（加密存储） |
| ssh_key | Text | SSH 密钥（预留） |
| description | Text | 描述信息 |
| created_at | DateTime | 创建时间 |

### session_logs 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(80) | 用户名 |
| server_id | Integer | 关联服务器 ID |
| session_id | String(100) | 会话唯一标识 |
| start_time | DateTime | 会话开始时间 |
| end_time | DateTime | 会话结束时间 |
| commands | Text | 命令记录（JSON 格式） |
| ip_address | String(45) | 客户端 IP |

## 安全注意事项

> ⚠️ **生产环境部署前请注意：**

1. **修改默认密钥**：务必设置环境变量 `SECRET_KEY` 为强密码
2. **密码存储**：当前密码以明文存储，生产环境应使用加密存储
3. **CORS 配置**：当前允许所有来源，生产环境应限制具体域名
4. **认证机制**：当前为简化认证，生产环境建议集成 OAuth/LDAP
5. **会话审计**：建议启用更详细的命令审计功能
6. **网络隔离**：WebSocket 和 HTTP 服务应配置防火墙规则

## 目录结构

```
.
├── jump_server.py          # 主程序文件
├── _set.sh                 # 环境安装脚本
├── _run.sh                 # 服务启动脚本
├── bastion.db              # SQLite 数据库（运行时生成）
└── README.md               # 项目文档
```

## 脚本说明

### `_set.sh` - 环境安装脚本

自动完成以下任务：
- 检查 Python 3.8+ 环境
- 升级 pip 到最新版本
- 安装所有必需的 Python 包
- 验证安装是否成功

### `_run.sh` - 服务启动脚本

- 检查依赖是否已安装
- 启动 HTTP API 服务（端口 5001）
- 启动 WebSocket 服务（端口 5002）
- 显示服务状态信息

## 与 SMN 前端集成

本跳板机后端需要配合 [SMN 项目](https://github.com/gopsc/smn) 的前端界面使用。SMN 提供了完整的 Web 终端界面和用户管理功能。

### 集成步骤

1. **克隆 SMN 项目**
   ```bash
   git clone https://github.com/gopsc/smn.git
   cd smn
   ```

2. **配置 SMN 代理**
   
   编辑 SMN 项目的 `config.ini` 文件，添加跳板机 API 的代理配置：
   ```ini
   [proxy]
   enabled = true
   allowed_targets = http://localhost:5001,ws://localhost:5002
   ```

3. **启动 SMN 前端**
   ```bash
   ./_run.sh  # SMN 项目的前端启动脚本
   ```

4. **启动跳板机后端**
   ```bash
   cd /path/to/jump-server
   ./_run.sh
   ```

5. **访问 Web 终端**
   
   打开浏览器访问 SMN 前端地址（默认 `http://localhost:5000`），通过代理功能连接到跳板机后端。

## 开发计划

- [ ] 支持 SSH 密钥认证
- [ ] 增加用户角色和权限管理
- [ ] 实现命令黑白名单过滤
- [ ] 添加会话录像功能
- [ ] 支持 RDP 协议
- [ ] 集成 LDAP/OAuth 认证
- [ ] 完善 Web 管理界面
- [ ] 支持多租户隔离

## 常见问题

### 1. WebSocket 连接失败？

检查防火墙是否开放 5002 端口，确认 WebSocket 服务正常启动。

### 2. SSH 连接超时？

- 确认目标服务器 SSH 服务正常运行
- 检查网络连通性
- 验证用户名和密码是否正确

### 3. 数据库锁定错误？

SQLite 并发写入能力有限，生产环境建议迁移到 PostgreSQL 或 MySQL。

### 4. `_set.sh` 脚本执行失败？

- 确认 Python 版本 >= 3.8
- 检查是否有管理员权限（某些系统需要 sudo）
- 手动执行 `pip install flask flask-cors flask-sqlalchemy paramiko websockets`

### 5. 如何修改默认端口？

编辑 `jump_server.py` 文件，找到 `app.run(host='127.0.0.1', port=5001, ...)` 和 `serve(handle_websocket, "0.0.0.0", 5002)` 修改端口号。

## 贡献指南

欢迎提交 Issue 和 Pull Request。

## 许可证

MIT License

## 相关项目

- [SMN](https://github.com/gopsc/smn) - 前端 Web 管理界面和代理服务

## 联系方式

如有问题，请提交 Issue 或联系项目维护者。
