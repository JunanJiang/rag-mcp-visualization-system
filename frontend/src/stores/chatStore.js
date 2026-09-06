/**
 * chatStore.js — 模块级单例
 * 将 AI 聊天 / 自动工作流的响应式状态提升到模块层，
 * 使流式任务在用户切换路由后仍然继续运行，
 * 返回页面时可无缝恢复显示。
 */
import { ref } from 'vue'

export const messages = ref([])
export const loading = ref(false)

export const autoRunning = ref(false)
export const autoProgress = ref(0)
export const autoProgressText = ref('')
export const autoMode = ref('')

/** 当前活跃的 AbortController（用于取消 in-flight 请求） */
let _activeAbortController = null

export function getAbortController() {
  return _activeAbortController
}

export function setAbortController(ctrl) {
  _activeAbortController = ctrl
}

/** 清空对话并中止当前请求 */
export function clearChatStore() {
  if (_activeAbortController) {
    _activeAbortController.abort()
    _activeAbortController = null
  }
  messages.value = []
  loading.value = false
  autoRunning.value = false
  autoProgress.value = 0
  autoProgressText.value = ''
  autoMode.value = ''
}
