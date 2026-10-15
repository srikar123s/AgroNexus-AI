import { useNavigate } from 'react-router-dom'
import './Recommendation.css'

function Recommendation() {
  const navigate = useNavigate()

  const reasons = [
    'The detected crop condition indicates that intervention is required.',
    'Heavy rainfall is expected and has been considered when evaluating the action.',
    'The recommendation is compatible with the current farm context.',
    'The available resources and budget constraints have been considered.',
    'Relevant agricultural evidence supports this intervention.',
  ]

  return (
    <div className="recommendation-page">

      <div className="recommendation-header">
        <h1>Recommended Action</h1>

        <p>
          AgroNexus evaluated the available evidence and current
          farm context to identify a suitable intervention.
        </p>
      </div>

      <div className="recommendation-card">

        <div className="recommendation-top">

          <div>
            <p className="recommendation-label">
              Recommended intervention
            </p>

            <h2 className="recommendation-action">
              Treatment B
            </h2>
          </div>

          <div className="outcome-box">

            <p className="outcome-value">
              80%
            </p>

            <p className="outcome-label">
              Expected Outcome
            </p>

          </div>

        </div>

        <div className="section">

          <h2>
            Why was this action selected?
          </h2>

          <div className="reasons">

            {reasons.map((reason, index) => (
              <div
                className="reason"
                key={index}
              >
                <span className="reason-icon">
                  ✓
                </span>

                <p>
                  {reason}
                </p>
              </div>
            ))}

          </div>

        </div>

        <div className="section">

          <h2>
            Decision Context
          </h2>

          <div className="context-grid">

            <div className="context-item">
              <p className="context-label">
                Crop
              </p>

              <p className="context-value">
                Tomato
              </p>
            </div>

            <div className="context-item">
              <p className="context-label">
                Condition
              </p>

              <p className="context-value">
                Early Blight
              </p>
            </div>

            <div className="context-item">
              <p className="context-label">
                Growth Stage
              </p>

              <p className="context-value">
                Flowering
              </p>
            </div>

            <div className="context-item">
              <p className="context-label">
                Weather
              </p>

              <p className="context-value">
                Heavy Rain
              </p>
            </div>

          </div>

        </div>

      </div>

      <div className="recommendation-actions">

        <button
          className="recommendation-button"
          onClick={() => navigate('/alternatives')}
        >
          View Alternative Actions →
        </button>

      </div>

    </div>
  )
}

export default Recommendation