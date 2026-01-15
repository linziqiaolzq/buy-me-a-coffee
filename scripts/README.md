# 分布式部署脚本

## 快速开始

### 启动所有服务

```bash
./scripts/start_distributed.sh start
```

或者：

```bash
bash scripts/start_distributed.sh start
```

### 停止所有服务

```bash
./scripts/start_distributed.sh stop
```

### 查看服务状态

```bash
./scripts/start_distributed.sh status
```

### 查看日志

```bash
# 查看所有服务的日志
tail -f logs/*.log

# 查看特定服务的日志
./scripts/start_distributed.sh logs gateway
./scripts/start_distributed.sh logs coffee-api
```

## 服务列表

| 服务 | 端口 | 模块 |
|------|------|------|
| 咖啡店 API | 8001 | coffee.main |
| 配送 API | 8002 | delivery.main |
| 咖啡 Agent | 8003 | coffee.a2a |
| 配送 Agent | 8004 | delivery.a2a |
| 网关 | 8000 | gateway.main |

## 日志文件

所有服务的日志保存在 `logs/` 目录：

- `logs/coffee-api.log` - 咖啡店 API 日志
- `logs/delivery-api.log` - 配送 API 日志
- `logs/coffee-agent.log` - 咖啡 Agent 日志
- `logs/delivery-agent.log` - 配送 Agent 日志
- `logs/gateway.log` - 网关日志

## 注意事项

1. **环境变量**：确保在项目根目录或 `backend/` 目录有 `.env` 文件，包含 `QWEN_API_KEY`
2. **端口占用**：如果端口被占用，脚本会跳过启动该服务
3. **启动顺序**：脚本会按正确顺序启动服务（API → Agent → 网关）
4. **PID 文件**：服务 PID 保存在 `.distributed_pids` 文件中，用于停止服务

## 故障排查

### 服务启动失败

1. 检查日志文件：`logs/<service>.log`
2. 检查端口是否被占用：`lsof -i :8000`
3. 检查环境变量是否正确设置

### 无法停止服务

```bash
# 手动停止
pkill -f "python -m coffee.main"
pkill -f "python -m delivery.main"
pkill -f "python -m coffee.a2a"
pkill -f "python -m delivery.a2a"
pkill -f "python -m gateway.main"
```

