# 堡垒机后端 API 手册
本文档描述了堡垒机后端提供的所有 REST API 接口和 WebSocket 事件。
## 基础信息
+ **基础地址**: `http://<host>:5001`
+ **认证方式**: 基于 Flask-Login 的会话认证（Cookie），登录后后续请求自动携带会话标识。
+ **权限说明**:
  + `@login_required`: 需要用户已登录。
  + `@admin_required`: 需要当前用户为管理员。
---
# 1. 认证接口
## 1.1 用户注册
+ **URL**: `/api/auth/register`
+ **方法**: `POST`
+ **权限**: 公开
+ **请求体** (JSON):
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
+ **成功响应** (200):
  ```json
  {
    "message": "注册成功"
  }
  ```
+ **错误响应** (400): 用户名已存在等。
## 1.2 用户登录
+ **URL**: `/api/auth/login`
+ **方法**: `POST`
+ **权限**: 公开
+ **请求体** (JSON):
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
+ **成功响应** (200):
  ```json
  {
    "message": "登录成功",
    "user": {
      "id": 1,
      "username": "admin",
      "is_admin": true
    }
  }
  ```
+ **错误响应** (401): 用户名或密码错误。
## 1.3 用户登出
+ **URL**: `/api/auth/logout`
+ **方法**: `POST`
+ **权限**: `@login_required`
+ **成功响应** (200):
  ```json
  {
    "message": "登出成功"
  }
  ```
## 1.4 获取当前用户信息
+ **URL**: `/api/auth/me`
+ **方法**: `GET`
+ **权限**: `@login_required`
+ **成功响应** (200):
  ```json
  {
    "id": 1,
    "username": "admin",
    "is_admin": true
  }
  ```
---
# 2. 服务器管理
## 2.1 获取服务器列表
+ **URL**: `/api/servers`
+ **方法**: `GET`
+ **权限**: `@login_required`
+ **说明**:
  + 管理员返回所有服务器。
  + 普通用户返回被授予权限的服务器。
+ **成功响应** (200):
  ```json
  [
    {
      "id": 1,
      "name": "测试服务器",
      "host": "192.168.1.100",
      "port": 22,
      "username": "root",
      "description": "用于测试"
    }
  ]
  ```
## 2.2 创建服务器
+ **URL**: `/api/servers`
+ **方法**: `POST`
+ **权限**: `@admin_required`
+ **请求体** (JSON):
  ```json
  {
    "name": "string",          // 必填
    "host": "string",          // 必填
    "port": 22,                // 可选，默认22
    "username": "string",      // 必填
    "password": "string",      // 可选，密码和密钥二选一
    "ssh_key": "string",       // 可选
    "description": "string"    // 可选
  }
  ```
+ **成功响应** (200):
  ```json
  {
    "message": "服务器创建成功",
    "id": 1
  }
  ```
## 2.3 获取单个服务器详情
+ **URL**: `/api/servers/<int:server_id>`
+ **方法**: `GET`
+ **权限**: `@admin_required`
+ **成功响应** (200):
  ```json
  {
    "id": 1,
    "name": "测试服务器",
    "host": "192.168.1.100",
    "port": 22,
    "username": "root",
    "description": "用于测试"
  }
  ```
  *注意：密码和密钥不返回。*
## 2.4 更新服务器信息
+ **URL**: `/api/servers/<int:server_id>`
+ **方法**: `PUT`
+ **权限**: `@admin_required`
+ **请求体** (JSON，字段均为可选):
  ```json
  {
    "name": "新名称",
    "host": "新主机",
    "port": 2222,
    "username": "新用户",
    "password": "新密码",   // 只有提供时才更新
    "ssh_key": "新密钥",    // 只有提供时才更新
    "description": "新描述"
  }
  ```
+ **成功响应** (200):
  ```json
  {
    "message": "服务器更新成功"
  }
  ```
## 2.5 删除服务器
+ **URL**: `/api/servers/<int:server_id>`
+ **方法**: `DELETE`
+ **权限**: `@admin_required`
+ **说明**: 删除服务器会同时删除相关的权限、会话记录，并关闭所有活动 SSH 连接。
+ **成功响应** (200):
  ```json
  {
    "message": "服务器删除成功"
  }
  ```
---
# 3. 权限管理
## 3.1 获取所有用户列表
+ **URL**: `/api/users`
+ **方法**: `GET`
+ **权限**: `@admin_required`
+ **成功响应** (200):
  ```json
  [
    {
      "id": 1,
      "username": "admin",
      "is_admin": true,
      "created_at": "2024-01-01T00:00:00+00:00"
    }
  ]
  ```
## 3.2 获取指定服务器的权限列表
+ **URL**: `/api/servers/<int:server_id>/permissions`
+ **方法**: `GET`
+ **权限**: `@admin_required`
+ **成功响应** (200):
  ```json
  [
    {
      "id": 1,
      "user_id": 2,
      "username": "zhangsan",
      "created_at": "2024-01-01T00:00:00+00:00"
    }
  ]
  ```
