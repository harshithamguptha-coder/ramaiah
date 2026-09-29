/** Top bar: page context, backend health indicator and mobile menu toggle. */

import { useLocation } from 'react-router-dom'
import { NAV_SECTIONS } from '../../constants/navigation'
import Icon from '../ui/Icon'

const TITLES = NAV_SECTIONS.flatMap((s) => s.items).reduce((acc, item) => {
  acc[item.to] = item.label
  return acc
}, {})

export default function Topbar({ health, onMenu }) {
  const { pathname } = useLocation()
  const statusClass = {
    online: 'topbar__status--online',
    offline: 'topbar__status--offline',
    checking: '',
  }[health.status]

  return (
    <header className="topbar">
      <button className="menu-toggle" onClick={onMenu} aria-label="Toggle navigation">
        <Icon name="menu" size={18} />
      </button>

      <span className="topbar__title">{TITLES[pathname] || 'Q-Compass'}</span>

      <div className="spacer" />

      <span className={`topbar__status ${statusClass}`}>
        <span className="dot" />
        {health.status === 'online'
          ? `API online${health.version ? ` · v${health.version}` : ''}`
          : health.status === 'offline'
            ? 'API offline'
            : 'Checking API…'}
      </span>
    </header>
  )
}
