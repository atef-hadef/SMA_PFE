import { useTheme } from '../../theme/useTheme'
import Icon from './Icon'

type ThemeToggleProps = {
  size?: number
  className?: string
}

function ThemeToggle({ size = 20, className }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Activer le mode clair' : 'Activer le mode sombre'}
      title={isDark ? 'Mode clair' : 'Mode sombre'}
      className={
        className ??
        'rounded-lg border border-transparent p-2 text-slate-400 transition hover:border-slate-700 hover:bg-slate-800/70 hover:text-slate-100'
      }
    >
      <Icon name={isDark ? 'sun' : 'moon'} size={size} />
    </button>
  )
}

export default ThemeToggle
