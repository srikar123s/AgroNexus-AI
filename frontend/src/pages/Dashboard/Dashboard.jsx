import { Link } from 'react-router-dom'
import './Dashboard.css'

function Dashboard() {
  return (
    <div className="dashboard">

      <div className="dashboard-header">
        <h1>Good evening, Farmer 👋</h1>

        <p>
          Here's an overview of your farm and current conditions.
        </p>
      </div>

      <div className="dashboard-stats">

        <div className="stat-card">
          <div className="stat-icon">🌱</div>

          <p className="stat-label">
            Current Crop
          </p>

          <p className="stat-value">
            Tomato
          </p>

          <p className="stat-detail">
            Flowering stage
          </p>
        </div>

        <div className="stat-card">
          <div className="stat-icon">❤️</div>

          <p className="stat-label">
            Crop Health
          </p>

          <p className="stat-value">
            Needs Attention
          </p>

          <p className="stat-detail">
            Early blight detected
          </p>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🌧️</div>

          <p className="stat-label">
            Weather
          </p>

          <p className="stat-value">
            29°C
          </p>

          <p className="stat-detail">
            Rain probability: 82%
          </p>
        </div>

      </div>

      <div className="farm-card">

        <div className="farm-card-header">

          <div>
            <h2>Current Farm</h2>

            <p>
              Tomato Farm • Flowering stage
            </p>
          </div>

          <Link to="/farm">
            <button className="primary-button">
              View Farm
            </button>
          </Link>

        </div>

        <div className="weather-warning">
          🌧️ Heavy rainfall is expected. This condition
          will be considered during the agricultural decision.
        </div>

        <div style={{ marginTop: '22px' }}>

          <Link to="/farm">
            <button className="primary-button">
              Start New Analysis
            </button>
          </Link>

        </div>

      </div>

      <div className="decision-card">

        <h2>Recent Decision</h2>

        <p className="decision-action">
          Treatment B
        </p>

        <p>
          Recommended based on current disease,
          weather, resources, and farm context.
        </p>

        <p className="decision-outcome">
          Expected outcome: 80%
        </p>

      </div>

    </div>
  )
}

export default Dashboard