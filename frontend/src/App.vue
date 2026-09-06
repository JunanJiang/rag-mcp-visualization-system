<template>
  <!-- 登录页：不显示导航框架 -->
  <router-view v-if="isPlainRoute" />

  <!-- 主应用框架 -->
  <div v-else class="app-container">
    <!-- 顶部栏 -->
    <header class="app-header">
      <div class="header-left">
        <div class="logo" @click="goHome">
          <div class="logo-icon">
            <el-icon :size="15"><DataAnalysis /></el-icon>
          </div>
          <span class="logo-text">SimuReport</span>
        </div>
        <div class="header-sep"></div>
        <nav class="nav-tabs">
          <button
            class="nav-tab"
            :class="{ active: route.path === '/v2' || route.path === '/' }"
            @click="router.push('/v2')"
          >报告生成</button>
          <button
            class="nav-tab"
            :class="{ active: route.path === '/kb' }"
            @click="router.push('/kb')"
          >知识库</button>
          <button
            class="nav-tab"
            :class="{ active: route.path === '/orgs' }"
            @click="router.push('/orgs')"
          >组织</button>
          <button
            v-if="isAdmin"
            class="nav-tab"
            :class="{ active: route.path === '/admin' }"
            @click="router.push('/admin')"
          >管理中心</button>
        </nav>
      </div>
      <div class="header-right">
        <el-dropdown trigger="click" @command="handleUserCommand">
          <div class="user-trigger">
            <div class="user-avatar" :style="{ background: userAvatarColor }">{{ userAvatarLetter }}</div>
            <span class="user-display-name">{{ displayName }}</span>
            <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled class="dropdown-user-info">
                <div class="dropdown-user-role">
                  <span>{{ displayName }}</span>
                  <el-tag :type="userRole === 'admin' ? 'warning' : ''" size="small" effect="plain">{{ roleLabel }}</el-tag>
                </div>
              </el-dropdown-item>
              <el-dropdown-item divided command="profile">
                <el-icon><User /></el-icon> 个人信息
              </el-dropdown-item>
              <el-dropdown-item command="logout">
                <el-icon><SwitchButton /></el-icon> 退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <!-- 主体：左侧AI面板 + 右侧内容 -->
    <div class="app-body">
      <AiChatPanel @workflow-action="onWorkflowAction" />
      <main class="app-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { provide, ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { DataAnalysis, ArrowDown, User, SwitchButton } from '@element-plus/icons-vue'
import AiChatPanel from './components/AiChatPanel.vue'
import { getUserPresentation } from './userPresentation'

const router = useRouter()
const route = useRoute()

// AI 密钥已由管理员在后端统一管理，前端不再注入也不再传递凭证
const workflowEvent = ref(null)
provide('workflowEvent', workflowEvent)

const isPlainRoute = computed(() => ['/login', '/integration-entry'].includes(route.path))

// 当前用户信息 —— 用 ref 存储，路由变化时重新读取 localStorage
// （computed 对 localStorage 无响应性，必须用 ref + watch 手动刷新）
const currentUser = ref(null)

function _refreshUser() {
  try {
    const raw = localStorage.getItem('user')
    currentUser.value = raw ? JSON.parse(raw) : null
  } catch { currentUser.value = null }
}

// 路由切换时刷新（登录后 router.push('/v2') 会触发）
watch(route, () => { _refreshUser() }, { immediate: true })

// 监听其他标签页登录/退出
window.addEventListener('storage', _refreshUser)

const userRole = computed(() => currentUser.value?.role || 'user')
const isAdmin = computed(() => userRole.value === 'admin')
const roleLabel = computed(() => {
  const map = { user: '用户', admin: '管理员' }
  return map[userRole.value] || '用户'
})
const presentedCurrentUser = computed(() => getUserPresentation(currentUser.value || {}))
const displayName = computed(() => presentedCurrentUser.value.displayTitle || currentUser.value?.username || '用户')
const userAvatarLetter = computed(() => {
  const name = displayName.value
  return name.charAt(0).toUpperCase()
})
const userAvatarColor = computed(() => {
  const colors = ['#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899']
  const name = currentUser.value?.username || ''
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return colors[Math.abs(hash) % colors.length]
})

function onWorkflowAction(event) {
  workflowEvent.value = { ...event, timestamp: Date.now() }
}

function handleUserCommand(cmd) {
  if (cmd === 'profile') router.push('/profile')
  else if (cmd === 'logout') handleLogout()
}

function handleLogout() {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

function goHome() {
  // 跳转到报告生成页并重置到模式选择
  router.push({ path: '/v2', query: { reset: '1' } })
}
</script>

<style scoped>
.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--c-bg-page);
}

/* ── 顶部栏：48px，干净 ── */
.app-header {
  height: 48px;
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-4);
  background: var(--c-bg-card);
  border-bottom: 1px solid var(--c-border);
  flex-shrink: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  cursor: pointer;
  padding: var(--sp-1) var(--sp-2);
  border-radius: var(--radius-md);
  transition: background var(--duration-fast) var(--ease-default);
}
.logo:hover { background: var(--c-gray-100); }

.logo-icon {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: var(--c-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-text {
  font-size: var(--text-md);
  font-weight: 700;
  color: var(--c-text-1);
  letter-spacing: -0.3px;
}

.header-sep {
  width: 1px;
  height: 18px;
  background: var(--c-border);
}

.nav-tabs {
  display: flex;
  gap: 2px;
  min-width: 0;
}

.nav-tab {
  padding: 5px var(--sp-3);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--c-text-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.nav-tab:hover {
  color: var(--c-text-1);
  background: var(--c-gray-100);
}
.nav-tab.active {
  color: var(--c-primary);
  background: var(--c-primary-light);
}

.logo:focus-visible,
.nav-tab:focus-visible {
  outline: 2px solid var(--c-primary);
  outline-offset: 1px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 10px 4px 4px;
  border-radius: var(--radius-md);
  transition: background var(--duration-fast) var(--ease-default);
}
.user-trigger:hover {
  background: var(--c-gray-100);
}

.user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.user-display-name {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--c-text-1);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-arrow {
  font-size: 12px;
  color: var(--c-text-3);
  transition: transform .2s;
}

.dropdown-user-info {
  cursor: default !important;
}

.dropdown-user-role {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--c-text-1);
}
.dev-tab {
  color: #7c3aed !important;
}
.dev-tab.active {
  color: #7c3aed !important;
  background: #f5f3ff !important;
}

/* ── 主体 ── */
.app-body {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  min-height: 0;
}

.app-main {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
  background: var(--c-bg-page);
}

@media (max-width: 900px) {
  .app-header {
    height: auto;
    min-height: 56px;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: var(--sp-2);
    padding: var(--sp-2) var(--sp-3);
  }

  .header-left {
    width: 100%;
    min-width: 0;
    gap: var(--sp-2);
  }

  .header-sep {
    display: none;
  }

  .nav-tabs {
    flex: 1;
    overflow-x: auto;
    white-space: nowrap;
    scrollbar-width: none;
    padding-bottom: 2px;
  }

  .nav-tabs::-webkit-scrollbar {
    display: none;
  }

  .nav-tab {
    flex: 0 0 auto;
    white-space: nowrap;
    font-size: var(--text-sm);
    padding: 6px var(--sp-2);
  }

  .header-right {
    margin-left: auto;
  }

  .app-body {
    flex-direction: column;
    overflow-y: auto;
  }

  .app-main {
    min-height: 0;
  }
}

@media (max-width: 640px) {
  .logo-text {
    display: none;
  }

  .user-display-name {
    display: none;
  }
}
</style>
