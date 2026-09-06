export function getUserPresentation(user) {
  const rawId = user?.id ?? ''
  const username = String(user?.username || '').trim()
  const displayName = String(user?.display_name || '').trim()

  return {
    displayId: rawId === '' ? '' : `U-${String(rawId).padStart(3, '0')}`,
    displayUsername: username,
    displayName: displayName || username,
    displayTitle: displayName || username || '用户'
  }
}
