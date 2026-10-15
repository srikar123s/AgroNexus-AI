import { useNavigate } from 'react-router-dom'
import './Alternatives.css'

function Alternatives() {
  const navigate = useNavigate()

  const actions = [
    {
      name: 'Treatment A',
      status: 'Less Suitable',
      reason:
        'Reduced suitability under the current heavy rainfall conditions.',
      recommended: false,
    },
    {
      name: 'Treatment B',
      status: '✓ Recommended',
      reason:
        'Best overall fit for the current disease, weather, farm context, and resource constraints.',
      outcome: 'Expected outcome: 80%',
      recommended: true,
    },
    {
      name: 'Treatment C',
      status: 'Less Suitable',
      reason:
        'Requires more resources than are currently available on the farm.',
      recommended: false,
    },
  ]

  return (
    <div className="alternatives-page">

      <div className="alternatives-header">
        <h1>Alternative Actions</h1>

        <p>
          These are the other interventions considered during
          the decision process.
        </p>
      </div>

      <div className="actions-list">

        {actions.map((action) => (
          <div
            key={action.name}
            className={`action-card ${
              action.recommended ? 'recommended' : ''
            }`}
          >

            <div className="action-header">

              <h2 className="action-name">
                {action.name}
              </h2>

              <span className="action-status">
                {action.status}
              </span>

            </div>

            <p className="action-reason">
              {action.reason}
            </p>

            {action.outcome && (
              <p className="action-outcome">
                {action.outcome}
              </p>
            )}

          </div>
        ))}

      </div>

      <div className="alternatives-actions">

        <button
          className="alternatives-button"
          onClick={() => navigate('/feedback')}
        >
          Record Outcome →
        </button>

      </div>

    </div>
  )
}

export default Alternatives