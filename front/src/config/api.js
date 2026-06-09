export const apiConfig = {
  baseURL: import.meta.env.VITE_BASE_URL || '',
  userBaseURL: import.meta.env.VITE_USER_BASE_URL || '',
  
  endpoints: {
    login: '/user/login/',
    logout: '/user/logout/',
    register: '/user/register/',
    profile: '/user/detail/',
    
    uploadFile: '/file/upload/',
    
    agentQuery: '/chat/agent/query/stream',
    agentQueryStream: '/chat/agent/query/stream',

    ragQuery: '/chat/rag/query',

    getSession: '/chat/session/',
    deleteSession: '/chat/session/',
    getAllSessions: '/chat/sessions',
    getUserSessions: '/chat/sessions',

    uploadSingleFile: '/knowledge/add/single',
    uploadMultipleFiles: '/knowledge/add/multiple',
    cleanVectors: '/knowledge/clean',

    reorderDocuments: '/chat/reorder'
  }
}
