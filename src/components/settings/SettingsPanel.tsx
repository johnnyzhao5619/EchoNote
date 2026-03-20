import { Link } from '@tanstack/react-router'

export function SettingsPanel() {
  const navItems = [
    { to: '/settings' as const,        label: 'General' },
    { to: '/settings/models' as const, label: 'Models' },
    { to: '/settings/theme' as const,  label: 'Theme' },
  ]

  return (
    <nav className="flex flex-col gap-1 p-2">
      {navItems.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className="rounded px-3 py-1.5 text-sm transition-colors text-text-secondary hover:bg-bg-hover hover:text-text-primary"
          activeProps={{ className: 'rounded px-3 py-1.5 text-sm transition-colors bg-accent text-white' }}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  )
}
