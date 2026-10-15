import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './Feedback.css'

function Feedback() {
  const navigate = useNavigate()

  const [outcome, setOutcome] = useState('')
  const [effectiveness, setEffectiveness] = useState(45)
  const [notes, setNotes] = useState('')

  const handleSubmit = (event) => {
    event.preventDefault()

    const feedbackData = {
      action: 'Treatment B',
      expectedOutcome: 80,
      observedOutcome: effectiveness,
      outcome,
      notes,
    }

    console.log('Farmer Feedback:', feedbackData)

    navigate('/adaptive-update')
  }

  return (
    <div className="feedback-page">

      <div className="feedback-header">
        <h1>Record Farm Outcome</h1>

        <p>
          Tell AgroNexus what happened after the recommended
          intervention was used.
        </p>
      </div>

      <form
        className="feedback-card"
        onSubmit={handleSubmit}
      >

        <div className="previous-decision">

          <p className="previous-decision-label">
            Previous recommendation
          </p>

          <p className="previous-decision-action">
            Treatment B
          </p>

          <p className="previous-decision-outcome">
            Expected outcome: 80%
          </p>

        </div>

        <div className="feedback-section">

          <span className="feedback-section-title">
            What happened?
          </span>

          <div className="outcome-options">

            <div className="outcome-option">
              <input
                id="improved"
                type="radio"
                name="outcome"
                value="improved"
                checked={outcome === 'improved'}
                onChange={(event) =>
                  setOutcome(event.target.value)
                }
                required
              />

              <label htmlFor="improved">
                ✓ Improved
              </label>
            </div>

            <div className="outcome-option">
              <input
                id="same"
                type="radio"
                name="outcome"
                value="same"
                checked={outcome === 'same'}
                onChange={(event) =>
                  setOutcome(event.target.value)
                }
              />

              <label htmlFor="same">
                → Same
              </label>
            </div>

            <div className="outcome-option">
              <input
                id="worse"
                type="radio"
                name="outcome"
                value="worse"
                checked={outcome === 'worse'}
                onChange={(event) =>
                  setOutcome(event.target.value)
                }
              />

              <label htmlFor="worse">
                ↓ Worse
              </label>
            </div>

          </div>

        </div>

        <div className="feedback-section">

          <label htmlFor="effectiveness">
            Observed Effectiveness
          </label>

          <input
            id="effectiveness"
            className="effectiveness-slider"
            type="range"
            min="0"
            max="100"
            value={effectiveness}
            onChange={(event) =>
              setEffectiveness(Number(event.target.value))
            }
          />

          <div className="effectiveness-value">
            {effectiveness}%
          </div>

        </div>

        <div className="feedback-section">

          <label htmlFor="notes">
            Additional Notes
          </label>

          <textarea
            id="notes"
            className="feedback-textarea"
            placeholder="Describe any observations, changes, or problems..."
            value={notes}
            onChange={(event) =>
              setNotes(event.target.value)
            }
          />

        </div>

        <div className="feedback-actions">

          <button
            className="feedback-button"
            type="submit"
          >
            Submit Outcome →
          </button>

        </div>

      </form>

    </div>
  )
}

export default Feedback