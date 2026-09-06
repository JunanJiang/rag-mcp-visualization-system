import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import KBPanel from '../views/KBPanel.vue'
import OrganizationPanel from '../views/OrganizationPanel.vue'
import ProfilePanel from '../views/ProfilePanel.vue'
import ReportGeneratorV2 from '../views/ReportGeneratorV2.vue'
import AdminPanel from '../views/AdminPanel.vue'
import IntegrationEntry from '../views/IntegrationEntry.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { guest: true }
  },
  {
    path: '/integration-entry',
    name: 'IntegrationEntry',
    component: IntegrationEntry,
    meta: { guest: true, allowAuthenticatedGuest: true }
  },
  {
    path: '/',
    redirect: '/v2'
  },
  {
    path: '/v2',
    name: 'ReportGeneratorV2',
    component: ReportGeneratorV2,
    meta: { requiresAuth: true }
  },
  {
    path: '/kb',
    name: 'KBPanel',
    component: KBPanel,
    meta: { requiresAuth: true }
  },
  {
    path: '/orgs',
    name: 'OrganizationPanel',
    component: OrganizationPanel,
    meta: { requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'ProfilePanel',
    component: ProfilePanel,
    meta: { requiresAuth: true }
  },
  {
    path: '/admin',
    name: 'AdminPanel',
    component: AdminPanel,
    meta: { requiresAuth: true, roles: ['admin'] }
  },
  {
    path: '/dev-tools',
    redirect: '/admin'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：未登录重定向到登录页 + 角色权限检查
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.meta.guest && token && !to.meta.allowAuthenticatedGuest) {
    next('/v2')
  } else if (to.meta.roles) {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      if (to.meta.roles.includes(user.role)) {
        next()
      } else {
        next('/v2')
      }
    } catch { next('/v2') }
  } else {
    next()
  }
})

export default router
