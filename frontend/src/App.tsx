import { useState, useEffect } from 'react';
import { CopilotKit } from '@copilotkit/react-core';
import '@copilotkit/react-ui/styles.css';
import PhoneSimulator from './components/PhoneSimulator';
import AdminPanel from './components/AdminPanel';
import ErrorBoundary from './components/ErrorBoundary';
import { Coffee, Truck, X, Bot } from 'lucide-react';
import { ENDPOINT } from './utils/config';

// Agent Card 类型
interface AgentCard {
  name: string;
  description: string;
  protocolVersion: string;
  url?: string;
  skills?: Array<{
    id: string;
    name: string;
    description: string;
    tags?: string[];
  }>;
  capabilities?: Record<string, unknown>;
  defaultInputModes?: string[];
  defaultOutputModes?: string[];
}

// Agent 信息类型（从 /api/agents 返回）
interface AgentInfo {
  name: string;
  description: string;
  url: string;
  icon: string;
  card: AgentCard | null;
  error?: string;
}

// 根据 Agent 名称获取图标组件
function getAgentIcon(name: string) {
  const nameLower = name.toLowerCase();
  if (nameLower.includes('coffee') || nameLower.includes('咖啡')) {
    return <Coffee className='w-5 h-5 text-white' />;
  } else if (nameLower.includes('delivery') || nameLower.includes('配送')) {
    return <Truck className='w-5 h-5 text-white' />;
  }
  return <Bot className='w-5 h-5 text-white' />;
}

// 根据 Agent 名称获取颜色
function getAgentColor(name: string) {
  const nameLower = name.toLowerCase();
  if (nameLower.includes('coffee') || nameLower.includes('咖啡')) {
    return {
      bg: 'bg-gradient-to-r from-amber-600 to-orange-600',
      button: 'bg-amber-500/10 hover:bg-amber-500/20 border-amber-500/30',
      dot: 'bg-amber-400',
      text: 'text-amber-400',
    };
  } else if (nameLower.includes('delivery') || nameLower.includes('配送')) {
    return {
      bg: 'bg-gradient-to-r from-purple-600 to-indigo-600',
      button: 'bg-purple-500/10 hover:bg-purple-500/20 border-purple-500/30',
      dot: 'bg-purple-400',
      text: 'text-purple-400',
    };
  }
  return {
    bg: 'bg-gradient-to-r from-blue-600 to-cyan-600',
    button: 'bg-blue-500/10 hover:bg-blue-500/20 border-blue-500/30',
    dot: 'bg-blue-400',
    text: 'text-blue-400',
  };
}

// 获取 Agent 显示名称
function getAgentDisplayName(name: string) {
  const nameLower = name.toLowerCase();
  if (nameLower.includes('coffee') || nameLower.includes('咖啡')) {
    return '咖啡 Agent';
  } else if (nameLower.includes('delivery') || nameLower.includes('配送')) {
    return '配送 Agent';
  }
  return name;
}

