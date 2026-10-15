import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './FarmProfile.css'

function FarmProfile() {
  const navigate = useNavigate()

  const [formData, setFormData] = useState({
    farmId: '',
    location: '',
    soilType: '',
    resources: '',
    budget: '',
    constraints: '',
  })

  const handleChange = (event) => {
    const { name, value } = event.target

    setFormData((previous) => ({
      ...previous,
      [name]: value,
    }))
  }

  const handleSubmit = (event) => {
    event.preventDefault()

    console.log('Farm Profile:', formData)

    navigate('/crop')
  }

  return (
    <div className="form-page">

      <div className="form-header">
        <h1>Farm Profile</h1>

        <p>
          Tell us about your farm so AgroNexus can understand
          your current farming context.
        </p>
      </div>

      <form
        className="form-card"
        onSubmit={handleSubmit}
      >

        <div className="form-grid">

          <div className="form-group">
            <label htmlFor="farmId">
              Farm / Field ID
            </label>

            <input
              id="farmId"
              name="farmId"
              type="text"
              placeholder="Example: FARM-001"
              value={formData.farmId}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="location">
              Location
            </label>

            <input
              id="location"
              name="location"
              type="text"
              placeholder="Village, District, State"
              value={formData.location}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="soilType">
              Soil Type
            </label>

            <select
              id="soilType"
              name="soilType"
              value={formData.soilType}
              onChange={handleChange}
              required
            >
              <option value="">
                Select soil type
              </option>

              <option value="loamy">
                Loamy
              </option>

              <option value="clay">
                Clay
              </option>

              <option value="sandy">
                Sandy
              </option>

              <option value="silty">
                Silty
              </option>

              <option value="red">
                Red Soil
              </option>

              <option value="black">
                Black Soil
              </option>

              <option value="other">
                Other
              </option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="resources">
              Available Resources
            </label>

            <input
              id="resources"
              name="resources"
              type="text"
              placeholder="Example: Irrigation, labor, equipment"
              value={formData.resources}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label htmlFor="budget">
              Available Budget
            </label>

            <input
              id="budget"
              name="budget"
              type="number"
              min="0"
              placeholder="Enter amount"
              value={formData.budget}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group full-width">
            <label htmlFor="constraints">
              Additional Constraints
            </label>

            <textarea
              id="constraints"
              name="constraints"
              placeholder="Describe any important limitations..."
              value={formData.constraints}
              onChange={handleChange}
            />
          </div>

        </div>

        <div className="form-actions">
          <button
            className="primary-button"
            type="submit"
          >
            Continue →
          </button>
        </div>

      </form>

    </div>
  )
}

export default FarmProfile