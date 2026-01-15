import { useState, useRef, useEffect } from 'react';
import {
  Send,
  Loader2,
  Sparkles,
  Wifi,
  Battery,
  Signal,
  Zap,
  ArrowRight,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ENDPOINT } from '../utils/config';

// 工具调用状态
interface ToolCall {
  id?: string;
  name: string;
  args: Record<string, unknown>;
  status: 'calling' | 'success' | 'error';
  result?: string;
}

// Agent 转移
interface AgentTransfer {
  from?: string;
  to: string;
  timestamp: Date;
}

// A2A 调用
interface A2ACall {
  type: string;
  agent?: string;
  details?: Record<string, unknown>;
  timestamp: Date;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolCalls?: ToolCall[];
  agentTransfers?: AgentTransfer[];
  a2aCalls?: A2ACall[];
  isStreaming?: boolean;
}

interface PhoneSimulatorProps {
  onOrderCreated?: () => void;
}

export default function PhoneSimulator({
  onOrderCreated,
}: PhoneSimulatorProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: `你好！

我是你的智能助手，可以帮你：
- 查询天气
- 查询时间

我已连接到希希咖啡店与送了么配送服务，可以帮你完成以下任务：
- ☕ 点咖啡、查菜单
- 📋 查询订单状态
- 🛵 安排外卖配送

有什么我可以帮你的吗？`,
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [currentStatus, setCurrentStatus] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // 更新时间
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const formatPhoneTime = (date: Date) => {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setCurrentStatus('连接中...');

    try {
      const response = await fetch(`${ENDPOINT}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage.content,
          session_id: sessionId,
        }),
      });

      if (!response.ok) throw new Error('请求失败');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      let assistantContent = '';
      const assistantMessageId = (Date.now() + 1).toString();
      const toolCalls: ToolCall[] = [];
      const agentTransfers: AgentTransfer[] = [];
      const a2aCalls: A2ACall[] = [];

      // 创建初始的助手消息
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          toolCalls: [],
          agentTransfers: [],
          a2aCalls: [],
          isStreaming: true,
        },
      ]);

      setCurrentStatus('思考中...');

      let buffer = '';

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 保留不完整的行

        for (const line of lines) {
          if (line.startsWith('data:')) {
            try {
              const jsonStr = line.slice(5).trim();
              if (!jsonStr || jsonStr === '{}') continue;

              const data = JSON.parse(jsonStr);

              // 处理 session_id
              if (data.session_id) {
                setSessionId(data.session_id);
              }

              // 处理文本内容 - 流式更新
              if (data.type === 'text' && data.content) {
                // partial=true 表示增量内容，需要追加
                // partial=false 表示完整内容，直接替换
                if (data.partial === false) {
                  // 完整内容，直接替换（作为最终确认）
                  assistantContent = data.content;
                } else {
                  // 增量内容，追加
                  assistantContent += data.content;
                }
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIdx = newMessages.length - 1;
                  if (
                    lastIdx >= 0 &&
                    newMessages[lastIdx].role === 'assistant'
                  ) {
                    // 创建新对象以触发 React 重新渲染
                    newMessages[lastIdx] = {
                      ...newMessages[lastIdx],
                      content: assistantContent,
                    };
                  }
                  return newMessages;
                });
              }

              // 处理工具调用
              if (data.type === 'function_call' && data.name) {
                setCurrentStatus(`调用工具: ${data.name}`);
                const newToolCall: ToolCall = {
                  id: data.id,
                  name: data.name,
                  args: data.args || {},
                  status: 'calling',
                };
                toolCalls.push(newToolCall);
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIdx = newMessages.length - 1;
                  if (
                    lastIdx >= 0 &&
                    newMessages[lastIdx].role === 'assistant'
                  ) {
                    newMessages[lastIdx] = {
                      ...newMessages[lastIdx],
                      toolCalls: [...toolCalls],
                    };
                  }
                  return newMessages;
                });
              }

              // 处理工具结果
              if (data.type === 'function_response' && data.name) {
                setCurrentStatus(`工具返回: ${data.name}`);
                const existingCall = toolCalls.find(
                  (tc) => tc.name === data.name && tc.status === 'calling'
                );
                if (existingCall) {
                  existingCall.status = 'success';
                  existingCall.result = data.response;
                }
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIdx = newMessages.length - 1;
                  if (
                    lastIdx >= 0 &&
                    newMessages[lastIdx].role === 'assistant'
                  ) {
                    newMessages[lastIdx] = {
                      ...newMessages[lastIdx],
                      toolCalls: [...toolCalls],
                    };
                  }
                  return newMessages;
                });
              }

              // 处理 Agent 转移
              if (data.type === 'agent_transfer' && data.agent) {
                setCurrentStatus(`转交给: ${data.agent}`);
                agentTransfers.push({
                  to: data.agent,
                  timestamp: new Date(),
                });
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIdx = newMessages.length - 1;
                  if (
                    lastIdx >= 0 &&
                    newMessages[lastIdx].role === 'assistant'
                  ) {
                    newMessages[lastIdx] = {
                      ...newMessages[lastIdx],
                      agentTransfers: [...agentTransfers],
                    };
                  }
                  return newMessages;
                });
              }

              // 处理 A2A 事件
              if (data.type === 'a2a_event') {
                setCurrentStatus(`A2A: ${data.event_type}`);
                a2aCalls.push({
                  type: data.event_type,
                  details: data.details,
                  timestamp: new Date(),
                });
                setMessages((prev) => {
                  const newMessages = [...prev];
                  const lastIdx = newMessages.length - 1;
                  if (
                    lastIdx >= 0 &&
                    newMessages[lastIdx].role === 'assistant'
                  ) {
                    newMessages[lastIdx] = {
                      ...newMessages[lastIdx],
                      a2aCalls: [...a2aCalls],
                    };
                  }
                  return newMessages;
                });
              }
            } catch (e) {
              // 忽略解析错误，可能是不完整的 JSON
              console.debug('Parse error:', e);
            }
          }
        }
      }

      // 标记流式传输结束
      setMessages((prev) => {
        const newMessages = [...prev];
        const lastIdx = newMessages.length - 1;
        if (lastIdx >= 0 && newMessages[lastIdx].role === 'assistant') {
          newMessages[lastIdx] = {
            ...newMessages[lastIdx],
            isStreaming: false,
          };
        }
        return newMessages;
      });

      // 检查是否创建了订单
      if (
        assistantContent.includes('订单创建成功') ||
        assistantContent.includes('订单号')
      ) {
        onOrderCreated?.();
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: '抱歉，出现了一些问题。请稍后重试。',
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
      setCurrentStatus('');
    }
  };

  const quickActions = [
    { label: '☕ 看菜单', message: '我想看看菜单' },
    { label: '📋 查订单', message: '查询我的订单' },
    { label: '🛵 叫配送', message: '我要配送' },
  ];

  // 渲染工具调用
  const renderToolCalls = (toolCalls: ToolCall[]) => {
    if (!toolCalls || toolCalls.length === 0) return null;

    return (
      <div className='mt-2 space-y-1'>
        {toolCalls.map((tool, idx) => (
          <div
            key={idx}
            className='flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 text-[10px]'
          >
            {tool.status === 'calling' ? (
              <Loader2 className='w-3 h-3 text-blue-500 animate-spin' />
            ) : tool.status === 'success' ? (
              <CheckCircle className='w-3 h-3 text-green-500' />
            ) : (
              <AlertCircle className='w-3 h-3 text-red-500' />
            )}
            <Zap className='w-2.5 h-2.5 text-blue-500' />
            <span className='font-medium text-blue-700'>
              {tool.name.replace('tool_', '')}
            </span>
            {tool.args && Object.keys(tool.args).length > 0 && (
              <span className='text-blue-500 truncate max-w-[100px]'>
                (
                {Object.entries(tool.args)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(', ')}
                )
              </span>
            )}
          </div>
        ))}
      </div>
    );
  };

  // 渲染 Agent 转移
  const renderAgentTransfers = (transfers: AgentTransfer[]) => {
    if (!transfers || transfers.length === 0) return null;

    return (
      <div className='mt-2 space-y-1'>
        {transfers.map((transfer, idx) => (
          <div
            key={idx}
            className='flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-100 text-[10px]'
          >
            <ArrowRight className='w-3 h-3 text-purple-500' />
            <span className='text-purple-600'>转交给</span>
            <span className='font-medium text-purple-700'>{transfer.to}</span>
          </div>
        ))}
      </div>
    );
  };

  // 渲染 A2A 调用
  const renderA2ACalls = (calls: A2ACall[]) => {
    if (!calls || calls.length === 0) return null;

    return (
      <div className='mt-2 space-y-1'>
        {calls.map((call, idx) => (
          <div
            key={idx}
            className='flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-100 text-[10px]'
          >
            <Sparkles className='w-3 h-3 text-amber-500' />
            <span className='font-medium text-amber-700'>A2A</span>
            <span className='text-amber-600'>{call.type}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className='relative'>
      {/* 手机外框 - 响应式尺寸 */}
      <div
        className='relative phone-frame rounded-[2.5rem] p-3'
        style={{
          background:
            'linear-gradient(145deg, #2d3748 0%, #1a202c 50%, #0d1117 100%)',
          boxShadow:
            '0 25px 50px -12px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255,255,255,0.05), inset 0 1px 0 rgba(255,255,255,0.1), inset 0 -1px 0 rgba(0,0,0,0.3)',
        }}
      >
        {/* 手机边框内光效 */}
        <div
          className='absolute inset-0 rounded-[2.5rem] pointer-events-none'
          style={{
            background:
              'linear-gradient(135deg, rgba(255,255,255,0.08) 0%, transparent 40%, transparent 60%, rgba(0,0,0,0.2) 100%)',
            borderRadius: '2.5rem',
          }}
        />

        {/* 手机屏幕 */}
        <div className='relative w-full h-full bg-gradient-to-b from-amber-50 to-orange-50 rounded-[2rem] overflow-hidden flex flex-col'>
          {/* 刘海 */}
          <div className='absolute top-0 left-1/2 -translate-x-1/2 w-24 h-5 bg-black rounded-b-xl z-20 flex items-center justify-center'>
            <div className='w-1.5 h-1.5 rounded-full bg-gray-700 ring-1 ring-gray-600' />
          </div>

          {/* 状态栏 */}
          <div className='relative z-10 h-10 bg-gradient-to-r from-amber-600 to-orange-600 flex items-center justify-between px-6 pt-1 flex-shrink-0'>
            <span className='text-white text-xs font-medium'>
              {formatPhoneTime(currentTime)}
            </span>
            <div className='flex items-center gap-1 text-white'>
              <Signal className='w-3 h-3' />
              <Wifi className='w-3 h-3' />
              <Battery className='w-3.5 h-3.5' />
            </div>
          </div>

          {/* App 标题栏 */}
          <div className='bg-gradient-to-r from-amber-600 to-orange-600 px-4 pb-2 pt-0.5 flex-shrink-0'>
            <h2 className='text-white text-base font-bold flex items-center gap-2'>
              寒小艾智能助手
            </h2>
            <p className='text-amber-100 text-[10px]'>
              函数计算 AI 助手，帮助您完成一切工作
            </p>
          </div>

          {/* 消息区域 */}
          <div className='flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin'>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                } animate-fade-in`}
              >
                <div
                  className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm ${
                    message.role === 'user'
                      ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-br-sm'
                      : 'bg-white shadow-sm border border-amber-100 rounded-bl-sm'
                  }`}
                >
                  {message.role === 'assistant' ? (
                    <div className='prose prose-sm max-w-none text-gray-700 [&>*]:my-0.5 [&>ul]:pl-4 [&>ol]:pl-4 [&>p]:text-sm [&>ul]:text-sm'>
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                      {message.isStreaming && (
                        <span className='inline-block w-1.5 h-4 bg-amber-500 animate-pulse ml-0.5' />
                      )}
                    </div>
                  ) : (
                    <p className='whitespace-pre-wrap text-sm'>
                      {message.content}
                    </p>
                  )}

                  {/* 工具调用显示 */}
                  {message.toolCalls && renderToolCalls(message.toolCalls)}

                  {/* Agent 转移显示 */}
                  {message.agentTransfers &&
                    renderAgentTransfers(message.agentTransfers)}

                  {/* A2A 调用显示 */}
                  {message.a2aCalls && renderA2ACalls(message.a2aCalls)}

                  <div
                    className={`text-[9px] mt-1 ${
                      message.role === 'user'
                        ? 'text-amber-100'
                        : 'text-gray-400'
                    }`}
                  >
                    {message.timestamp.toLocaleTimeString('zh-CN', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && !messages[messages.length - 1]?.isStreaming && (
              <div className='flex justify-start animate-fade-in'>
                <div className='bg-white shadow-sm border border-amber-100 rounded-2xl rounded-bl-sm px-3 py-2'>
                  <div className='flex items-center space-x-1.5 text-amber-600'>
                    <Loader2 className='w-3 h-3 animate-spin' />
                    <span className='text-xs'>
                      {currentStatus || '思考中...'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* 输入区域和快捷操作 */}
          <div className='bg-white border-t border-amber-100 flex-shrink-0'>
            {/* 快捷操作 */}
            <div className='px-2 pt-1.5 pb-1'>
              <div className='flex gap-1.5 overflow-x-auto scrollbar-none'>
                {quickActions.map((action, idx) => (
                  <button
                    key={idx}
                    type='button'
                    onClick={() => setInput(action.message)}
                    className='flex-shrink-0 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-[11px] font-medium hover:bg-amber-100 hover:border-amber-300 transition-all'
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 输入框 */}
            <form onSubmit={handleSubmit} className='px-2 pb-2 pt-1'>
              <div className='flex items-center gap-1.5'>
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder='输入消息...'
                  className='flex-1 h-8 px-3 text-gray-700 rounded-full border border-amber-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent bg-amber-50/50 placeholder-amber-400'
                />
                <button
                  type='submit'
                  disabled={!input.trim() || isLoading}
                  className='w-8 h-8 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 text-white flex items-center justify-center hover:from-amber-600 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md'
                >
                  {isLoading ? (
                    <Loader2 className='w-3.5 h-3.5 animate-spin' />
                  ) : (
                    <Send className='w-3.5 h-3.5' />
                  )}
                </button>
              </div>
            </form>

            {/* 底部指示条 */}
            <div className='flex justify-center pb-1'>
              <div className='w-24 h-1 bg-gray-300 rounded-full' />
            </div>
          </div>
        </div>
      </div>

      {/* 底部提示文字 - 在手机外框下方 */}
      <div className='mt-4 w-full px-4'>
        <p className='text-slate-500 text-sm text-center'>
          💡 试试说「我要一杯拿铁」或「帮我查一下订单」
        </p>
      </div>

      {/* 手机底部反光 */}
      <div className='absolute -bottom-4 left-1/2 -translate-x-1/2 w-48 h-4 bg-gradient-to-r from-transparent via-gray-400/20 to-transparent blur-sm' />
    </div>
  );
}
