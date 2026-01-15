#!/bin/bash

# 分布式部署启动脚本
# 用于启动所有服务（咖啡 API、配送 API、咖啡 Agent、配送 Agent、网关）

set -e

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
PID_FILE="$PROJECT_ROOT/.distributed_pids"
LOG_DIR="$PROJECT_ROOT/logs"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查服务是否已经在运行
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

# 启动服务
start_service() {
    local name=$1
    local port=$2
    local command=$3
    local log_file="$LOG_DIR/${name}.log"
    
    if check_port $port; then
        echo -e "${YELLOW}⚠️  端口 $port 已被占用，跳过启动 $name${NC}"
        return 1
    fi
    
    echo -e "${BLUE}🚀 启动 $name (端口 $port)...${NC}"
    cd "$BACKEND_DIR"
    
    # 在后台启动服务，保存 PID
    nohup python -m $command > "$log_file" 2>&1 &
    local pid=$!
    echo $pid >> "$PID_FILE"
    
    # 等待服务启动（最多等待 30 秒，每 1 秒检查一次）
    local max_attempts=30
    local attempt=0
    local started=false
    
    while [ $attempt -lt $max_attempts ]; do
        sleep 1
        if check_port $port; then
            started=true
            break
        fi
        attempt=$((attempt + 1))
    done
    
    if [ "$started" = true ]; then
        echo -e "${GREEN}✅ $name 已启动 (PID: $pid, 端口: $port)${NC}"
        echo -e "   日志: $log_file"
        return 0
    else
        # 检查进程是否还在运行
        if kill -0 $pid 2>/dev/null; then
            echo -e "${YELLOW}⚠️  $name 进程运行中但端口 $port 未就绪，请检查日志: $log_file${NC}"
            echo -e "   PID: $pid"
        else
            echo -e "${RED}❌ $name 启动失败，请检查日志: $log_file${NC}"
        fi
        return 1
    fi
}

# 停止所有服务
stop_services() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}没有运行中的服务${NC}"
        return
    fi
    
    echo -e "${BLUE}🛑 停止所有服务...${NC}"
    
    while read pid; do
        if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
            echo -e "${YELLOW}   停止进程 $pid...${NC}"
            kill $pid 2>/dev/null || true
        fi
    done < "$PID_FILE"
    
    rm -f "$PID_FILE"
    echo -e "${GREEN}✅ 所有服务已停止${NC}"
}

# 显示服务状态
show_status() {
    echo -e "${BLUE}📊 服务状态:${NC}"
    echo ""
    
    local services=(
        "咖啡店 API:8001:coffee.main"
        "配送 API:8002:delivery.main"
        "咖啡 Agent:8003:coffee.a2a"
        "配送 Agent:8004:delivery.a2a"
        "网关:8000:gateway.main"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r name port module <<< "$service_info"
        if check_port $port; then
            echo -e "  ${GREEN}✅${NC} $name (端口 $port) - 运行中"
        else
            echo -e "  ${RED}❌${NC} $name (端口 $port) - 未运行"
        fi
    done
}

# 显示日志
show_logs() {
    local service=$1
    local log_file="$LOG_DIR/${service}.log"
    
    if [ ! -f "$log_file" ]; then
        echo -e "${RED}日志文件不存在: $log_file${NC}"
        return
    fi
    
    echo -e "${BLUE}📄 $service 日志 (最后 50 行):${NC}"
    echo ""
    tail -n 50 "$log_file"
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}  启动分布式部署服务${NC}"
            echo -e "${GREEN}========================================${NC}"
            echo ""
            
            # 清理旧的 PID 文件
            rm -f "$PID_FILE"
            
            # 检查环境变量
            if [ -z "$QWEN_API_KEY" ] && [ -z "$AGENTRUN_MODEL_NAME" ]; then
                echo -e "${YELLOW}⚠️  警告: 未设置 QWEN_API_KEY 或 AGENTRUN_MODEL_NAME${NC}"
                echo -e "${YELLOW}   请确保在 .env 文件中设置了这些变量${NC}"
                echo ""
            fi
            
            # 启动服务（按顺序）
            start_service "咖啡店 API" 8001 "coffee.main"
            start_service "配送 API" 8002 "delivery.main"
            start_service "咖啡 Agent" 8003 "coffee.a2a"
            start_service "配送 Agent" 8004 "delivery.a2a"
            
            # 等待 A2A 服务启动
            echo -e "${BLUE}⏳ 等待 A2A 服务启动...${NC}"
            sleep 3
            
            # 启动网关（需要设置环境变量）
            cd "$BACKEND_DIR"
            export DEPLOY_MODE=distributed
            export A2A_URLS="http://localhost:8003,http://localhost:8004"
            export COFFEE_API_URL="http://localhost:8001"
            export DELIVERY_API_URL="http://localhost:8002"
            
            start_service "网关" 8000 "gateway.main"
            
            echo ""
            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}  所有服务启动完成！${NC}"
            echo -e "${GREEN}========================================${NC}"
            echo ""
            echo -e "📝 查看日志: ${BLUE}tail -f logs/*.log${NC}"
            echo -e "📊 查看状态: ${BLUE}./scripts/start_distributed.sh status${NC}"
            echo -e "🛑 停止服务: ${BLUE}./scripts/start_distributed.sh stop${NC}"
            echo ""
            show_status
            ;;
        stop)
            stop_services
            ;;
        status)
            show_status
            ;;
        logs)
            if [ -z "$2" ]; then
                echo -e "${RED}请指定服务名称: coffee-api, delivery-api, coffee-agent, delivery-agent, gateway${NC}"
                exit 1
            fi
            show_logs "$2"
            ;;
        *)
            echo "用法: $0 {start|stop|status|logs [service]}"
            echo ""
            echo "命令:"
            echo "  start             启动所有服务"
            echo "  stop              停止所有服务"
            echo "  status            显示服务状态"
            echo "  logs <service>    查看指定服务的日志"
            echo ""
            echo "服务名称: coffee-api, delivery-api, coffee-agent, delivery-agent, gateway"
            exit 1
            ;;
    esac
}

main "$@"

