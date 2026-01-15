# 技术验证清单

## 需要确认的关键信息

### 1. `agentrun.integration.google_adk.model()` 的返回类型

**当前状态**: 无法直接验证（需要安装 agentrun-sdk）

**需要确认**:
- [ ] 该函数返回什么类型的对象？
  - 可能是字符串（模型名称）
  - 可能是模型对象
  - 可能是适配器对象

**验证方法**:
```python
from agentrun.integration.google_adk import model
result = model('', '')
print(type(result))
print(result)
```

### 2. Google ADK `Agent` 类的 `model` 参数类型

**当前状态**: 无法直接验证（需要安装 google-adk）

**从代码分析**:
- 所有 Agent 都使用 `model=DEFAULT_LLM`
- DEFAULT_LLM 来自 `model(AGENTRUN_MODEL_NAME, model=MODEL_NAME)`
- 说明 Agent 的 model 参数接受 `agentrun.integration.google_adk.model()` 的返回值

**需要确认**:
- [ ] Agent 的 model 参数接受什么类型？
  - 字符串（如 `"gemini-2.0-flash"`, `"qwen-plus"`）
  - 模型对象
  - 适配器对象

**验证方法**:
```python
from google.adk import Agent
import inspect
sig = inspect.signature(Agent.__init__)
print(sig.parameters['model'])
```

### 3. Qwen 模型名称格式

**需要确认**:
- [ ] Qwen 模型名称的正确格式是什么？
  - `"qwen-plus"`?
  - `"qwen-max"`?
  - `"qwen-turbo"`?
  - 其他格式？

**参考**: publish.yaml 中提到 `qwen3-max`

### 4. dashscope SDK 的使用方式

**需要确认**:
- [ ] 如何配置 dashscope API key？
  - `dashscope.api_key = api_key`?
  - 其他方式？

- [ ] Google ADK 如何与 dashscope 集成？
  - 是否需要适配器？
  - 还是直接使用字符串模型名称？

## 实现策略（基于当前理解）

### 方案 A: 如果 model 参数接受字符串

```python
def qwen_model(api_key: str, model_name: str = "qwen-plus"):
    """Qwen 模型适配器"""
    import dashscope
    dashscope.api_key = api_key
    # 直接返回模型名称字符串
    return model_name
```

### 方案 B: 如果 model 参数需要对象

可能需要创建适配器类，但需要先确认 AgentRun 的实现方式。

## 下一步行动

1. **在实现阶段**，先尝试方案 A（返回字符串）
2. **如果方案 A 不工作**，查看 AgentRun SDK 源码或文档
3. **创建适配器**（如果需要）


