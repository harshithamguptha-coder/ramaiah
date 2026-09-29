/** Sidebar navigation. Highlights the active route and numbers the pipeline steps. */

import { NavLink } from 'react-router-dom'
import { NAV_SECTIONS } from '../../constants/navigation'
import Icon from '../ui/Icon'

export default function Sidebar({ open, onNavigate }) {
  return (
    <aside className={`sidebar${open ? ' is-open' : ''}`}>
      <div className="sidebar__brand">
        <div className="sidebar__logo">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="m15.5 8.5-2.1 4.9-4.9 2.1 2.1-4.9 4.9-2.1Z" fill="#fff" stroke="none" />
          </svg>
        </div>
        <div>
          <div className="sidebar__title">Q-Compass</div>
          <div className="sidebar__tagline">Quantum Readiness</div>
        </div>
      </div>

      <nav className="sidebar__nav" aria-label="Main navigation">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <div className="sidebar__section-label">{section.label}</div>
            {section.items.map((item) => (
              <NavLink
                key={item.key}
                to={item.to}
                end={item.to === '/'}
                onClick={onNavigate}
                className={({ isActive }) => `sidebar__link${isActive ? ' is-active' : ''}`}
              >
                <Icon name={item.icon} size={17} className="sidebar__icon" />
                <span>{item.label}</span>
                {item.step && <span className="sidebar__step">{item.step}</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar__footer">
        <span className="sidebar__mode">
          <span className="dot" />
          Prototype · mock analysis
        </span>
      </div>
    </aside>
  )
}
