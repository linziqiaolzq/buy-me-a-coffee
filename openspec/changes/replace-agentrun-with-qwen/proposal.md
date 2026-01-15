# Change: 将 AI 模型从 AgentRun 切换为直接调用 Qwen API

## Why

当前代码使用 `agentrun.integration.google_adk.model()` 来创建模型，这依赖于 AgentRun 平台。用户希望改为直接调用 Qwen（通义千问）API，以便在本地环境独立运行，不依赖 AgentRun 平台。

## What Changes

- **MODIFIED**: `backend/config.py` 中的 `DEFAULT_LLM` 创建方式
  - 模仿 `agentrun.integration.google_adk.model()` 的模式
  - 创建 `qwen_model()` 适配函数来支持 Qwen
  - 添加 `QWEN_API_KEY` 环境变量支持
  - 添加 `QWEN_MODEL` 环境变量支持（可选，默认值: `"qwen-plus"`）
  - 保持 AgentRun 相关导入和逻辑（向后兼容）

- **ADDED**: 环境变量配置
  - `QWEN_API_KEY`: Qwen API 密钥（必需）
  - `QWEN_MODEL`: Qwen 模型名称（可选，如 `qwen-plus`, `qwen-max` 等）

- **MODIFIED**: 文档更新
  - 更新 `AGENTS.md` 中的环境变量说明
  - 移除 AgentRun 相关的模型配置说明

## Impact

- **Affected specs**: `model-config` (新增)
- **Affected code**:
  - `backend/config.py` - 核心模型配置逻辑
  - `backend/gateway/agent.py` - 使用 DEFAULT_LLM
  - `backend/assistant/agent.py` - 使用 DEFAULT_LLM
  - `backend/coffee/agent.py` - 使用 DEFAULT_LLM
  - `backend/delivery/agent.py` - 使用 DEFAULT_LLM
  - `AGENTS.md` - 文档更新

- **Breaking changes**: 无（向后兼容，如果设置了 AgentRun 环境变量仍可使用）

- **Dependencies**: 
  - 需要添加 `dashscope` Python SDK（Qwen 官方 SDK）
  - Google ADK 不支持 Qwen，直接使用字符串形式的模型名称
  - 通过 `dashscope.api_key` 配置 API 密钥