## 3.3 授予用户服务器访问权限
+ **URL**: `/api/servers/<int:server_id>/permissions`
+ **方法**: `POST`
+ **权限**: `@admin_required`
+ **请求体** (JSON):
  ```json
  {
    "user_id": 2
  }
  ```
+ **成功响应** (200):
  ```json
  {
    "message": "权限授予成功"
  }
  ```
  如果权限已存在，返回 `{"message": "用户已有此服务器权限"}`。
## 3.4 撤销用户服务器访问权限
+ **URL**: `/api/servers/<int:server_id>/permissions/<int:user_id>`
+ **方法**: `DELETE`
+ **权限**: `@admin_required`
+ **成功响应** (200):
  ```json
  {
    "message": "权限撤销成功"
  }
  ```
---
# 4. 会话管理
## 4.1 获取会话记录列表
+ **URL**: `/api/sessions`
+ **方法**: `GET`
+ **权限**: `@login_required`
+ **说明**:
  + 管理员查看所有会话。
  + 普通用户仅查看自己的会话。
+ **成功响应** (200):
  ```json
  [
    {
      "id": 1,
      "username": "admin",
      "server_name": "测试服务器",
      "start_time": "2024-01-01T00:00:00+00:00",
      "end_time": "2024-01-01T01:00:00+00:00",
      "session_id": "uuid-string"
    }
  ]
  ```
## 4.2 获取单个会话详情
+ **URL**: `/api/sessions/<session_id>`
+ **方法**: `GET`
+ **权限**: `@login_required`（仅限本人或管理员）
+ **成功响应** (200):
  ```json
  {
    "id": 1,
    "user": "admin",
    "server": "测试服务器",
    "start_time": "2024-01-01T00:00:00+00:00",
    "end_time": "2024-01-01T01:00:00+00:00",
    "commands": [
      {
        "command": "ls -la",
        "output": "",
        "timestamp": "2024-01-01T00:01:00+00:00"
      }
    ]
  }
  ```
---
# 5. 健康检查
## 5.1 服务健康状态
+ **URL**: `/api/health`
+ **方法**: `GET`
+ **权限**: 公开
+ **成功响应** (200):
  ```json
  {
    "status": "healthy",
    "timestamp": "2024-01-01T00:00:00+00:00"
  }
  ```
---
# 6. WebSocket 事件 (Socket.IO)
WebSocket 连接地址: `ws://<host>:5001` (或使用 Socket.IO 客户端库连接)
## 6.1 连接事件
+ `connect`: 客户端连接时自动触发，无需手动发送。
+ `disconnect`: 客户端断开时自动触发。
## 6.2 客户端发送事件
`connect_server`
+ **说明**: 请求连接到指定服务器。
+ **数据格式**:
  ```json
  {
    "server_id": 1,
    "user_id": 1,        // 当前登录用户ID
    "cols": 80,          // 终端宽度，可选
    "rows": 24           // 终端高度，可选
  }
  ```
+ **服务端响应**:
  + 成功: `connected` 事件
    ```json
    {
      "session_id": "uuid-string",
      "message": "连接成功"
    }
    ```
  + 失败: `error` 事件
    ```json
    {
      "message": "连接失败: 错误信息"
    }
    ```
`command`
+ **说明**: 在已连接的会话中执行命令。
+ **数据格式**:
  ```json
  {
    "session_id": "uuid-string",
    "command": "ls -la\n"   // 命令需包含换行符
  }
  ```
+ **服务端响应**: 无直接响应，命令输出将通过 `output` 事件返回。
`resize`
+ **说明**: 调整终端窗口大小。
+ **数据格式**:
  ```json
  {
    "session_id": "uuid-string",
    "width": 120,
    "height": 40
  }
  ```
`disconnect_server`
+ **说明**: 主动断开指定会话。
+ **数据格式**:
  ```json
  {
    "session_id": "uuid-string"
  }
  ```
+ **服务端响应**: `disconnected` 事件
  ```json
  {
    "message": "连接已断开"
  }
  ```
## 6.3 服务端发送事件
`output`
+ **说明**: 向客户端发送命令执行输出（实时流式）。
+ **数据格式**:
  ```json
  {
    "session_id": "uuid-string",
    "data": "命令输出内容"
  }
  ```
`error`
+ **说明**: 向客户端发送错误信息。
+ **数据格式**:
  ```json
  {
    "message": "错误描述"
  }
  ```
`connected`
+ **说明**: 连接服务器成功后的确认事件。
+ **数据格式**: 见 connect_server 响应。
`disconnected`
+ **说明**: 服务器会话已断开。
+ **数据格式**:
  ```json
  {
    "message": "连接已断开"
  }
  ```
---
# 附录
+ **默认管理员**: 首次启动会自动创建管理员 `admin` / `admin123`，请及时修改密码。
