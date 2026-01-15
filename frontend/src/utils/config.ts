// 后端 API 地址配置
// 默认使用本地后端，可以通过环境变量覆盖
// 如果通过本机 IP 访问，自动使用相同的 hostname 和端口 8000
function getBackendUrl(): string {
  // 优先使用环境变量
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL;
  }
  
  // 如果当前访问的不是 localhost，使用相同的 hostname
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      return `http://${hostname}:8000`;
    }
  }
  
  // 默认使用 localhost
  return 'http://localhost:8000';
}

export const ENDPOINT = getBackendUrl();

// API 端点
export const API_BASE_URL = ENDPOINT;
export const CHAT_API_URL = `${API_BASE_URL}/api/chat/stream`;
export const COPILOTKIT_API_URL = `${API_BASE_URL}/api/copilotkit`;
