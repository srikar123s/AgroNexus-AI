import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './CropImage.css'

function CropImage() {
  const navigate = useNavigate()

  const [image, setImage] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)

  const handleImageChange = (event) => {
    const selectedFile = event.target.files?.[0]

    if (!selectedFile) {
      return
    }

    if (!selectedFile.type.startsWith('image/')) {
      alert('Please select a valid image file.')
      return
    }

    setImage(selectedFile)
    setPreviewUrl(URL.createObjectURL(selectedFile))
  }

  const handleRemove = () => {
    setImage(null)
    setPreviewUrl(null)
  }

  const handleContinue = () => {
    if (!image) {
      return
    }

    console.log('Crop image selected:', image)

    navigate('/analysis')
  }

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  return (
    <div className="image-page">

      <div className="image-header">
        <h1>Crop Image</h1>

        <p>
          Upload a clear image of the crop or affected leaf
          for analysis.
        </p>
      </div>

      <div className="image-card">

        {!previewUrl && (
          <div className="upload-area">

            <div className="upload-icon">
              📷
            </div>

            <h2>
              Upload Crop Image
            </h2>

            <p>
              Use a clear image showing the crop or visible symptoms.
            </p>

            <label
              htmlFor="crop-image"
              className="upload-button"
            >
              Choose Image
            </label>

            <input
              id="crop-image"
              className="file-input"
              type="file"
              accept="image/*"
              onChange={handleImageChange}
            />

          </div>
        )}

        {previewUrl && (
          <div className="preview-section">

            <h2>
              Image Preview
            </h2>

            <div className="image-preview-container">

              <img
                className="image-preview"
                src={previewUrl}
                alt="Selected crop"
              />

            </div>

            <button
              className="remove-button"
              type="button"
              onClick={handleRemove}
            >
              Remove Image
            </button>

          </div>
        )}

        <div className="image-actions">

          <button
            className="primary-button"
            type="button"
            disabled={!image}
            onClick={handleContinue}
          >
            Analyze Crop →
          </button>

        </div>

      </div>

    </div>
  )
}

export default CropImage