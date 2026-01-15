## 1. 添加依赖

- [x] 1.1 在 `backend/requirements.txt` 中添加 `dashscope` SDK 依赖
  - 添加: `dashscope>=1.0.0`

## 2. 实现模型配置（模仿 AgentRun 模式）

- [x] 2.1 创建 Qwen LLM 适配器类
  - 在 `backend/shared/qwen_llm.py` 中创建 `QwenLlm` 类，继承 `BaseLlm`
  - 实现 `supported_models()` 方法，返回匹配 qwen-* 的正则表达式
  - 实现 `generate_content_async()` 方法，使用 dashscope SDK 调用 Qwen API
  - 实现 `connect()` 方法
- [x] 2.2 创建 `qwen_model()` 适配函数（模仿 AgentRun 模式）
  - 在 `backend/config.py` 中创建 `qwen_model(api_key, model_name)` 函数
  - 函数签名模仿 `agentrun.integration.google_adk.model(agentrun_model_name, model=model_name)`
  - 配置 `dashscope.api_key = api_key`
  - 注册 `QwenLlm` 类到 `LLMRegistry`
  - 返回模型名称字符串（如 `"qwen-plus"`），Google ADK 会通过 LLMRegistry 解析
- [x] 2.3 修改 `backend/config.py`，添加 Qwen 相关环境变量读取
  - 添加 `QWEN_API_KEY` 环境变量读取
  - 添加 `QWEN_MODEL` 环境变量读取（默认值: `"qwen-plus"`）
- [x] 2.4 实现模型配置优先级逻辑
  - 如果设置了 `QWEN_API_KEY`，使用 `qwen_model()` 创建模型
  - 如果设置了 `AGENTRUN_MODEL_NAME`，保持原有 AgentRun 逻辑（向后兼容）
  - 优先使用 Qwen 配置
- [x] 2.5 保持 AgentRun 相关导入（用于向后兼容）

## 3. 测试和验证

- [x] 3.1 创建 `.env.example` 文件，添加 Qwen 配置示例（已创建，但被 .gitignore 忽略）
- [ ] 3.2 在本地环境测试 Qwen 模型调用（需要用户提供 QWEN_API_KEY 后测试）
- [ ] 3.3 验证所有 Agent（root_agent, assistant_agent, coffee_agent, delivery_agent）都能正常工作（需要测试）
- [ ] 3.4 测试流式和非流式聊天接口（需要测试）

## 4. 文档更新

- [x] 4.1 更新 `AGENTS.md` 中的环境变量说明
- [ ] 4.2 更新 `README.md`（如果需要）- README.md 主要面向 AgentRun 部署，暂不更新
- [x] 4.3 添加 Qwen API 密钥获取说明（已在 .env.example 中添加注释）

