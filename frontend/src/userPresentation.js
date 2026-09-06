const RESERVED_USERNAMES = new Set(['admin', '111'])

const ALIAS_PROFILES = [
  { username: 'wanglei', name: '王磊' },
  { username: 'chenyu', name: '陈宇' },
  { username: 'liuyang', name: '刘洋' },
  { username: 'zhaomin', name: '赵敏' },
  { username: 'sunhao', name: '孙浩' },
  { username: 'zhouyan', name: '周妍' },
  { username: 'wujie', name: '吴杰' },
  { username: 'xuruo', name: '徐若' },
  { username: 'heting', name: '何婷' },
  { username: 'guorui', name: '郭睿' },
  { username: 'tangyuan', name: '唐源' },
  { username: 'lujia', name: '陆嘉' },
  { username: 'pengfei', name: '彭飞' },
  { username: 'yaonan', name: '姚楠' },
  { username: 'jiangxin', name: '蒋欣' },
  { username: 'shihan', name: '石涵' },
  { username: 'linyue', name: '林月' },
  { username: 'gaohan', name: '高涵' },
  { username: 'duanqi', name: '段琪' },
  { username: 'songchen', name: '宋辰' }
]

function hashText(value) {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = value.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash)
}

function isSyntheticUser(user) {
  const username = String(user?.username || '').trim()
  const displayName = String(user?.display_name || '').trim()
  if (!username || RESERVED_USERNAMES.has(username)) return false
  return /^testuser(?:_|-)/i.test(username) || /^测试用户/.test(displayName)
}

function getAliasProfile(user) {
  const username = String(user?.username || '')
  const numericSeed = Number.isFinite(Number(user?.id)) ? Number(user.id) : hashText(username)
  const index = numericSeed % ALIAS_PROFILES.length
  const cycle = Math.floor(numericSeed / ALIAS_PROFILES.length)
  const profile = ALIAS_PROFILES[index]
  return {
    username: cycle > 0 ? `${profile.username}${cycle}` : profile.username,
    name: profile.name
  }
}

export function getUserPresentation(user) {
  const rawId = user?.id ?? ''
  const rawUsername = String(user?.username || '').trim()
  const rawDisplayName = String(user?.display_name || '').trim()

  if (!rawUsername) {
    return {
      displayId: rawId,
      displayUsername: rawUsername,
      displayName: rawDisplayName,
      displayTitle: rawDisplayName || rawUsername || '用户'
    }
  }

  if (RESERVED_USERNAMES.has(rawUsername)) {
    return {
      displayId: rawId,
      displayUsername: rawUsername,
      displayName: rawDisplayName || rawUsername,
      displayTitle: rawUsername
    }
  }

  if (rawUsername === 'zhangwei') {
    return {
      displayId: `U-${String(rawId).padStart(3, '0')}`,
      displayUsername: 'zhangwei',
      displayName: '张伟',
      displayTitle: '张伟'
    }
  }

  if (rawUsername === 'liuming') {
    return {
      displayId: `U-${String(rawId).padStart(3, '0')}`,
      displayUsername: 'liuming',
      displayName: '刘明',
      displayTitle: '刘明'
    }
  }

  if (isSyntheticUser(user)) {
    const alias = getAliasProfile(user)
    return {
      displayId: `U-${String(rawId).padStart(3, '0')}`,
      displayUsername: alias.username,
      displayName: alias.name,
      displayTitle: alias.name
    }
  }

  return {
    displayId: `U-${String(rawId).padStart(3, '0')}`,
    displayUsername: rawUsername,
    displayName: rawDisplayName || rawUsername,
    displayTitle: rawDisplayName || rawUsername
  }
}
