/** Application shell: sidebar + topbar + routed content. */

import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import { useApiHealth } from '../../hooks/useApiHealth'

export default function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  const health = useApiHealth()

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setMenuOpen(false), [pathname])

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />
      {menuOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMenuOpen(false)}
          role="presentation"
        />
      )}
      <div className="app-main">
        <Topbar health={health} onMenu={() => setMenuOpen((v) => !v)} />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
