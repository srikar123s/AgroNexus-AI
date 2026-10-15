import { NavLink, Outlet } from 'react-router-dom'
import './MainLayout.css'

function MainLayout() {
  return (
    <div className="app-layout">

      <header className="topbar">

        <div className="brand">
          <div className="brand-icon">🌱</div>

          <div>
            <h1 className="brand-name">AgroNexus AI</h1>
            <p className="brand-subtitle">
              Intelligent Farm Advisor
            </p>
          </div>
        </div>

        <div className="user-profile">
          <div>
            <strong>Farmer</strong>
          </div>

          <div className="user-avatar">
            F
          </div>
        </div>

      </header>

      <div className="app-body">

        <aside className="sidebar">

          <div className="sidebar-title">
            Navigation
          </div>

          <nav className="sidebar-nav">

            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              🏠 Dashboard
            </NavLink>

            <NavLink
              to="/farm"
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              🌾 My Farm
            </NavLink>

            <NavLink
              to="/crop"
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              🌱 Crop
            </NavLink>

            <NavLink
              to="/image"
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              📷 Crop Image
            </NavLink>

            <NavLink
              to="/analysis"
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              🔬 Analysis
            </NavLink>

            <NavLink
              to="/recommendation"
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              🧠 Recommendation
            </NavLink>

            <NavLink
              to="/alternatives"
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              ⚖️ Alternatives
            </NavLink>

            <NavLink
              to="/feedback"
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              📝 Feedback
            </NavLink>

            <NavLink
              to="/adaptive-update"
              className={({ isActive }) =>
                isActive ? 'nav-link active' : 'nav-link'
              }
            >
              🔄 Adaptive Update
            </NavLink>

          </nav>

        </aside>

        <main className="main-content">
          <Outlet />
        </main>

      </div>

    </div>
  )
}

export default MainLayout