import { useNavigate } from 'react-router-dom'
import './Analysis.css'

function Analysis() {
  const navigate = useNavigate()

  const evidence = [
    {
      icon: '🔬',
      source: 'Disease',
      value: 'Early Blight',
      detail: 'High confidence based on the submitted crop image.',
    },
    {
      icon: '🌧️',
      source: 'Weather',
      value: 'Heavy Rain Expected',
      detail: 'Rainfall conditions may affect the suitability of interventions.',
    },
    {
      icon: '🌱',
      source: 'Soil',
      value: 'Moderate Moisture',
      detail: 'Current soil condition should be considered during intervention selection.',
    },
    {
      icon: '📈',
      source: 'Yield Outlook',
      value: 'Moderate',
      detail: 'Current conditions indicate a moderate yield outlook.',
    },
    {
      icon: '📚',
      source: 'Agricultural Knowledge',
      value: 'Relevant Information Found',
      detail: 'Agricultural knowledge related to the current crop condition was identified.',
      wide: true,
    },
    {
      icon: '💰',
      source: 'Market',
      value: 'Cost Information Available',
      detail: 'Relevant treatment and input cost information is available.',
      wide: true,
    },
    {
      icon: '🏛️',
      source: 'Policy',
      value: 'Relevant Information Found',
      detail: 'Potentially relevant agricultural scheme and policy information is available.',
      wide: true,
    },
  ]

  return (
    <div className="analysis-page">

      <div className="analysis-header">
        <h1>Crop Analysis</h1>

        <p>
          Here's what AgroNexus found about your current
          farming situation.
        </p>
      </div>

      <div className="evidence-grid">

        {evidence.map((item) => (
          <div
            key={item.source}
            className={`evidence-card ${
              item.wide ? 'evidence-wide' : ''
            }`}
          >

            <div className="evidence-icon">
              {item.icon}
            </div>

            <p className="evidence-source">
              {item.source}
            </p>

            <p className="evidence-value">
              {item.value}
            </p>

            <p className="evidence-detail">
              {item.detail}
            </p>

          </div>
        ))}

      </div>

      <div className="analysis-actions">

        <button
          className="analysis-button"
          onClick={() => navigate('/recommendation')}
        >
          Continue to Recommendation →
        </button>

      </div>

    </div>
  )
}

export default Analysis