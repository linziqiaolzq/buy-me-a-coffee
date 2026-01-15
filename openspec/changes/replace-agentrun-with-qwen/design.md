# Design: 将 AI 模型从 AgentRun 切换为直接调用 Qwen API

## Context

当前代码使用 `agentrun.integration.google_adk.model()` 来创建模型，这依赖于阿里云 AgentRun 平台。代码库原本基于 Google ADK，然后 AgentRun 通过 `agentrun.integration.google_adk.model()` 函数进行了适配，使得可以支持 AgentRun 平台。现在需要模仿 AgentRun 的方式，创建一个类似的适配层来直接支持 Qwen API。

## Goals

1. 支持直接使用 Qwen API，不依赖 AgentRun 平台
2. 保持向后兼容，如果设置了 AgentRun 环境变量仍可使用
3. 通过 `.env` 文件配置 Qwen API 密钥
4. 最小化代码改动，只修改模型配置部分

## Non-Goals

- 不支持其他 AI 模型（如 OpenAI、Claude 等）
- 不改变 Agent 架构和工具调用逻辑
- 不修改 A2A 协议相关代码

## Decisions

### Decision 1: 模型配置优先级

**选择**: 优先使用 Qwen 配置，如果未设置则回退到 AgentRun

**理由**: 
- 用户明确要求使用 Qwen
- 保持向后兼容，避免破坏现有部署

**实现**:
模仿 AgentRun 的模式，创建类似的函数：
```python
# 在 config.py 中
def qwen_model(api_key: str, model_name: str = "qwen-plus"):
    """Qwen 模型适配器，模仿 agentrun.integration.google_adk.model()"""
    import dashscope
    dashscope.api_key = api_key
    # 返回模型对象（需要确认返回类型，可能是字符串或适配器对象）
    return model_name  # 或适配器对象

# 模型配置优先级
QWEN_API_KEY = get_env_with_default("", "QWEN_API_KEY")
QWEN_MODEL = get_env_with_default("qwen-plus", "QWEN_MODEL")

if QWEN_API_KEY:
    # 使用 Qwen 模型（模仿 AgentRun 方式）
    DEFAULT_LLM = qwen_model(QWEN_API_KEY, QWEN_MODEL)
elif AGENTRUN_MODEL_NAME:
    # 使用 AgentRun（向后兼容）
    DEFAULT_LLM = model(AGENTRUN_MODEL_NAME, model=MODEL_NAME)
else:
    # 错误提示
    raise ValueError("需要设置 QWEN_API_KEY 或 AGENTRUN_MODEL_NAME")
```

### Decision 2: 模仿 AgentRun 的适配模式

**选择**: 模仿 `agentrun.integration.google_adk.model()` 的方式，创建一个类似的适配函数来支持 Qwen

**理由**: 
- AgentRun 通过 `model()` 函数适配了 Google ADK，返回一个模型对象
- 应该模仿相同的模式，创建一个 `qwen_model()` 函数
- 保持代码结构的一致性，便于理解和维护

**实现模式**:
参考 AgentRun 的实现：
```python
# AgentRun 方式（现有）
from agentrun.integration.google_adk import model, toolset
DEFAULT_LLM = model(AGENTRUN_MODEL_NAME, model=MODEL_NAME)
```

模仿创建 Qwen 适配：
```python
# Qwen 方式（新增）
def qwen_model(api_key: str, model_name: str = "qwen-plus"):
    """创建 Qwen 模型适配器，模仿 agentrun.integration.google_adk.model() 的模式"""
    import dashscope
    dashscope.api_key = api_key
    # 返回模型对象（需要确认 Google ADK 接受什么类型）
    # 可能是字符串，也可能是适配器对象
    return model_name  # 或返回适配器对象
```

**技术细节**:
- Qwen SDK 包名: `dashscope`
- API 密钥通过环境变量 `QWEN_API_KEY` 配置
- 模型名称通过环境变量 `QWEN_MODEL` 配置（默认值: `"qwen-plus"`）
- 需要确认 `agentrun.integration.google_adk.model()` 返回的对象类型
- 可能需要创建适配器类来兼容 Google ADK 的接口

### Decision 3: 环境变量命名

**选择**: 使用 `QWEN_API_KEY` 和 `QWEN_MODEL`

**理由**:
- 清晰明确，符合常见命名规范
- 与现有的 `GOOGLE_API_KEY` 和 `GOOGLE_MODEL` 命名风格一致

## Alternatives Considered

### Alternative 1: 完全移除 AgentRun 支持

**缺点**: 破坏向后兼容性，可能影响现有部署

**选择**: 不采用，保持向后兼容

### Alternative 2: 支持多种模型提供商

**缺点**: 增加复杂度，超出当前需求范围

**选择**: 不采用，只支持 Qwen

## Risks / Trade-offs

### Risk 1: Google ADK 可能不支持 Qwen

**状态**: **已确认不支持**

**缓解措施**: 
- 使用 Qwen SDK (`dashscope`) 直接调用
- Google ADK 的 `Agent` 类接受字符串类型的模型名称，可以直接传入 Qwen 模型名称

### Risk 2: Qwen API 调用方式可能与 Google AI 不同

**状态**: **已确认使用 dashscope SDK**

**缓解措施**:
- 使用官方 `dashscope` SDK
- 通过环境变量配置 API 密钥
- 模型名称直接使用字符串

### Risk 3: 向后兼容可能增加代码复杂度

**缓解措施**:
- 保持代码清晰，使用条件判断
- 添加注释说明

## Migration Plan

1. **阶段 1**: 调研和确认技术方案
   - 确认 Google ADK 支持方式
   - 确认 Qwen API 调用方式

2. **阶段 2**: 实现模型配置
   - 修改 `config.py`
   - 添加环境变量支持

3. **阶段 3**: 测试验证
   - 本地测试 Qwen 模型调用
   - 验证所有 Agent 正常工作

4. **阶段 4**: 文档更新
   - 更新环境变量说明
   - 添加 Qwen 配置指南

## Open Questions

~~1. Google ADK 是否原生支持 Qwen 模型？如果不支持，如何适配？~~ **已确认：不支持，使用 Qwen SDK，模仿 AgentRun 模式**

~~2. Qwen API 的调用方式是什么？是否需要特殊的 SDK？~~ **已确认：使用 `dashscope` SDK**

~~3. 是否需要修改 `requirements.txt` 添加 Qwen SDK 依赖？~~ **已确认：需要添加 `dashscope`**

4. `agentrun.integration.google_adk.model()` 返回什么类型的对象？**待实现时确认：优先尝试返回字符串，如果不工作再查看 AgentRun SDK**

5. Google ADK 的 `Agent` 类的 `model` 参数接受什么类型？**待实现时确认：从代码使用方式推断，可能是字符串或对象**

6. Qwen 模型的默认值应该是什么？（如 `qwen-plus`, `qwen-max`）**已确认：使用 `qwen-plus` 作为默认值**

## 实现策略

基于代码分析，所有 Agent 都使用 `model=DEFAULT_LLM`，而 `DEFAULT_LLM = model(AGENTRUN_MODEL_NAME, model=MODEL_NAME)`。

**优先方案**: 假设 `model()` 函数返回字符串或可被 Agent 接受的简单对象，直接返回 Qwen 模型名称字符串。

**备选方案**: 如果字符串不工作，需要查看 AgentRun SDK 源码，创建类似的适配器对象。