// Agent Card 弹窗组件
function AgentCardModal({
  agent,
  onClose,
}: {
  agent: AgentInfo;
  onClose: () => void;
}) {
  const agentCard = agent.card;
  const color = getAgentColor(agent.name);
  const displayName = getAgentDisplayName(agent.name);

  return (
    <div
      className='fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm'
      onClick={onClose}
    >
      <div
        className='bg-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden border border-slate-700'
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div
          className={`px-6 py-4 border-b border-slate-700 flex items-center justify-between ${color.bg}`}
        >
          <div className='flex items-center gap-3'>
            <div className='w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center'>
              {getAgentIcon(agent.name)}
            </div>
            <div>
              <h2 className='text-lg font-bold text-white'>{displayName}</h2>
              <p className='text-white/70 text-sm'>A2A Agent Card</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className='w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-white transition-colors'
          >
            <X className='w-5 h-5' />
          </button>
        </div>

        {/* 内容 */}
        <div className='p-6 overflow-y-auto max-h-[60vh]'>
          {agent.error ? (
            <div className='bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400'>
              <p className='font-medium'>无法获取 Agent Card</p>
              <p className='text-sm mt-1'>{agent.error}</p>
              <p className='text-xs mt-2 text-red-400/70'>URL: {agent.url}</p>
            </div>
          ) : agentCard ? (
            <div className='space-y-4'>
              {/* 基本信息 */}
              <div>
                <h3 className='text-slate-400 text-xs uppercase tracking-wider mb-2'>
                  基本信息
                </h3>
                <div className='bg-slate-900/50 rounded-xl p-4 space-y-3'>
                  <div className='flex justify-between'>
                    <span className='text-slate-400'>名称</span>
                    <span className='text-white font-medium'>
                      {agentCard.name}
                    </span>
                  </div>
                  <div className='flex justify-between'>
                    <span className='text-slate-400'>协议版本</span>
                    <span className='text-white font-mono text-sm'>
                      {agentCard.protocolVersion}
                    </span>
                  </div>
                  <div className='flex justify-between'>
                    <span className='text-slate-400'>URL</span>
                    <span className='text-white font-mono text-xs truncate max-w-[300px]'>
                      {agent.url}
                    </span>
                  </div>
                  <div>
                    <span className='text-slate-400 block mb-1'>描述</span>
                    <span className='text-white text-sm'>
                      {agentCard.description}
                    </span>
                  </div>
                </div>
              </div>

              {/* 输入输出模式 */}
              <div>
                <h3 className='text-slate-400 text-xs uppercase tracking-wider mb-2'>
                  支持的模式
                </h3>
                <div className='bg-slate-900/50 rounded-xl p-4 flex gap-4'>
                  <div>
                    <span className='text-slate-400 text-xs'>输入</span>
                    <div className='flex gap-1 mt-1'>
                      {agentCard.defaultInputModes?.map((mode, i) => (
                        <span
                          key={i}
                          className='px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs'
                        >
                          {mode}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className='text-slate-400 text-xs'>输出</span>
                    <div className='flex gap-1 mt-1'>
                      {agentCard.defaultOutputModes?.map((mode, i) => (
                        <span
                          key={i}
                          className='px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs'
                        >
                          {mode}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Skills */}
              {agentCard.skills && agentCard.skills.length > 0 && (
                <div>
                  <h3 className='text-slate-400 text-xs uppercase tracking-wider mb-2'>
                    技能列表 ({agentCard.skills.length})
                  </h3>
                  <div className='space-y-2 max-h-64 overflow-y-auto'>
                    {agentCard.skills.map((skill, idx) => (
                      <div key={idx} className='bg-slate-900/50 rounded-xl p-3'>
                        <div className='flex items-center gap-2 mb-1'>
                          <span className='text-white font-medium text-sm'>
                            {skill.name}
                          </span>
                          {skill.tags?.map((tag, i) => (
                            <span
                              key={i}
                              className='px-1.5 py-0.5 bg-slate-700 text-slate-300 rounded text-[10px]'
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                        <p className='text-slate-400 text-xs line-clamp-2'>
                          {skill.description.slice(0, 150)}
                          {skill.description.length > 150 ? '...' : ''}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className='text-slate-400 text-center py-8'>
              正在加载 Agent Card...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentInfo | null>(null);
  const [agentsLoading, setAgentsLoading] = useState(true);

  // 从 /api/agents 获取 Agent 列表
  useEffect(() => {
    setAgentsLoading(true);
    fetch(`${ENDPOINT}/api/agents`)
      .then((res) => res.json())
      .then((data) => {
        if (data.success && data.agents) {
          setAgents(data.agents);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch agents:', err);
      })
      .finally(() => {
        setAgentsLoading(false);
      });
  }, []);

  const handleOrderCreated = () => {
    setRefreshKey((k) => k + 1);
  };

  // CopilotKit 直接可用（因为功能正常）
  const copilotKitReady = true;

  // 应用内容（不依赖 CopilotKit）
  const appContent = (
    <div className='h-screen flex flex-col overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900'>
        {/* 顶部标题栏 - 简化版 */}
        <header className='relative z-10 px-8 py-4 bg-gradient-to-r from-slate-900/80 to-slate-800/80 backdrop-blur-sm border-b border-slate-700/50'>
          <div className='flex items-center justify-between max-w-[1800px] mx-auto'>
            {/* Logo */}
            <div className='flex items-center gap-4'>
              <div className='relative'>
                <div className='w-12 h-12 bg-gradient-to-br from-amber-400 to-orange-500 rounded-xl flex items-center justify-center shadow-lg shadow-amber-500/20'>
                  <div
                    className='w-full h-full rounded-full'
                    style={{
                      backgroundImage: 'url(logo.png)',
                      backgroundSize: 'cover',
                    }}
                  />
                </div>
              </div>
              <div>
                <h1 className='text-2xl font-bold text-white tracking-tight'>
                  希希咖啡店
                </h1>
                <p className='text-slate-400 text-sm'>
                  多 Agent 咖啡点单与配送系统
                </p>
              </div>
            </div>

            {/* 右侧留空或放其他内容 */}
            <div className='text-slate-400 text-sm'>
              Powered by <b>ComputeNest</b> + Google ADK + A2A Protocol + AGUI +
              CopliotKit
            </div>
          </div>
        </header>

        {/* 主体内容 */}
        <main className='flex-1 flex overflow-hidden'>
          {/* 左侧 - 顾客端（手机模拟器） */}
          <div className='flex-1 flex flex-col items-center justify-center p-4 lg:p-8 relative'>
            {/* 背景装饰 */}
            <div className='absolute inset-0 overflow-hidden pointer-events-none'>
              <div className='absolute top-20 left-20 w-72 h-72 bg-amber-500/10 rounded-full blur-3xl' />
              <div className='absolute bottom-20 right-20 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl' />
            </div>

            {/* 标签 - 在手机上方 */}
            <div className='mb-3 flex items-center gap-3 relative z-20'>
              <div className='w-3 h-3 rounded-full bg-amber-400 animate-pulse' />
              <h2 className='text-lg font-semibold text-white'>顾客端</h2>
              <span className='text-slate-400 text-sm'>· 手机 App 模拟</span>
            </div>

            {/* 手机模拟器 */}
            <div className='relative z-10'>
              <PhoneSimulator onOrderCreated={handleOrderCreated} />
            </div>
          </div>

          {/* 中间分隔线 */}
          <div className='w-px bg-gradient-to-b from-transparent via-slate-600 to-transparent' />

          {/* 右侧 - 商家后台 */}
          <div className='w-[500px] xl:w-[580px] flex flex-col'>
            {/* 标签 - 确保在顶部可见 */}
            <div className='px-6 py-4 pt-6 flex items-center gap-3 border-b border-slate-700/50 relative z-20'>
              <div className='w-3 h-3 rounded-full bg-green-400 animate-pulse' />
              <h2 className='text-lg font-semibold text-white'>商家后台</h2>
              <span className='text-slate-400 text-sm'>· 订单管理系统</span>
            </div>

            {/* 后台面板 */}
            <div className='flex-1 overflow-hidden'>
              <AdminPanel
                refreshTrigger={refreshKey}
                onRefresh={() => setRefreshKey((k) => k + 1)}
              />
            </div>
          </div>
        </main>

        {/* 底部状态栏 */}
        <footer className='px-8 py-3 bg-slate-900/80 border-t border-slate-700/50'>
          <div className='flex items-center justify-between max-w-[1800px] mx-auto'>
            <div className='flex items-center gap-6'>
              <div className='flex items-center gap-2'>
                <div className='w-2 h-2 rounded-full bg-green-400 animate-pulse' />
                <span className='text-slate-400 text-sm'>
                  {agentsLoading
                    ? '正在加载 A2A 服务...'
                    : agents.length > 0
                      ? `${agents.length} 个 A2A 服务运行中`
                      : '无 A2A 服务'}
                </span>
              </div>

              {/* 动态渲染 Agent 按钮 */}
              {agents.map((agent, idx) => {
                const color = getAgentColor(agent.name);
                const displayName = getAgentDisplayName(agent.name);
                return (
                  <button
                    key={idx}
                    onClick={() => setSelectedAgent(agent)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-colors cursor-pointer ${color.button}`}
                  >
                    <div className={`w-2 h-2 rounded-full ${color.dot}`} />
                    <span className={`text-sm ${color.text}`}>
                      {displayName}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className='text-slate-500 text-xs'>A2A Protocol v0.3.0</div>
          </div>
        </footer>

        {/* Agent Card 弹窗 */}
        {selectedAgent && (
          <AgentCardModal
            agent={selectedAgent}
            onClose={() => setSelectedAgent(null)}
          />
        )}

      </div>
  );

  // 如果 CopilotKit 可用，包装在 CopilotKit 中；否则直接返回内容
  if (copilotKitReady) {
    return (
      <ErrorBoundary>
        <CopilotKit runtimeUrl={`${ENDPOINT}/api/copilotkit`}>
          {appContent}
        </CopilotKit>
      </ErrorBoundary>
    );
  }

  // 降级处理：即使 CopilotKit 不可用，也显示应用内容
  return <ErrorBoundary>{appContent}</ErrorBoundary>;
}

export default App;
