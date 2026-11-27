import { Info, Mail } from 'lucide-react'
import { Link } from 'react-router-dom'
import Brand from './Brand'

export default function PublicHeader({ showBrand = true }: { showBrand?: boolean }) {
  return (
    <>
      {showBrand && <Link to="/login" className="login-header__brand"><Brand /></Link>}
      <nav aria-label="Public navigation" className="public-nav">
        <Link to="/about"><Info size={16} aria-hidden="true" />About</Link>
        <span className="public-nav__disabled" aria-disabled="true" title="Contact is not available yet">
          <Mail size={16} aria-hidden="true" />Contact
        </span>
      </nav>
    </>
  )
}
