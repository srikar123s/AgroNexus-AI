import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './CropInformation.css'

function CropInformation() {
  const navigate = useNavigate()

  const [formData, setFormData] = useState({
    crop: '',
    variety: '',
    growthStage: '',
    plantingDate: '',
    symptoms: '',
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

    console.log('Crop Information:', formData)

    navigate('/image')
  }

  return (
    <div className="crop-form-page">

      <div className="crop-form-header">
        <h1>Crop Information</h1>

        <p>
          Tell us about the crop you're currently growing.
        </p>
      </div>

      <form
        className="crop-form-card"
        onSubmit={handleSubmit}
      >

        <div className="crop-form-grid">

          <div className="crop-form-group">
            <label htmlFor="crop">
              Crop
            </label>

            <select
              id="crop"
              name="crop"
              value={formData.crop}
              onChange={handleChange}
              required
            >
              <option value="">
                Select crop
              </option>

              <option value="tomato">
                Tomato
              </option>

              <option value="rice">
                Rice
              </option>

              <option value="wheat">
                Wheat
              </option>

              <option value="cotton">
                Cotton
              </option>

              <option value="maize">
                Maize
              </option>

              <option value="sugarcane">
                Sugarcane
              </option>

              <option value="other">
                Other
              </option>
            </select>
          </div>

          <div className="crop-form-group">
            <label htmlFor="variety">
              Variety
            </label>

            <input
              id="variety"
              name="variety"
              type="text"
              placeholder="Enter variety, if known"
              value={formData.variety}
              onChange={handleChange}
            />
          </div>

          <div className="crop-form-group">
            <label htmlFor="growthStage">
              Growth Stage
            </label>

            <select
              id="growthStage"
              name="growthStage"
              value={formData.growthStage}
              onChange={handleChange}
              required
            >
              <option value="">
                Select growth stage
              </option>

              <option value="seedling">
                Seedling
              </option>

              <option value="vegetative">
                Vegetative
              </option>

              <option value="flowering">
                Flowering
              </option>

              <option value="fruiting">
                Fruiting
              </option>

              <option value="maturity">
                Maturity
              </option>

              <option value="harvest">
                Harvest
              </option>
            </select>
          </div>

          <div className="crop-form-group">
            <label htmlFor="plantingDate">
              Planting Date
            </label>

            <input
              id="plantingDate"
              name="plantingDate"
              type="date"
              value={formData.plantingDate}
              onChange={handleChange}
            />
          </div>

          <div className="crop-form-group full-width">
            <label htmlFor="symptoms">
              Current Symptoms
            </label>

            <textarea
              id="symptoms"
              name="symptoms"
              placeholder="Describe what you currently observe on the crop..."
              value={formData.symptoms}
              onChange={handleChange}
            />
          </div>

        </div>

        <div className="crop-form-actions">
          <button
            className="crop-primary-button"
            type="submit"
          >
            Continue →
          </button>
        </div>

      </form>

    </div>
  )
}

export default CropInformation