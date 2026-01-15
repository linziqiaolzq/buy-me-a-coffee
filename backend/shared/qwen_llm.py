"""
Qwen LLM 适配器，用于 Google ADK

实现 BaseLlm 接口，内部使用 dashscope SDK 调用 Qwen API
支持工具调用（Function Calling）
"""

from typing import AsyncGenerator, Any, ClassVar, Dict, List, Optional
import inspect
import json
import logging
from google.adk.models import BaseLlm
from google.adk.models.base_llm import BaseLlmConnection
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
import dashscope

# 设置日志
# 配置 logger，确保日志能够输出
logger = logging.getLogger(__name__)
# 如果根 logger 没有 handler，配置 basicConfig
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
# 确保 logger 的级别至少是 INFO
if logger.level == logging.NOTSET:
    logger.setLevel(logging.INFO)


class QwenLlm(BaseLlm):
    """Qwen 模型适配器，实现 Google ADK BaseLlm 接口"""

    # Google ADK 内部工具黑名单（不应传递给 Qwen API）
    # 注意：transfer_to_agent 不在黑名单中，因为它是 root_agent 路由到子 agent 的必需工具
    INTERNAL_TOOLS: ClassVar[set[str]] = {"append_tools", "remove_tools", "update_tools"}

    @classmethod
    def supported_models(cls) -> list[str]:
        """返回支持 Qwen 模型名称的正则表达式"""
        return [
            r"^qwen-plus$",
            r"^qwen-max$",
            r"^qwen-turbo$",
            r"^qwen-.*",  # 匹配所有 qwen- 开头的模型
        ]

    def _try_get_tools_from_other_sources(self, llm_request: LlmRequest) -> Optional[List[Any]]:
        """
        尝试从其他来源获取工具定义（备用机制）
        
        Args:
            llm_request: Google ADK 的 LlmRequest 对象
            
        Returns:
            工具列表，如果没有找到则返回 None
        """
        logger.info("  🔍 方法1: 检查 QwenLlm 实例属性")
        # 检查 self 是否有工具定义相关的属性
        instance_attrs = [attr for attr in dir(self) if not attr.startswith('_') and ('tool' in attr.lower() or 'function' in attr.lower())]
        if instance_attrs:
            logger.info(f"    - 找到相关属性: {instance_attrs}")
            for attr in instance_attrs:
                try:
                    value = getattr(self, attr, None)
                    if value and isinstance(value, (list, tuple)) and len(value) > 0:
                        # 检查是否是工具列表
                        if callable(value[0]) or hasattr(value[0], "__name__"):
                            logger.info(f"    ✅ 从 {attr} 获取到工具列表: {len(value)} 个")
                            return list(value)
                except Exception as e:
                    logger.debug(f"    - 检查 {attr} 时出错: {e}")
        else:
            logger.info("    - 未找到相关属性")
        
        logger.info("  🔍 方法2: 检查 BaseLlmConnection")
        # 检查是否有连接对象
        if hasattr(self, '_connection'):
            conn = self._connection
            logger.info(f"    - 找到连接对象: {type(conn)}")
            conn_attrs = [attr for attr in dir(conn) if not attr.startswith('_') and ('tool' in attr.lower() or 'function' in attr.lower())]
            if conn_attrs:
                logger.info(f"    - 连接对象相关属性: {conn_attrs}")
                for attr in conn_attrs:
                    try:
                        value = getattr(conn, attr, None)
                        if value and isinstance(value, (list, tuple)) and len(value) > 0:
                            if callable(value[0]) or hasattr(value[0], "__name__"):
                                logger.info(f"    ✅ 从连接对象.{attr} 获取到工具列表: {len(value)} 个")
                                return list(value)
                    except Exception as e:
                        logger.debug(f"    - 检查连接对象.{attr} 时出错: {e}")
        else:
            logger.info("    - 未找到连接对象")
        
        logger.info("  🔍 方法3: 检查 LlmRequest 的所有属性（深度搜索）")
        # 深度搜索 LlmRequest 的所有属性
        all_attrs = [attr for attr in dir(llm_request) if not attr.startswith('__')]
        for attr in all_attrs:
            try:
                value = getattr(llm_request, attr, None)
                # 跳过方法
                if callable(value) and hasattr(value, "__self__"):
                    continue
                # 检查是否是工具列表
                if isinstance(value, (list, tuple)) and len(value) > 0:
                    first_item = value[0]
                    # 检查是否是函数或函数声明
                    if callable(first_item) or (hasattr(first_item, "__name__") and not isinstance(first_item, type)):
                        # 检查是否是用户工具
                        if self._is_user_tool(first_item):
                            logger.info(f"    ✅ 从 llm_request.{attr} 获取到工具列表: {len(value)} 个")
                            return list(value)
            except Exception as e:
                logger.debug(f"    - 检查 {attr} 时出错: {e}")
        
        logger.info("  🔍 方法4: 检查 tool_config 的所有属性（深度搜索）")
        if hasattr(llm_request, "tool_config") and llm_request.tool_config:
            tool_config = llm_request.tool_config
            tool_config_attrs = [attr for attr in dir(tool_config) if not attr.startswith('__')]
            for attr in tool_config_attrs:
                try:
                    value = getattr(tool_config, attr, None)
                    # 跳过方法
                    if callable(value) and hasattr(value, "__self__"):
                        continue
                    # 检查是否是工具列表
                    if isinstance(value, (list, tuple)) and len(value) > 0:
                        first_item = value[0]
                        if callable(first_item) or (hasattr(first_item, "__name__") and not isinstance(first_item, type)):
                            if self._is_user_tool(first_item):
                                logger.info(f"    ✅ 从 tool_config.{attr} 获取到工具列表: {len(value)} 个")
                                return list(value)
                except Exception as e:
                    logger.debug(f"    - 检查 tool_config.{attr} 时出错: {e}")
        
        return None

    def _is_user_tool(self, tool: Any) -> bool:
        """
        检查是否是用户定义的 Agent 工具
        
        Args:
            tool: 工具对象（可能是函数或函数声明对象）
            
        Returns:
            True 如果是用户定义的工具，False 如果是内部工具
        """
        try:
            # 获取函数名和模块
            func_name = None
            func_module = None
            func = tool
            
            if callable(tool):
                func_name = getattr(tool, "__name__", None)
                func_module = getattr(tool, "__module__", None)
                func = tool
            elif hasattr(tool, "name"):
                func_name = tool.name
            elif hasattr(tool, "__name__"):
                func_name = tool.__name__
            elif hasattr(tool, "function"):
                func = tool.function
                if callable(func):
                    func_name = getattr(func, "__name__", None)
                    func_module = getattr(func, "__module__", None)
                elif hasattr(func, "name"):
                    func_name = func.name
                    func_module = getattr(func, "__module__", None)
            
            if not func_name:
                logger.debug(f"   无法获取函数名，过滤: {type(tool)}")
                return False
            
            # 检查是否是内部工具（黑名单）
            if func_name in self.INTERNAL_TOOLS:
                logger.debug(f"   过滤内部工具（黑名单）: {func_name}")
                return False
            
            # 特殊处理：允许 transfer_to_agent 通过（它是 root_agent 路由到子 agent 的必需工具）
            if func_name == "transfer_to_agent":
                logger.debug(f"   保留路由工具: {func_name} (root_agent 需要它来路由到子 agent)")
                return True
            
            # 检查工具函数的模块路径
            if func_module:
                # 排除 Google ADK 内部模块（但允许 transfer_to_agent）
                if "google.adk" in func_module or "agentrun" in func_module:
                    # transfer_to_agent 已经在上面处理了，这里只处理其他内部工具
                    if func_name != "transfer_to_agent":
                        logger.debug(f"   过滤 Google ADK/AgentRun 内部工具: {func_name} (模块: {func_module})")
                        return False
                # 保留项目内的工具模块
                if any(prefix in func_module for prefix in ["coffee", "delivery", "assistant"]):
                    logger.debug(f"   保留用户工具（模块匹配）: {func_name} (模块: {func_module})")
                    return True
            
            # 默认策略：只保留以 tool_ 开头的工具（用户定义的 Agent 工具通常遵循这个命名）
            if func_name.startswith("tool_"):
                logger.debug(f"   保留用户工具（tool_ 前缀）: {func_name}")
                return True
            
            # 如果模块路径为空但函数名以 tool_ 开头，也保留（可能是动态创建的工具）
            # 其他工具默认过滤掉
            logger.debug(f"   过滤未知工具: {func_name} (模块: {func_module or 'unknown'})")
            return False
            
        except Exception as e:
            logger.warning(f"检查工具类型时出错: {e}, 工具: {tool}, 类型: {type(tool)}", exc_info=True)
            return False

    def _debug_llm_request(self, llm_request: LlmRequest) -> None:
        """
        输出 LlmRequest 的详细调试信息
        
        Args:
            llm_request: Google ADK 的 LlmRequest 对象
        """
        logger.info("=" * 80)
        logger.info("🔍 LlmRequest 详细调试信息:")
        logger.info("=" * 80)
        
        # 基本信息
        logger.info(f"  📋 LlmRequest 类型: {type(llm_request)}")
        logger.info(f"  📋 LlmRequest 模块: {type(llm_request).__module__}")
        
        # 检查继承关系
        try:
            mro = type(llm_request).__mro__
            logger.info(f"  📋 继承关系 (MRO): {[cls.__name__ for cls in mro]}")
        except:
            pass
        
        # 所有属性（包括私有属性，但过滤掉特殊方法）
        all_attrs = [attr for attr in dir(llm_request) if not (attr.startswith('__') and attr.endswith('__'))]
        public_attrs = [attr for attr in all_attrs if not attr.startswith('_')]
        logger.info(f"  📋 公共属性 ({len(public_attrs)} 个): {public_attrs}")
        logger.info(f"  📋 私有属性 ({len(all_attrs) - len(public_attrs)} 个): {[attr for attr in all_attrs if attr.startswith('_')]}")
        
        # 检查工具相关的属性（包括私有属性）
        tool_attrs = [attr for attr in all_attrs if ('tool' in attr.lower() or 'function' in attr.lower())]
        if tool_attrs:
            logger.info(f"  🔧 工具相关属性 ({len(tool_attrs)} 个): {tool_attrs}")
            for attr in tool_attrs:
                try:
                    value = getattr(llm_request, attr, None)
                    value_type = type(value)
                    value_str = str(value)
                    # 限制输出长度
                    if len(value_str) > 200:
                        value_str = value_str[:200] + "..."
                    logger.info(f"    - {attr}: {value_type} = {value_str}")
                    
                    # 如果是对象，检查其属性
                    if not isinstance(value, (str, int, float, bool, type(None), list, tuple, dict)):
                        try:
                            sub_attrs = [a for a in dir(value) if not a.startswith('__')]
                            if sub_attrs:
                                logger.info(f"      └─ 子属性: {sub_attrs[:10]}{'...' if len(sub_attrs) > 10 else ''}")
                        except:
                            pass
                except Exception as e:
                    logger.info(f"    - {attr}: 无法访问 ({e})")
        else:
            logger.info("  🔧 未找到工具相关属性")
        
        # 检查 contents 的结构
        if hasattr(llm_request, 'contents'):
            logger.info(f"  📝 Contents 数量: {len(llm_request.contents)}")
            for i, content in enumerate(llm_request.contents):
                logger.info(f"  📝 Content[{i}]: role={getattr(content, 'role', 'N/A')}, parts={len(getattr(content, 'parts', []))}")
                for j, part in enumerate(getattr(content, 'parts', [])):
                    part_info = []
                    if hasattr(part, 'text') and part.text:
                        text_preview = part.text[:50] + "..." if len(part.text) > 50 else part.text
                        part_info.append(f"text={text_preview}")
                    if hasattr(part, 'function_call') and part.function_call:
                        fc = part.function_call
                        fc_name = getattr(fc, 'name', 'unknown')
                        part_info.append(f"function_call={fc_name}")
                    if hasattr(part, 'function_response') and part.function_response:
                        fr = part.function_response
                        fr_name = getattr(fr, 'name', 'unknown')
                        part_info.append(f"function_response={fr_name}")
                    logger.info(f"    - Part[{j}]: {', '.join(part_info) if part_info else 'empty'}")
        else:
            logger.info("  📝 未找到 contents 属性")
        
        # 尝试访问所有可能的工具定义位置
        logger.info("  🔍 尝试访问工具定义的可能位置:")
        possible_paths = [
            ('tool_config', None),
            ('tool_config.function_declarations', lambda r: getattr(getattr(r, 'tool_config', None), 'function_declarations', None) if hasattr(r, 'tool_config') else None),
            ('tool_config.tools', lambda r: getattr(getattr(r, 'tool_config', None), 'tools', None) if hasattr(r, 'tool_config') else None),
            ('tools', None),
        ]
        
        for path_name, accessor in possible_paths:
            try:
                if accessor:
                    value = accessor(llm_request)
                else:
                    value = getattr(llm_request, path_name, None)
                
                if value is not None:
                    logger.info(f"    ✅ {path_name}: {type(value)}")
                    if isinstance(value, dict):
                        logger.info(f"       └─ 字典键: {list(value.keys())}")
                        logger.info(f"       └─ 字典值数量: {len(value)}")
                        if len(value) > 0:
                            first_key = list(value.keys())[0]
                            first_value = value[first_key]
                            logger.info(f"       └─ 第一个元素 [{first_key}]: {type(first_value)}")
                            # 如果是工具对象，尝试获取其函数名
                            if hasattr(first_value, 'function') or hasattr(first_value, '__name__'):
                                func_name = getattr(first_value, '__name__', None) or getattr(getattr(first_value, 'function', None), '__name__', None)
                                if func_name:
                                    logger.info(f"          └─ 函数名: {func_name}")
                    elif isinstance(value, (list, tuple)):
                        logger.info(f"       └─ 数量: {len(value)}")
                        if len(value) > 0:
                            logger.info(f"       └─ 第一个元素: {type(value[0])}")
                    else:
                        logger.info(f"       └─ 值: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
                else:
                    logger.info(f"    ❌ {path_name}: None")
            except Exception as e:
                logger.info(f"    ⚠️  {path_name}: 访问失败 ({e})")
        
        logger.info("=" * 80)

    def _debug_api_params(self, api_params: Dict[str, Any]) -> None:
        """
        输出 API 调用参数的调试信息（隐藏敏感信息）
        
        Args:
            api_params: API 调用参数字典
        """
        safe_params = api_params.copy()
        # 隐藏敏感信息
        if 'api_key' in safe_params:
            safe_params['api_key'] = '***'
        if 'messages' in safe_params:
            # 只显示消息数量，不显示内容
            safe_params['messages'] = f"[{len(safe_params['messages'])} messages]"
        if 'tools' in safe_params:
            # 只显示工具数量
            safe_params['tools'] = f"[{len(safe_params['tools'])} tools]"
        
        logger.debug("🔍 Qwen API 调用参数:")
        for key, value in safe_params.items():
            logger.debug(f"  - {key}: {value}")

    def _convert_tools_to_qwen_format(self, llm_request: LlmRequest) -> Optional[List[Dict[str, Any]]]:
        """
        将 Google ADK 的工具定义转换为 Qwen API 的格式
        
        Args:
            llm_request: Google ADK 的 LlmRequest 对象
            
        Returns:
            Qwen API 格式的工具定义列表，如果没有工具则返回 None
        """
        logger.debug("🔍 开始提取工具定义...")
        
        # 尝试从 llm_request 中获取工具定义
        # Google ADK 可能通过多种方式传递工具：
        # 1. tools 属性（直接的工具列表）
        # 2. tool_config 属性（工具配置对象）
        # 3. tool_config.function_declarations（函数声明列表）
        tools = None
        
        # 方法1: 检查 tools_dict（从日志看，这是 Google ADK 存储工具的地方）
        logger.info("  方法1: 检查 llm_request.tools_dict 属性")
        if hasattr(llm_request, "tools_dict"):
            tools_dict = llm_request.tools_dict
            logger.info(f"    - 找到 tools_dict: {type(tools_dict)}")
            if tools_dict and isinstance(tools_dict, dict):
                # tools_dict 是字典，键是工具名称，值是工具对象
                logger.info(f"    - tools_dict 键: {list(tools_dict.keys())}")
                tools_list = list(tools_dict.values())
                logger.info(f"    - 从 tools_dict 获取: {len(tools_list)} 个工具")
                for idx, tool_obj in enumerate(tools_list):
                    logger.info(f"      - 工具 [{idx+1}]: {type(tool_obj)}")
                    # 尝试从工具对象中提取实际的函数
                    if hasattr(tool_obj, 'function'):
                        func = tool_obj.function
                        logger.info(f"        └─ function 属性: {type(func)}")
                        if callable(func):
                            logger.info(f"        └─ 函数名: {getattr(func, '__name__', 'unknown')}")
                    elif hasattr(tool_obj, '__call__'):
                        logger.info(f"        └─ 可调用对象")
                    elif callable(tool_obj):
                        logger.info(f"        └─ 直接可调用，函数名: {getattr(tool_obj, '__name__', 'unknown')}")
                if tools_list:
                    tools = tools_list
        else:
            logger.info("    - 未找到 tools_dict 属性")
        
        # 方法2: 检查 tool_config（优先，因为这是 Google ADK 的标准方式）
        if not tools:
            logger.debug("  方法2: 检查 llm_request.tool_config 属性")
            if hasattr(llm_request, "tool_config"):
                tool_config = llm_request.tool_config
                logger.debug(f"    - 找到 tool_config: {type(tool_config)}")
                if tool_config:
                    # 检查 function_declarations
                    if hasattr(tool_config, "function_declarations"):
                        tools = tool_config.function_declarations
                        logger.debug(f"    - 从 function_declarations 获取: {len(tools) if tools else 0} 个工具")
                    # 检查 function_declaration（单数）
                    elif hasattr(tool_config, "function_declaration"):
                        tools = [tool_config.function_declaration]
                        logger.debug("    - 从 function_declaration 获取: 1 个工具")
                    # 检查 tools
                    elif hasattr(tool_config, "tools"):
                        tools = tool_config.tools
                        logger.debug(f"    - 从 tool_config.tools 获取: {len(tools) if isinstance(tools, (list, tuple)) else 1} 个工具")
                    else:
                        logger.debug("    - tool_config 中没有找到工具定义")
                else:
                    logger.debug("    - tool_config 为 None")
            else:
                logger.debug("    - 未找到 tool_config 属性")
        
        # 方法2: 直接检查 tools 属性（但要排除方法类型）
        if not tools:
            logger.debug("  方法2: 检查 llm_request.tools 属性（排除方法类型）")
            if hasattr(llm_request, "tools"):
                tools_attr = llm_request.tools
                logger.debug(f"    - 找到 tools 属性: {type(tools_attr)}")
                # 排除方法类型（如 append_tools）
                if callable(tools_attr) and not isinstance(tools_attr, type):
                    # 检查是否是方法（有 __self__ 属性）
                    if hasattr(tools_attr, "__self__"):
                        logger.debug("    - tools 是方法，跳过（不是工具列表）")
                        tools_attr = None
                
                if tools_attr:
                    if isinstance(tools_attr, (list, tuple)):
                        tools = tools_attr
                        logger.debug(f"    - 工具列表: {len(tools)} 个工具")
                    elif not callable(tools_attr):
                        tools = [tools_attr]
                        logger.debug(f"    - 转换为列表: 1 个工具")
            else:
                logger.debug("    - 未找到 tools 属性")
        
        # 方法3: 检查所有属性，查找可能的工具定义（排除方法）
        if not tools:
            logger.debug("  方法3: 检查所有属性，查找工具相关属性（排除方法）")
            tool_attrs = []
            for attr_name in dir(llm_request):
                if not attr_name.startswith("_") and ("tool" in attr_name.lower() or "function" in attr_name.lower()):
                    tool_attrs.append(attr_name)
                    attr_value = getattr(llm_request, attr_name, None)
                    logger.debug(f"    - 检查属性 {attr_name}: {type(attr_value)}")
                    
                    # 跳过方法类型
                    if callable(attr_value) and hasattr(attr_value, "__self__"):
                        logger.debug(f"      -> 跳过方法: {attr_name}")
                        continue
                    
                    if attr_value and isinstance(attr_value, (list, tuple)) and len(attr_value) > 0:
                        # 可能是工具列表
                        if callable(attr_value[0]) or (hasattr(attr_value[0], "__name__")):
                            tools = attr_value
                            logger.debug(f"      -> 找到工具列表: {len(tools)} 个工具")
                            break
            if not tools and tool_attrs:
                logger.debug(f"    - 找到工具相关属性但无法提取: {tool_attrs}")
        
        if not tools:
            logger.warning("⚠️  未找到工具定义，跳过工具调用逻辑")
            # 输出详细的调试信息
            logger.info("🔍 工具定义提取失败，输出详细诊断信息...")
            self._debug_llm_request(llm_request)
            
            # 尝试从其他来源获取工具
            logger.info("🔍 尝试从其他来源获取工具定义...")
            tools = self._try_get_tools_from_other_sources(llm_request)
            if tools:
                logger.info(f"✅ 从备用来源获取到 {len(tools) if isinstance(tools, (list, tuple)) else 1} 个工具")
            else:
                logger.warning("❌ 所有来源都未找到工具定义")
                return None
        
        tool_count = len(tools) if isinstance(tools, (list, tuple)) else 1
        logger.info(f"🔧 找到 {tool_count} 个工具定义，开始过滤和转换...")

        # 过滤掉内部工具，只保留用户定义的 Agent 工具
        user_tools = []
        for idx, tool in enumerate(tools):
            # 详细记录工具信息
            try:
                func_name = None
                func_module = None
                if callable(tool):
                    func_name = getattr(tool, "__name__", None)
                    func_module = getattr(tool, "__module__", None)
                elif hasattr(tool, "name"):
                    func_name = tool.name
                elif hasattr(tool, "__name__"):
                    func_name = tool.__name__
                elif hasattr(tool, "function"):
                    func = tool.function
                    if callable(func):
                        func_name = getattr(func, "__name__", None)
                        func_module = getattr(func, "__module__", None)
                    elif hasattr(func, "name"):
                        func_name = func.name
                
                logger.info(f"   检查工具 [{idx+1}]: 名称={func_name}, 类型={type(tool)}, 模块={func_module}")
            except Exception as e:
                logger.warning(f"   检查工具 [{idx+1}] 时出错: {e}, 类型={type(tool)}")
            
            if self._is_user_tool(tool):
                user_tools.append(tool)
                logger.info(f"   ✅ 保留工具: {func_name or 'unknown'}")
            else:
                logger.warning(f"   ❌ 过滤掉工具: {func_name or type(tool)}")
        
        if not user_tools:
            logger.warning(f"⚠️  过滤后没有用户定义的 Agent 工具，跳过工具调用逻辑")
            logger.info(f"   原始工具数量: {tool_count}, 过滤后: 0")
            return None
        
        logger.info(f"🔧 过滤后保留 {len(user_tools)} 个用户工具，开始转换为 Qwen API 格式")

        qwen_tools = []
        for idx, tool in enumerate(user_tools):
            logger.debug(f"  处理工具 [{idx+1}/{len(user_tools)}]: {type(tool)}")
            try:
                # 获取函数对象（可能是函数本身或函数声明对象）
                func = tool
                if hasattr(tool, "function"):
                    func = tool.function
                elif hasattr(tool, "name"):
                    # 可能是函数声明对象，需要获取实际的函数
                    func = tool
                
                # 获取函数名
                func_name = None
                if callable(func):
                    func_name = func.__name__
                elif hasattr(func, "name"):
                    func_name = func.name
                elif hasattr(func, "__name__"):
                    func_name = func.__name__
                
                # 特殊处理：TransferToAgentTool 对象
                if not func_name and hasattr(tool, "__class__"):
                    class_name = tool.__class__.__name__
                    if "TransferToAgentTool" in class_name or "transfer_to_agent" in class_name.lower():
                        func_name = "transfer_to_agent"
                        logger.debug(f"   检测到 TransferToAgentTool 对象，使用函数名: {func_name}")
                
                if not func_name:
                    logger.warning(f"无法获取工具函数名，跳过工具: {tool}, 类型: {type(tool)}")
                    continue
                
                # 获取函数文档字符串作为描述
                description = ""
                if callable(func):
                    description = inspect.getdoc(func) or ""
                elif hasattr(func, "description"):
                    description = func.description or ""
                elif hasattr(tool, "description"):
                    description = tool.description or ""
                
                # 特殊处理：TransferToAgentTool 的描述和参数
                available_agents = []  # 在外部作用域定义，以便后续使用
                agent_descriptions = {}
                
                if func_name == "transfer_to_agent":
                    # 尝试从 TransferToAgentTool 对象获取子 agent 信息
                    # 检查 tool 对象是否有 sub_agents 或 agent 属性
                    if hasattr(tool, "agent") and tool.agent:
                        agent_obj = tool.agent
                        if hasattr(agent_obj, "sub_agents") and agent_obj.sub_agents:
                            for sub_agent in agent_obj.sub_agents:
                                agent_name = getattr(sub_agent, "name", None)
                                agent_desc = getattr(sub_agent, "description", "")
                                if agent_name:
                                    available_agents.append(agent_name)
                                    if agent_desc:
                                        agent_descriptions[agent_name] = agent_desc
                    
                    # 构建描述
                    if available_agents:
                        agent_list = ", ".join(available_agents)
                        description = f"将请求转发给合适的子 Agent 处理。可用的子 Agent: {agent_list}"
                        logger.info(f"   📋 找到可用的子 Agent: {available_agents}")
                    else:
                        description = "将请求转发给合适的子 Agent 处理。可用的子 Agent: assistant_agent (日常助手), remote_agent_1 (希希咖啡), remote_agent_2 (送了么配送) 等"
                        logger.warning(f"   ⚠️ 无法从 TransferToAgentTool 获取子 Agent 列表，使用默认描述")
                
                # 获取函数签名
                sig = None
                if callable(func):
                    try:
                        sig = inspect.signature(func)
                    except (ValueError, TypeError):
                        pass
                
                # 构建参数定义
                parameters = {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
                
                # 特殊处理：TransferToAgentTool 的参数（如果没有签名）
                if not sig and func_name == "transfer_to_agent":
                    # transfer_to_agent 通常需要一个 agent_name 参数
                    # 直接构建参数定义，不依赖签名
                    logger.debug(f"   为 transfer_to_agent 创建默认参数定义")
                    
                    # 构建 agent_name 参数的描述
                    agent_name_desc = "要转发到的子 Agent 名称"
                    if available_agents:
                        agent_name_desc += f"。可选值: {', '.join(available_agents)}"
                    else:
                        agent_name_desc += "。可选值: assistant_agent (日常助手), remote_agent_1 (希希咖啡), remote_agent_2 (送了么配送) 等"
                    
                    parameters = {
                        "type": "object",
                        "properties": {
                            "agent_name": {
                                "type": "string",
                                "description": agent_name_desc
                            }
                        },
                        "required": ["agent_name"]
                    }
                    # 跳过签名处理，直接使用上面的参数定义
                    sig = None
                
                if sig:
                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue
                        
                        param_info = {
                            "type": "string",  # 默认类型
                            "description": ""
                        }
                        
                        # 从参数注解获取类型
                        if param.annotation != inspect.Parameter.empty:
                            type_str = str(param.annotation)
                            # 映射 Python 类型到 JSON Schema 类型
                            if "int" in type_str or "Integer" in type_str:
                                param_info["type"] = "integer"
                            elif "float" in type_str or "Float" in type_str or "number" in type_str:
                                param_info["type"] = "number"
                            elif "bool" in type_str or "Boolean" in type_str:
                                param_info["type"] = "boolean"
                            elif "list" in type_str or "List" in type_str or "Array" in type_str:
                                param_info["type"] = "array"
                            elif "dict" in type_str or "Dict" in type_str or "object" in type_str:
                                param_info["type"] = "object"
                            else:
                                param_info["type"] = "string"
                        
                        # 从文档字符串中提取参数描述
                        if description:
                            # 简单的文档字符串解析（查找 Args: 部分）
                            lines = description.split("\n")
                            in_args = False
                            for line in lines:
                                if "Args:" in line or "参数:" in line:
                                    in_args = True
                                    continue
                                if in_args and param_name in line:
                                    # 提取描述
                                    parts = line.split(":", 1)
                                    if len(parts) > 1:
                                        param_info["description"] = parts[1].strip()
                                    break
                        
                        # 检查是否有默认值
                        if param.default != inspect.Parameter.empty:
                            param_info["default"] = param.default
                        else:
                            parameters["required"].append(param_name)
                        
                        parameters["properties"][param_name] = param_info
                
                # 构建 Qwen API 格式的工具定义
                qwen_tool = {
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "description": description.split("\n")[0] if description else f"{func_name} 工具",
                        "parameters": parameters
                    }
                }
                
                qwen_tools.append(qwen_tool)
                logger.info(f"✅ 转换工具定义: {func_name} (参数: {len(parameters.get('properties', {}))} 个)")
                
            except Exception as e:
                logger.error(f"❌ 转换工具定义时出错: {e}", exc_info=True)
                logger.warning(f"   工具对象: {tool}, 类型: {type(tool)}")
                continue
        
        return qwen_tools if qwen_tools else None

    def _build_messages_with_tools(self, llm_request: LlmRequest) -> List[Dict[str, Any]]:
        """
        构建包含工具调用的消息列表（Qwen API 格式）
        
        Args:
            llm_request: Google ADK 的 LlmRequest 对象
            
        Returns:
            Qwen API 格式的消息列表
        """
        messages = []
        
        for content in llm_request.contents:
            role = "user" if content.role == "user" else "assistant"
            message_content = None
            tool_calls = None
            tool_call_id = None
            
            for part in content.parts:
                # 处理文本消息
                if hasattr(part, "text") and part.text:
                    if message_content is None:
                        message_content = part.text
                    else:
                        message_content += "\n" + part.text
                
                # 处理 function_call（模型请求调用工具）
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    if tool_calls is None:
                        tool_calls = []
                    
                    tool_call = {
                        "id": getattr(fc, "id", None) or f"call_{len(tool_calls)}",
                        "type": "function",
                        "function": {
                            "name": getattr(fc, "name", ""),
                            "arguments": json.dumps(getattr(fc, "args", {}), ensure_ascii=False)
                        }
                    }
                    tool_calls.append(tool_call)
                    tool_call_id = tool_call["id"]
                
                # 处理 function_response（工具执行结果）
                if hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    logger.debug(f"   处理 function_response: {getattr(fr, 'name', 'unknown')}")
                    
                    # Qwen API 需要将 function_response 转换为 tool 消息
                    response_data = getattr(fr, "response", {})
                    
                    # 确保 response 是可序列化的
                    if not isinstance(response_data, (dict, list, str, int, float, bool, type(None))):
                        try:
                            response_data = str(response_data)
                        except:
                            response_data = {}
                    
                    # 获取 tool_call_id（需要匹配之前的 tool_call）
                    tool_call_id = getattr(fr, "id", None) or getattr(fr, "name", "") or "unknown"
                    
                    tool_message = {
                        "role": "tool",
                        "content": json.dumps(response_data, ensure_ascii=False) if not isinstance(response_data, str) else response_data,
                        "tool_call_id": tool_call_id
                    }
                    messages.append(tool_message)
                    logger.debug(f"   添加 tool 消息: tool_call_id={tool_call_id}, content_length={len(str(response_data))}")
            
            # 构建消息
            if tool_calls:
                # 如果有工具调用，构建 assistant 消息，包含 tool_calls
                message = {
                    "role": role,
                    "content": message_content or "",
                    "tool_calls": tool_calls
                }
                messages.append(message)
            elif message_content:
                # 普通文本消息
                messages.append({
                    "role": role,
                    "content": message_content
                })
        
        return messages

    def _parse_tool_calls(self, qwen_response: Any) -> Optional[List[types.FunctionCall]]:
        """
        解析 Qwen API 返回的 tool_calls，转换为 Google ADK 格式
        
        Args:
            qwen_response: Qwen API 的响应对象
            
        Returns:
            Google ADK 格式的 FunctionCall 列表，如果没有则返回 None
        """
        tool_calls = []
        
        # 检查响应中是否有 tool_calls
        output = getattr(qwen_response, "output", None)
        if not output:
            return None
        
        # 从 choices 中提取 tool_calls
        # 注意：避免使用 hasattr 检查 dashscope 响应对象，因为它会触发 KeyError
        choices = None
        try:
            choices = getattr(output, "choices", None)
            if choices:
                choices = choices
        except (AttributeError, KeyError):
            choices = None
        
        # 尝试直接从 output.message 获取 tool_calls
        if not choices:
            try:
                message = getattr(output, "message", None)
                if message:
                    # 安全地获取 tool_calls
                    tool_calls_data = None
                    if isinstance(message, dict):
                        tool_calls_data = message.get("tool_calls")
                    else:
                        try:
                            tool_calls_data = getattr(message, "tool_calls", None)
                        except (AttributeError, KeyError):
                            tool_calls_data = None
                    
                    if tool_calls_data:
                        for tc in tool_calls_data:
                            try:
                                func_name = tc.get("function", {}).get("name", "") if isinstance(tc, dict) else getattr(tc, "function", {}).get("name", "")
                                func_args_str = tc.get("function", {}).get("arguments", "{}") if isinstance(tc, dict) else getattr(tc, "function", {}).get("arguments", "{}")
                                
                                try:
                                    func_args = json.loads(func_args_str)
                                except (json.JSONDecodeError, TypeError):
                                    func_args = {}
                                
                                fc = types.FunctionCall(
                                    name=func_name,
                                    args=func_args
                                )
                                tool_calls.append(fc)
                            except Exception as e:
                                logger.warning(f"解析 tool_call 时出错: {e}")
                        return tool_calls if tool_calls else None
            except (AttributeError, KeyError):
                pass
        
        if choices:
            for choice in choices:
                message = None
                # 安全地获取 message
                try:
                    if isinstance(choice, dict):
                        message = choice.get("message", {})
                    else:
                        message = getattr(choice, "message", None)
                except (AttributeError, KeyError):
                    message = None
                
                if not message:
                    continue
                
                # 检查 message 中是否有 tool_calls（避免使用 hasattr）
                tool_calls_data = None
                try:
                    if isinstance(message, dict):
                        tool_calls_data = message.get("tool_calls")
                    else:
                        # 使用 getattr 安全访问，避免触发 KeyError
                        tool_calls_data = getattr(message, "tool_calls", None)
                except (AttributeError, KeyError):
                    tool_calls_data = None
                
                if tool_calls_data:
                    for tc in tool_calls_data:
                        try:
                            func_name = ""
                            func_args = {}
                            
                            if isinstance(tc, dict):
                                func_info = tc.get("function", {})
                                func_name = func_info.get("name", "")
                                func_args_str = func_info.get("arguments", "{}")
                                try:
                                    func_args = json.loads(func_args_str)
                                except (json.JSONDecodeError, TypeError):
                                    func_args = {}
                            else:
                                func_name = getattr(tc, "function", {}).get("name", "")
                                func_args_str = getattr(tc, "function", {}).get("arguments", "{}")
                                try:
                                    func_args = json.loads(func_args_str)
                                except (json.JSONDecodeError, TypeError):
                                    func_args = {}
                            
                            if func_name:
                                fc = types.FunctionCall(
                                    name=func_name,
                                    args=func_args
                                )
                                tool_calls.append(fc)
                        except Exception as e:
                            logger.warning(f"解析 tool_call 时出错: {e}")
        
        return tool_calls if tool_calls else None

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ) -> AsyncGenerator[LlmResponse, None]:
        """异步生成内容，使用 dashscope 调用 Qwen API，支持工具调用"""
        from dashscope import Generation

        try:
            logger.info(f"🚀 QwenLlm.generate_content_async 开始 (stream={stream})")
            
            # 获取模型名称（从 self.model 属性，由 LLMRegistry 设置）
            model_name = getattr(self, "model", "qwen-plus")
            logger.info(f"  📋 模型名称: {model_name}")
            
            # 尝试确定当前使用的 Agent（用于调试）
            # 方法1: 从 tools_dict 推断
            agent_name = "unknown"
            if hasattr(llm_request, 'tools_dict') and llm_request.tools_dict:
                tools_keys = list(llm_request.tools_dict.keys())
                logger.info(f"  📋 tools_dict 中的工具: {tools_keys}")
                
                # 如果只有 transfer_to_agent，说明是 root_agent（没有直接工具，只有路由工具）
                if tools_keys == ['transfer_to_agent']:
                    agent_name = "root_agent (只有路由工具，没有用户工具)"
                elif len(tools_keys) > 0:
                    # 检查是否有用户工具
                    user_tools = [k for k in tools_keys if k.startswith('tool_')]
                    if user_tools:
                        agent_name = f"agent_with_tools (包含用户工具: {user_tools[:3]}...)"
                    else:
                        agent_name = f"agent_with_internal_tools (只有内部工具: {tools_keys})"
            
            # 方法2: 检查 LlmRequest 的其他属性
            if hasattr(llm_request, 'model'):
                logger.info(f"  📋 LlmRequest.model: {llm_request.model}")
            
            # 方法3: 检查 self (QwenLlm 实例) 是否有 agent 引用
            if hasattr(self, '_agent'):
                logger.info(f"  📋 QwenLlm._agent: {getattr(self, '_agent', None)}")
            if hasattr(self, 'agent'):
                logger.info(f"  📋 QwenLlm.agent: {getattr(self, 'agent', None)}")
            
            logger.info(f"  📋 推断的 Agent: {agent_name}")
            
            # 检查是否是路由后的子 agent 调用（通过检查 contents 中的 function_response）
            is_sub_agent_call = False
            transfer_result = None
            if hasattr(llm_request, 'contents'):
                for content in llm_request.contents:
                    for part in getattr(content, 'parts', []):
                        if hasattr(part, 'function_response') and part.function_response:
                            fr = part.function_response
                            fr_name = getattr(fr, 'name', '')
                            fr_response = getattr(fr, 'response', {})
                            if 'transfer_to_agent' in str(fr_name) or 'agent' in str(fr_name).lower():
                                is_sub_agent_call = True
                                transfer_result = fr_response
                                logger.info(f"  📋 检测到子 Agent 调用（通过 function_response）")
                                logger.info(f"  📋 transfer_to_agent 响应: {transfer_result}")
                                break
                    if is_sub_agent_call:
                        break
            
            # 如果是子 agent 调用，输出更详细的信息
            if is_sub_agent_call:
                logger.info(f"  📋 这是路由后的子 Agent 调用")
                logger.info(f"  📋 子 Agent 的 tools_dict: {getattr(llm_request, 'tools_dict', {})}")
            
            # 转换工具定义为 Qwen API 格式
            logger.debug("  步骤1: 提取和转换工具定义")
            qwen_tools = self._convert_tools_to_qwen_format(llm_request)
            if qwen_tools:
                tool_names = [tool.get("function", {}).get("name", "unknown") for tool in qwen_tools]
                logger.info(f"🔧 成功转换 {len(qwen_tools)} 个工具定义: {tool_names}")
            else:
                logger.debug("  未找到工具定义，将进行纯文本对话")
            
            # 构建消息列表（支持工具调用）
            logger.debug("  步骤2: 构建消息列表")
            messages = self._build_messages_with_tools(llm_request)
            
            # 如果没有消息，使用旧的简单方式（向后兼容）
            if not messages:
                logger.debug("  使用简单方式构建消息（向后兼容）")
                for content in llm_request.contents:
                    role = "user" if content.role == "user" else "assistant"
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            messages.append({"role": role, "content": part.text})
            
            logger.debug(f"  消息列表: {len(messages)} 条消息")

            # 准备 API 调用参数
            api_params = {
                "model": model_name,
                "messages": messages,
            }
            
            # 如果有工具定义，添加到参数中
            if qwen_tools:
                api_params["tools"] = qwen_tools
                logger.info(f"🔧 传递 {len(qwen_tools)} 个工具定义给 Qwen API")
            
            # 输出调试信息
            self._debug_api_params(api_params)

            if stream:
                # 流式模式：调用 Qwen API 时传递 stream=True
                logger.info("  步骤3: 调用 Qwen API (流式模式)")
                api_params["stream"] = True
                try:
                    response = Generation.call(**api_params)
                    logger.debug("  ✅ Qwen API 调用成功（流式）")
                except Exception as e:
                    logger.error(f"❌ Qwen API 调用失败（流式）: {e}", exc_info=True)
                    raise

                # 流式返回响应
                accumulated_text = ""
                accumulated_tool_calls = []
                last_chunk = None
                
                for chunk in response:
                    last_chunk = chunk
                    if chunk.status_code == 200:
                        # dashscope 流式响应的格式
                        if hasattr(chunk, "output") and chunk.output:
                            # 检查是否有 tool_calls
                            tool_calls = self._parse_tool_calls(chunk)
                            if tool_calls:
                                accumulated_tool_calls.extend(tool_calls)
                            
                            chunk_text = ""
                            # 检查是否有 choices
                            if hasattr(chunk.output, "choices") and chunk.output.choices:
                                for choice in chunk.output.choices:
                                    if hasattr(choice, "message") and choice.message:
                                        content = choice.message.get("content", "") if isinstance(choice.message, dict) else getattr(choice.message, "content", "")
                                        if content:
                                            chunk_text = content
                            # 或者直接检查 output.text
                            elif hasattr(chunk.output, "text") and chunk.output.text:
                                chunk_text = chunk.output.text
                            
                            if chunk_text:
                                # 检测 chunk_text 是否是累积内容
                                # 如果 chunk_text 以 accumulated_text 开头，说明是累积内容，需要提取增量
                                if chunk_text.startswith(accumulated_text):
                                    # 提取增量部分
                                    incremental_text = chunk_text[len(accumulated_text):]
                                    accumulated_text = chunk_text
                                else:
                                    # 假设是增量内容
                                    incremental_text = chunk_text
                                    accumulated_text += incremental_text
                                
                                # 只发送增量部分（如果有）
                                if incremental_text:
                                    # 构建 LlmResponse 对象（中间块，partial=True）
                                    yield LlmResponse(
                                        content=types.Content(
                                            parts=[types.Part(text=incremental_text)],
                                            role="model",
                                        ),
                                        partial=True,
                                        turn_complete=False,
                                    )
                    else:
                        # 处理错误
                        error_msg = getattr(chunk, "message", f"Status code: {chunk.status_code}")
                        logger.error(f"❌ Qwen API 返回错误（流式）: {error_msg}")
                        logger.error(f"   响应对象: {chunk}")
                        raise ValueError(f"Qwen API error: {error_msg}")
                
                # 处理最后一个响应
                # 如果有 tool_calls，优先返回 tool_calls
                if accumulated_tool_calls:
                    # 从最后一个 chunk 再次检查，确保获取完整的 tool_calls
                    if last_chunk:
                        final_tool_calls = self._parse_tool_calls(last_chunk)
                        if final_tool_calls:
                            accumulated_tool_calls = final_tool_calls
                    
                    logger.info(f"🔧 Qwen API 返回 {len(accumulated_tool_calls)} 个工具调用请求")
                    for idx, fc in enumerate(accumulated_tool_calls):
                        logger.info(f"   工具调用 [{idx+1}]: {getattr(fc, 'name', 'unknown')}({getattr(fc, 'args', {})})")
                    
                    # 返回工具调用
                    parts = [types.Part(function_call=fc) for fc in accumulated_tool_calls]
                    logger.debug(f"   返回 FunctionCall 响应，turn_complete=False（等待工具执行结果）")
                    yield LlmResponse(
                        content=types.Content(
                            parts=parts,
                            role="model",
                        ),
                        partial=False,
                        turn_complete=False,  # 工具调用后还需要继续对话
                    )
                elif accumulated_text:
                    # 返回文本响应
                    logger.debug(f"   返回文本响应，长度: {len(accumulated_text)} 字符")
                    yield LlmResponse(
                        content=types.Content(
                            parts=[types.Part(text=accumulated_text)],
                            role="model",
                        ),
                        partial=False,
                        turn_complete=True,
                    )
                else:
                    logger.warning("⚠️  流式响应中既没有 tool_calls 也没有文本内容")
            else:
                # 非流式模式：调用 Qwen API 时传递 stream=False
                logger.info("  步骤3: 调用 Qwen API (非流式模式)")
                api_params["stream"] = False
                try:
                    response = Generation.call(**api_params)
                    logger.debug("  ✅ Qwen API 调用成功（非流式）")
                except Exception as e:
                    logger.error(f"❌ Qwen API 调用失败（非流式）: {e}", exc_info=True)
                    raise

                # 处理非流式响应
                if hasattr(response, "output") and response.output:
                    # 首先检查是否有 tool_calls
                    tool_calls = self._parse_tool_calls(response)
                    
                    if tool_calls:
                        logger.info(f"🔧 Qwen API 返回 {len(tool_calls)} 个工具调用请求（非流式）")
                        for idx, fc in enumerate(tool_calls):
                            logger.info(f"   工具调用 [{idx+1}]: {getattr(fc, 'name', 'unknown')}({getattr(fc, 'args', {})})")
                        
                        # 返回工具调用
                        parts = [types.Part(function_call=fc) for fc in tool_calls]
                        logger.debug(f"   返回 FunctionCall 响应，turn_complete=False（等待工具执行结果）")
                        yield LlmResponse(
                            content=types.Content(
                                parts=parts,
                                role="model",
                            ),
                            partial=False,
                            turn_complete=False,  # 工具调用后还需要继续对话
                        )
                    else:
                        # 返回文本响应
                        response_text = ""
                        # 检查是否有 choices
                        if hasattr(response.output, "choices") and response.output.choices:
                            for choice in response.output.choices:
                                if hasattr(choice, "message") and choice.message:
                                    content = choice.message.get("content", "") if isinstance(choice.message, dict) else getattr(choice.message, "content", "")
                                    if content:
                                        response_text = content
                                        break
                        # 或者直接检查 output.text
                        elif hasattr(response.output, "text") and response.output.text:
                            response_text = response.output.text
                        
                        if response_text:
                            # 构建 LlmResponse 对象（非流式，partial=False, turn_complete=True）
                            yield LlmResponse(
                                content=types.Content(
                                    parts=[types.Part(text=response_text)],
                                    role="model",
                                ),
                                partial=False,
                                turn_complete=True,
                            )
                else:
                    # 处理错误
                    error_msg = getattr(response, "message", "Unknown error")
                    logger.error(f"❌ Qwen API 返回错误（非流式）: {error_msg}")
                    logger.error(f"   响应对象: {response}")
                    raise ValueError(f"Qwen API error: {error_msg}")
                
        except Exception as e:
            # 顶层异常处理，确保所有异常都被记录
            logger.error(f"❌ QwenLlm.generate_content_async 发生异常: {e}", exc_info=True)
            logger.error(f"   异常类型: {type(e).__name__}")
            logger.error(f"   stream 模式: {stream}")
            # 重新抛出异常，让 Google ADK 处理
            raise

    def connect(self, llm_request: LlmRequest) -> BaseLlmConnection:
        """创建连接（用于流式响应）"""
        # 返回一个连接对象，这里简化实现
        return BaseLlmConnection(llm=self, llm_request=llm_request)

