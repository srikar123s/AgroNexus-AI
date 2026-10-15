import { useNavigate } from 'react-router-dom'
import './AdaptiveUpdate.css'

function AdaptiveUpdate() {
  const navigate = useNavigate()

  const expectedOutcome = 80
  const observedOutcome = 45
  const deviation = observedOutcome - expectedOutcome

  return (
    <div className="adaptive-page">

      <div className="adaptive-header">
        <h1>Adaptive Update</h1>

        <p>
          The observed farm outcome has been recorded and
          incorporated into the AgroNexus learning process.
        </p>
      </div>

      <div className="outcome-summary">

        <div className="outcome-card expected">

          <p className="outcome-label">
            Expected Outcome
          </p>

          <p className="outcome-number">
            {expectedOutcome}%
          </p>

          <p className="outcome-description">
            Predicted before the intervention
          </p>

        </div>

        <div className="outcome-arrow">
          →
        </div>

        <div className="outcome-card observed">

          <p className="outcome-label">
            Observed Outcome
          </p>

          <p className="outcome-number">
            {observedOutcome}%
          </p>

          <p className="outcome-description">
            Reported after the intervention
          </p>

        </div>

      </div>

      <div className="deviation-card">

        <p className="deviation-label">
          Difference
        </p>

        <p className="deviation-value">
          {deviation} percentage points
        </p>

      </div>

      <div className="update-card">

        <div className="update-header">

          <div className="update-icon">
            🔄
          </div>

          <h2>
            System Update
          </h2>

        </div>

        <p>
          The observed outcome has been recorded. AgroNexus
          can use this experience when evaluating similar
          agricultural situations in future decisions.
        </p>

      </div>

      <div className="context-card">

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

          <div className="context-item">
            <p className="context-label">
              Action
            </p>

            <p className="context-value">
              Treatment B
            </p>
          </div>

          <div className="context-item">
            <p className="context-label">
              Observed Effectiveness
            </p>

            <p className="context-value">
              {observedOutcome}%
            </p>
          </div>

        </div>

      </div>

      <div className="adaptive-actions">

        <button
          className="adaptive-button"
          onClick={() => navigate('/')}
        >
          Return to Dashboard
        </button>

      </div>

    </div>
  )
}

export default AdaptiveUpdate