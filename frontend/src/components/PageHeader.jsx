/** Page header used by every route: title, description and right-aligned actions. */

export default function PageHeader({ title, subtitle, actions, children }) {
  return (
    <div className="page-head">
      <div className="page-head__title">
        <h1>{title}</h1>
        {subtitle && <p className="page-head__sub">{subtitle}</p>}
        {children}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}
