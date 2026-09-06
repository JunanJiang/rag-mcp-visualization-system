<template>
  <div class="integration-entry">
    <div class="entry-card">
      <div class="entry-badge">SimuReport</div>
      <h1>正在接入 SimuReport 网页端</h1>
      <p>正在同步登录态与数据包上下文，请稍候...</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

function decodeUser(raw) {
  if (!raw) return null
  try {
    return atob(String(raw))
  } catch {
    try {
      return decodeURIComponent(String(raw))
    } catch {
      return null
    }
  }
}

function decodeContext(raw) {
  if (!raw) return null
  try {
    const decoded = atob(String(raw))
    return JSON.parse(decoded)
  } catch {
    try {
      return JSON.parse(decodeURIComponent(String(raw)))
    } catch {
      return null
    }
  }
}

onMounted(() => {
  const token = route.query.token
  const encodedUser = route.query.user
  const encodedContext = route.query.context
  const redirectPath = typeof route.query.redirect === 'string' ? route.query.redirect : '/v2'

  if (token) {
    localStorage.setItem('token', String(token))
  }

  const user = decodeUser(encodedUser)
  if (user) {
    localStorage.setItem('user', user)
  }

  const context = decodeContext(encodedContext)
  if (context) {
    localStorage.setItem('integration_context', JSON.stringify(context))
  }

  if (!localStorage.getItem('token')) {
    router.replace('/login')
    return
  }

  router.replace({
    path: redirectPath,
    query: {
      resume: '1',
      source: 'integration-demo'
    }
  })
})
</script>

<style scoped>
.integration-entry {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 30%),
    radial-gradient(circle at bottom right, rgba(59, 130, 246, 0.1), transparent 30%),
    #f6f8fb;
}

.entry-card {
  width: min(520px, calc(100vw - 32px));
  padding: 40px 36px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 28px 60px rgba(15, 23, 42, 0.12);
  text-align: center;
}

.entry-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 18px;
}

h1 {
  margin: 0 0 10px;
  color: #0f172a;
  font-size: 28px;
  line-height: 1.2;
}

p {
  margin: 0;
  color: #475569;
  font-size: 15px;
}
</style>
