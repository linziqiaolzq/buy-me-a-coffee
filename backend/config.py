"""
配置文件

Buy A Coffee 多 Agent 系统配置

支持以下独立服务：
1. 咖啡店后端 API (COFFEE_API_PORT) - 提供咖啡店 REST API
2. 配送后端 API (DELIVERY_API_PORT) - 提供配送 REST API
3. 咖啡店 Agent A2A (COFFEE_A2A_PORT) - 咖啡店 A2A 服务
4. 配送 Agent A2A (DELIVERY_A2A_PORT) - 配送 A2A 服务
5. 主 Agent/网关 (GATEWAY_PORT) - 主入口，整合所有服务
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# 项目根目录（在加载环境变量之前确定）
BASE_DIR = Path(__file__).parent.parent

# 加载环境变量（从项目根目录查找 .env 文件）
# 尝试从项目根目录和 backend 目录加载
load_dotenv(dotenv_path=BASE_DIR / ".env")
load_dotenv(dotenv_path=BASE_DIR / "backend" / ".env")  # 也尝试 backend/.env


def get_env_with_default(default_value: str, *env_names: str) -> str:
    """按优先级获取环境变量值"""
    for name in env_names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default_value


# Qwen 模型适配器（模仿 AgentRun 模式）
def qwen_model(api_key: str, model_name: str = "qwen-plus"):
    """
    Qwen 模型适配器，模仿 agentrun.integration.google_adk.model() 的模式
    
    注册 Qwen LLM 适配器到 Google ADK 的 LLMRegistry，然后返回模型名称字符串
    
    Args:
        api_key: Qwen API 密钥
        model_name: Qwen 模型名称，默认 "qwen-plus"
    
    Returns:
        模型名称字符串（Google ADK Agent 接受字符串类型的 model 参数）
    """
    import dashscope
    from google.adk.models.registry import LLMRegistry
    from shared.qwen_llm import QwenLlm
    
    # 设置 dashscope API key
    dashscope.api_key = api_key
    
    # 注册 Qwen LLM 适配器到 Google ADK 的注册表
    # 注意：这里需要确保只注册一次，所以检查是否已注册
    try:
        LLMRegistry.register(QwenLlm)
    except Exception:
        # 如果已注册，忽略错误
        pass
    
    # 返回模型名称字符串，Google ADK 会通过 LLMRegistry 解析并找到 QwenLlm 类
    return model_name


# AgentRun 集成能力（向后兼容）
COFFEE_TOOLSET_NAME = get_env_with_default("", "COFFEE_TOOLSET_NAME")
DELIVERY_TOOLSET_NAME = get_env_with_default("", "DELIVERY_TOOLSET_NAME")
from agentrun.integration.google_adk import model, toolset

MODEL_NAME = get_env_with_default("", "MODEL_NAME")
AGENTRUN_MODEL_NAME = get_env_with_default("", "AGENTRUN_MODEL_NAME")

# Qwen 配置
QWEN_API_KEY = get_env_with_default("", "QWEN_API_KEY")
QWEN_MODEL = get_env_with_default("qwen-plus", "QWEN_MODEL")

# 模型配置优先级：优先使用 Qwen，否则使用 AgentRun（向后兼容）
if QWEN_API_KEY:
    # 使用 Qwen 模型（模仿 AgentRun 方式）
    DEFAULT_LLM = qwen_model(QWEN_API_KEY, QWEN_MODEL)
elif AGENTRUN_MODEL_NAME:
    # 使用 AgentRun（向后兼容）
    DEFAULT_LLM = model(AGENTRUN_MODEL_NAME, model=MODEL_NAME)
else:
    # 错误提示
    raise ValueError(
        "需要设置 QWEN_API_KEY 或 AGENTRUN_MODEL_NAME 环境变量。"
        "使用 Qwen: 设置 QWEN_API_KEY 和可选的 QWEN_MODEL（默认: qwen-plus）。"
        "使用 AgentRun: 设置 AGENTRUN_MODEL_NAME 和可选的 MODEL_NAME。"
    )

COFFEE_TOOLSET = toolset(COFFEE_TOOLSET_NAME) if COFFEE_TOOLSET_NAME else []
DEVELIVERY_TOOLSET = toolset(DELIVERY_TOOLSET_NAME) if DELIVERY_TOOLSET_NAME else []

# 项目根目录（已在上面定义）

# 数据库目录
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 数据库文件路径
COFFEE_DB_PATH = DATA_DIR / "coffee.db"
DELIVERY_DB_PATH = DATA_DIR / "delivery.db"


# 通用配置
API_HOST = get_env_with_default(
    "0.0.0.0",
    "API_HOST",
)

# 各服务端口配置
GATEWAY_PORT = int(
    get_env_with_default(
        "8000", "GATEWAY_PORT", "FC_SERVER_PORT", "FC_CUSTOM_LISTEN_PORT"
    )
)  # 主网关/Agent
COFFEE_API_PORT = int(
    get_env_with_default(
        "8001", "COFFEE_API_PORT", "FC_SERVER_PORT", "FC_CUSTOM_LISTEN_PORT"
    )
)  # 咖啡店后端 API
DELIVERY_API_PORT = int(
    get_env_with_default(
        "8002", "DELIVERY_API_PORT", "FC_SERVER_PORT", "FC_CUSTOM_LISTEN_PORT"
    )
)  # 配送后端 API
COFFEE_A2A_PORT = int(
    get_env_with_default(
        "8003", "COFFEE_A2A_PORT", "FC_SERVER_PORT", "FC_CUSTOM_LISTEN_PORT"
    )
)  # 咖啡店 Agent A2A
DELIVERY_A2A_PORT = int(
    get_env_with_default(
        "8004", "DELIVERY_A2A_PORT", "FC_SERVER_PORT", "FC_CUSTOM_LISTEN_PORT"
    )
)  # 配送 Agent A2A


A2A_URLS = get_env_with_default("", "A2A_URLS").split(",") or []

# 服务 URL 配置（用于服务间调用）
COFFEE_API_URL = os.getenv("COFFEE_API_URL", f"http://localhost:{COFFEE_API_PORT}")
DELIVERY_API_URL = os.getenv(
    "DELIVERY_API_URL", f"http://localhost:{DELIVERY_API_PORT}"
)

COFFEE_A2A_URL = os.getenv("COFFEE_A2A_URL", f"http://localhost:{COFFEE_A2A_PORT}")
DELIVERY_A2A_URL = os.getenv("DELIVERY_A2A_URL", f"http://localhost:{COFFEE_A2A_PORT}")
