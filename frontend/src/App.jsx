import { useEffect, useState } from 'react'
import { api } from './api'
import './index.css'

const SIDEBAR_ITEMS = [
  { id: 'dashboard', icon: '🏠', label: 'Crop Dashboard', step: 0 },
  { id: 'farm', icon: '🌾', label: '1. Farm Setup', step: 1 },
  { id: 'crop', icon: '🌱', label: '2. Crop Recommendation', step: 2 },
  { id: 'analysis', icon: '📅', label: '3. Management Plan', step: 3 },
  { id: 'monitoring', icon: '📊', label: '4. Crop Monitoring', step: 4 },
  { id: 'image', icon: '📷', label: '5. Disease Detection', step: 5 },
  { id: 'recommend', icon: '🧠', label: '6. Action Recommendation', step: 6 },
  { id: 'feedback', icon: '🔄', label: '7. Results & Learning', step: 7 },
  { id: 'benchmark', icon: '🧪', label: '8. Performance Review', step: 8 },
]

const JOURNEY_STEPS = [
  { step: 1, id: 'farm', label: '① Farm Setup' },
  { step: 2, id: 'crop', label: '② Crop Recommendation' },
  { step: 3, id: 'analysis', label: '③ Growing Plan' },
  { step: 4, id: 'monitoring', label: '④ Monitoring' },
  { step: 5, id: 'image', label: '⑤ Disease Check' },
  { step: 6, id: 'recommend', label: '⑥ Action Recommendation' },
  { step: 7, id: 'feedback', label: '⑦ Results & Learning' },
  { step: 8, id: 'benchmark', label: '⑧ Performance Review' },
]

const DEFAULT_FARM = {
  name: 'Green Valley Tomato Farm',
  state_name: 'Kerala',
  district_name: 'Wayanad',
  village_name: 'Achooranam',
  soil_type: 'loamy',
  water_source: 'Borewell & Rainfed',
  area_hectares: 2.5,
  budget: 50000,
  season: 'Kharif',
  additional_constraints: 'Labour and hand sprayer available',
  latitude: 11.6,
  longitude: 76.08,
}

const LEAF_INSPECTION_SAMPLES = [
  {
    id: 'early_blight_high',
    title: 'Leaf Sample A — Concentric Dark Lesions',
    disease_name: 'Early Blight (Alternaria solani)',
    detected: true,
    severity: 'high',
    confidence: 94,
    health_label: 'Disease Detected',
    summary:
      'Concentric bullseye dark brown rings on lower and mid-canopy foliage with surrounding chlorosis.',
  },
  {
    id: 'late_blight_mod',
    title: 'Leaf Sample B — Water-Soaked Margin Spots',
    disease_name: 'Foliar Blight / Leaf Spot',
    detected: true,
    severity: 'moderate',
    confidence: 89,
    health_label: 'Moderate Infection',
    summary:
      'Water-soaked lesions along leaf margins favored by high relative humidity and wet foliage.',
  },
  {
    id: 'healthy_canopy',
    title: 'Leaf Sample C — Uniform Green Canopy',
    disease_name: 'Healthy Crop (No Disease Detected)',
    detected: false,
    severity: 'low',
    confidence: 97,
    health_label: 'Healthy',
    summary:
      'Leaves show uniform chlorophyll coloration without fungal lesions or necrotic spots.',
  },
]

const DAY_BY_DAY_SMART_CALENDAR = {
  Tomato: [
    { days: 'Day 0', phase: 'Land Preparation', action: 'Deep ploughing, raised bed formation, incorporate 10 t/ha FYM + basal SSP & MOP.', monitor: 'Soil pH, sub-surface drainage slope, baseline NPK' },
    { days: 'Day 1–7', phase: 'Seedling Preparation', action: 'Sow hybrid seeds in pro-trays with Trichoderma viride treatment under net house.', monitor: 'Seed germination (>88%), nursery damping-off' },
    { days: 'Day 8–20', phase: 'Transplanting & Establishment', action: 'Transplant vigorous seedlings at 60×45 cm spacing; provide light root-zone life irrigation.', monitor: 'Transplant survival %, root-zone moisture (5–10 cm)' },
    { days: 'Day 21–45', phase: 'Vegetative Stage', action: 'First split Neem-Coated Urea top-dressing, bamboo staking, weeding.', monitor: 'Leaf chlorophyll color, whitefly/thrips vectors, soil moisture' },
    { days: 'Day 46–70', phase: 'Flowering Stage', action: 'Maintain uniform drip moisture, second N top-dressing, inspect lower canopy.', monitor: 'Air Humidity (>80%), Rain Probability (>40%), Early Blight lesions' },
    { days: 'Day 71–95', phase: 'Fruiting Stage', action: 'Apply water-soluble Potash (0:0:50), follow the recommended protection if disease is detected.', monitor: 'Fruit borer damage, foliar lesion spread, pre-spray rain forecast' },
    { days: 'Day 96–120', phase: 'Harvest', action: 'Pick fruits at breaker-to-red stage every 4–5 days during dry morning windows.', monitor: 'Fruit firmness, dry harvest window, post-harvest grading' },
  ],
  default: [
    { days: 'Day 0', phase: 'Land Preparation', action: 'Ploughing, field leveling, incorporate organic manure & basal P/K.', monitor: 'Soil tilth, pH, baseline village NPK' },
    { days: 'Day 1–10', phase: 'Seed / Nursery Preparation', action: 'Treat certified seed with bio-fungicide and establish nursery or ridge rows.', monitor: 'Germination rate & early seedling vigor' },
    { days: 'Day 11–25', phase: 'Sowing / Transplanting', action: 'Establish main field stand at recommended spacing with starter irrigation.', monitor: 'Stand establishment % & root-zone moisture' },
    { days: 'Day 26–55', phase: 'Vegetative Stage', action: 'First split nitrogen top-dressing, weeding, and canopy management.', monitor: 'Vegetative vigor, sucking pests, rainfall leaching risk' },
    { days: 'Day 56–80', phase: 'Flowering Stage', action: 'Critical moisture management, second nitrogen split, and foliar health scan.', monitor: 'Air humidity, rain probability, foliar fungal symptoms' },
    { days: 'Day 81–105', phase: 'Fruiting / Grain Filling', action: 'Potash supplementation and targeted protection if stress or disease occurs.', monitor: 'Pod/grain filling, disease severity, weather forecast' },
    { days: 'Day 106+', phase: 'Harvest', action: 'Harvest at physiological maturity during dry weather window.', monitor: 'Grain/produce moisture & storage hygiene' },
  ],
}

function WelcomeScreen({ onLogin, onJoin }) {
  return (
    <main className="welcome-page">
      <div className="welcome-nav">
        <div className="welcome-brand"><span>🌱</span><strong>AgroNexus AI</strong></div>
        <button className="welcome-link" type="button" onClick={onLogin}>Log in</button>
      </div>
      <section className="welcome-hero">
        <div className="welcome-copy">
          <span className="welcome-kicker">Your farm, made simpler</span>
          <h1>Better crop decisions, from seed to harvest.</h1>
          <p>AgroNexus brings your farm details, crop guidance, weather, and field observations together in one calm, easy-to-use place.</p>
          <div className="welcome-actions">
            <button className="primary-cta" type="button" onClick={onJoin}>Join AgroNexus <span>→</span></button>
            <button className="secondary-cta" type="button" onClick={onLogin}>I already have an account</button>
          </div>
          <div className="welcome-trust"><span>✓ Simple guidance</span><span>✓ Built for farmers</span><span>✓ Your farm stays yours</span></div>
        </div>
        <div className="welcome-visual">
          <img src="/agronexus-hero.svg" alt="A healthy green farm under a sunrise" />
          <div className="welcome-stat"><strong>One clear plan</strong><span>for your next farm decision</span></div>
        </div>
      </section>
      <section className="welcome-features">
        <div><span>🌾</span><strong>Know your field</strong><p>Keep your farm, soil, and crop details together.</p></div>
        <div><span>🌦️</span><strong>Plan with confidence</strong><p>Use local conditions to choose practical next steps.</p></div>
        <div><span>🌱</span><strong>Learn each season</strong><p>Record results and make future guidance more useful.</p></div>
      </section>
    </main>
  )
}

function AuthScreen({ mode, setMode, onSuccess, onBack }) {
  const [form, setForm] = useState({ email: '', username: '', phone: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const googleAuthUrl = import.meta.env.VITE_GOOGLE_AUTH_URL

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const result = mode === 'login'
        ? await api.login({ email: form.email, password: form.password })
        : await api.register(form)
      localStorage.setItem('agronexus-user', JSON.stringify(result))
      onSuccess(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-page">
      <button className="auth-back" type="button" onClick={onBack}>← Back to AgroNexus</button>
      <div className="auth-card">
        <div className="auth-mark">🌱</div>
        <span className="welcome-kicker">{mode === 'login' ? 'Welcome back' : 'Start your farm journey'}</span>
        <h1>{mode === 'login' ? 'Log in to your farm' : 'Create your farmer account'}</h1>
        <p className="auth-intro">{mode === 'login' ? 'Continue with your saved farm plans and guidance.' : 'Join free and keep your farm decisions in one place.'}</p>
        {error && <div className="auth-error">{error}</div>}
        <form onSubmit={submit} className="auth-form">
          {mode === 'login' ? (
            <label>Username, phone, or email<input required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@example.com" /></label>
          ) : (
            <>
              <label>Your name or username<input required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="e.g. RaviFarm" /></label>
              <label>Email address<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@example.com" /></label>
              <label>Phone number <span className="optional">(optional)</span><input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+91 98765 43210" /></label>
            </>
          )}
          <label>Password<input required minLength="8" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="At least 8 characters" /></label>
          <button className="primary-cta auth-submit" disabled={busy} type="submit">{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'} <span>→</span></button>
        </form>
        <div className="auth-divider"><span>or</span></div>
        <button className="google-button" type="button" onClick={() => googleAuthUrl ? (window.location.href = googleAuthUrl) : setError('Google sign-in is not configured yet. Add VITE_GOOGLE_AUTH_URL after the Google OAuth setup.')}>
          <strong>G</strong> Continue with Google
        </button>
        <p className="auth-switch">{mode === 'login' ? 'New to AgroNexus?' : 'Already have an account?'} <button type="button" onClick={() => { setError(''); setMode(mode === 'login' ? 'register' : 'login') }}>{mode === 'login' ? 'Join now' : 'Log in'}</button></p>
        <small className="auth-note">Google sign-in uses OAuth client credentials, not a private API key. Never place a Google client secret in this frontend.</small>
      </div>
    </main>
  )
}

function getSimpleApproachName(name = '') {
  if (name.includes('Fixed')) return 'Uses all available information'
  if (name.includes('Global')) return 'Uses general crop guidance'
  if (name.includes('Context-Only')) return 'Learns from similar field conditions'
  if (name.includes('Proposed')) return 'AgroNexus learning guidance'
  return name.replace(/^Baseline \d+:\s*/, '').replace('Proposed: ', '')
}

export default function App() {
  const [activePage, setActivePage] = useState('dashboard')
  const [authView, setAuthView] = useState(() => localStorage.getItem('agronexus-access-token') ? 'app' : 'welcome')
  const [authMode, setAuthMode] = useState('login')
  const handleLogout = () => {
    localStorage.removeItem('agronexus-access-token')
    localStorage.removeItem('agronexus-user')
    setAuthView('welcome')
  }
  // Dual View Mode: 'farmer' (simple agronomic explanations) vs 'research' (technical ERP/CNDA/ACER math)
  const [viewMode] = useState('farmer')

  const [farm, setFarm] = useState(DEFAULT_FARM)
  const [identity, setIdentity] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('agronexus-v2-farm') || 'null')
    } catch {
      return null
    }
  })

  // Automatic location, soil dataset & weather API state
  const [locations, setLocations] = useState({
    states: ['Kerala', 'Tamil Nadu', 'Karnataka', 'Andhra Pradesh', 'Telangana'],
    districts: ['Wayanad'],
    villages: ['Achooranam'],
    soil_evidence: null,
  })
  const [cropIntel, setCropIntel] = useState(null)
  const [selectedCrop, setSelectedCrop] = useState('Tomato')
  const [cropStage, setCropStage] = useState('flowering')

  // Image / Disease Detection state
  const [selectedSampleId, setSelectedSampleId] = useState('early_blight_high')
  const [uploadedImagePreview, setUploadedImagePreview] = useState(null)
  const [uploadedImageName, setUploadedImageName] = useState('')
  const [diseaseReport, setDiseaseReport] = useState(LEAF_INSPECTION_SAMPLES[0])

  // Stale weather simulation toggle (to demonstrate ERP sufficiency gating on stale humidity)
  const [weatherAgeHours, setWeatherAgeHours] = useState(1.0)

  // ADIE Decision, Alternatives, Feedback, Ledger & Benchmark state
  const [decisionResult, setDecisionResult] = useState(null)
  const [feedbackForm, setFeedbackForm] = useState({
    outcome_status: 'worse',
    observed_outcome: 40,
    outcome_measure_quality: 90,
    feedback_completeness: 90,
    rain_after_spray: true,
    notes: 'Heavy rain occurred after treatment.',
  })
  const [outcomeResult, setOutcomeResult] = useState(null)
  const [acerLedger, setAcerLedger] = useState(null)
  const [demoResult, setDemoResult] = useState(null)
  const [benchmarkResult, setBenchmarkResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // 1. Auto-fetch locations, soil dataset values, and weather whenever farm location changes
  useEffect(() => {
    api
      .getLocations(farm.state_name, farm.district_name, farm.village_name)
      .then((res) => {
        setLocations(res)
      })
      .catch(() => {})
  }, [farm.state_name, farm.district_name, farm.village_name])

  // 2. Auto-fetch Top 3 Recommended Crops + Complete 6-Part Crop Management Plan
  useEffect(() => {
    api
      .getCropIntelligence({
        state_name: farm.state_name,
        district_name: farm.district_name,
        village_name: farm.village_name,
        soil_type: farm.soil_type,
        water_source: farm.water_source,
        area_hectares: farm.area_hectares,
        selected_crop: selectedCrop,
        crop_stage: cropStage,
        budget: farm.budget,
        season: farm.season,
      })
      .then((res) => {
        setCropIntel(res)
      })
      .catch(() => {})
  }, [
    farm.state_name,
    farm.district_name,
    farm.village_name,
    farm.soil_type,
    farm.water_source,
    farm.area_hectares,
    farm.budget,
    farm.season,
    selectedCrop,
    cropStage,
  ])

  // 3. Load ACER Learning History when visiting Outcome/Learning or Benchmark pages
  useEffect(() => {
    if (activePage === 'feedback' || activePage === 'benchmark') {
      api
        .getAcerLedger('disease_intervention')
        .then((res) => setAcerLedger(res))
        .catch(() => {})
    }
  }, [activePage, outcomeResult, demoResult])

  const env = cropIntel?.environmental_evidence ||
    locations?.soil_evidence || {
      temperature: 29,
      air_humidity: 84,
      rain_probability: 42,
      weather_condition: 'Humid • Afternoon Showers Expected',
      n_status: 'Medium',
      p_status: 'Medium',
      k_status: 'Medium',
      ph_status: 'Neutral',
      soil_fertility: 0.65,
      source_level: 'village_soil_master_v4',
    }

  const handleFarmField = (e) => {
    const { name, type, value } = e.target
    setFarm((prev) => ({
      ...prev,
      [name]: type === 'number' ? Number(value) : value,
    }))
  }

  async function ensureFarmSaved() {
    if (identity?.farm_id) return identity
    const created = await api.createFarm({
      ...farm,
      field_name: 'Main Field',
      area_hectares: Number(farm.area_hectares) || 2.0,
      budget: Number(farm.budget) || 50000,
      season: farm.season || 'Kharif',
    })
    const merged = { ...farm, ...created }
    localStorage.setItem('agronexus-v2-farm', JSON.stringify(merged))
    setIdentity(merged)
    return merged
  }

  async function handleSaveFarmProfile(e) {
    e?.preventDefault()
    setBusy(true)
    setError('')
    try {
      const created = await api.createFarm({
        ...farm,
        field_name: 'Main Field',
        area_hectares: Number(farm.area_hectares) || 2.0,
        budget: Number(farm.budget) || 50000,
        season: farm.season || 'Kharif',
      })
      const merged = { ...farm, ...created }
      localStorage.setItem('agronexus-v2-farm', JSON.stringify(merged))
      setIdentity(merged)
      const recRes = await api.recommendCrops({
        state_name: farm.state_name,
        district_name: farm.district_name,
        village_name: farm.village_name,
        soil_type: farm.soil_type,
        water_source: farm.water_source,
        area_hectares: Number(farm.area_hectares) || 2.0,
        selected_crop: selectedCrop,
        crop_stage: cropStage,
        budget: Number(farm.budget) || 50000,
        season: farm.season || 'Kharif',
      })
      setCropIntel(recRes)
      setActivePage('crop')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function runAdieDecisionEngine(
    targetPage = null,
    overrideDisease = null,
    overrideCrop = null,
    overrideStage = null,
    overrideAgeHours = null
  ) {
    setBusy(true)
    setError('')
    try {
      const activeFarm = await ensureFarmSaved()
      const activeDisease = overrideDisease || diseaseReport
      const activeCropName = overrideCrop || selectedCrop
      const activeStage = overrideStage || cropStage
      const activeAge = overrideAgeHours !== null ? overrideAgeHours : weatherAgeHours

      const res = await api.makeDecision({
        farm_id: activeFarm.farm_id,
        field_id: activeFarm.field_id,
        decision_type: 'disease_intervention',
        crop: activeCropName,
        crop_stage: activeStage,
        disease_severity: activeDisease.detected ? activeDisease.severity : 'low',
        rain_probability: Number(env.rain_probability ?? 42),
        air_humidity: Number(env.air_humidity ?? 84),
        temperature: Number(env.temperature ?? 29),
        soil_fertility: Number(env.soil_fertility ?? 0.65),
        budget: Number(farm.budget) || 50000,
        resources: farm.additional_constraints || 'Labour and hand sprayer available',
        notes: `${activeDisease.disease_name} (${activeDisease.summary})`,
        has_crop_image: true,
        weather_age_hours: Number(activeAge),
        weather_distance_km: 1.5,
        enforce_inclusion_floor: true,
      })
      setDecisionResult(res)
      if (targetPage) setActivePage(targetPage)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleSelectCropAndAnalyze(cropName) {
    const cleanName = cropName.split(' (')[0]
    setSelectedCrop(cleanName)
    setActivePage('analysis')
  }

  async function handleImageUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadedImageName(file.name)
    const url = URL.createObjectURL(file)
    setUploadedImagePreview(url)
    try {
      const yoloEv = await api.analyzeDiseaseImage({
        crop: selectedCrop,
        crop_stage: cropStage,
        image_name: file.name,
      })
      const nextReport = {
        id: 'uploaded_custom',
        title: `Uploaded Image (${file.name})`,
        ...yoloEv,
      }
      setSelectedSampleId(nextReport.id)
      setDiseaseReport(nextReport)
      await runAdieDecisionEngine(null, nextReport)
    } catch {
      // fallback local
    }
  }

  async function handleSelectSamplePreset(sample) {
    setSelectedSampleId(sample.id)
    setUploadedImagePreview(null)
    setUploadedImageName('')
    try {
      const yoloEv = await api.analyzeDiseaseImage({
        crop: selectedCrop,
        crop_stage: cropStage,
        sample_id: sample.id,
      })
      const nextReport = {
        ...sample,
        ...yoloEv,
      }
      setDiseaseReport(nextReport)
      await runAdieDecisionEngine(null, nextReport)
    } catch {
      const nextReport = {
        ...sample,
        disease_name: sample.detected
          ? `${selectedCrop} ${sample.disease_name}`
          : sample.disease_name,
      }
      setDiseaseReport(nextReport)
      await runAdieDecisionEngine(null, nextReport)
    }
  }

  async function handleSubmitFeedback(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      let currentDec = decisionResult
      if (!currentDec?.decision_id) {
        const activeFarm = await ensureFarmSaved()
        currentDec = await api.makeDecision({
          farm_id: activeFarm.farm_id,
          field_id: activeFarm.field_id,
          decision_type: 'disease_intervention',
          crop: selectedCrop,
          crop_stage: cropStage,
          disease_severity: diseaseReport.detected ? diseaseReport.severity : 'moderate',
          rain_probability: Number(env.rain_probability ?? 42),
          air_humidity: Number(env.air_humidity ?? 84),
          temperature: Number(env.temperature ?? 29),
          soil_fertility: Number(env.soil_fertility ?? 0.65),
          budget: Number(farm.budget) || 50000,
          resources: farm.additional_constraints || 'Labour and hand sprayer available',
          notes: diseaseReport.disease_name,
          has_crop_image: true,
        })
        setDecisionResult(currentDec)
      }

      const saved = await api.recordOutcome(currentDec.decision_id, {
        observed_outcome: Number(feedbackForm.observed_outcome),
        outcome_status: feedbackForm.outcome_status,
        notes: feedbackForm.rain_after_spray
          ? `${feedbackForm.notes} [Heavy rain/humidity occurred after application]`
          : feedbackForm.notes,
        outcome_measure_quality: Number(feedbackForm.outcome_measure_quality) / 100,
        feedback_completeness: Number(feedbackForm.feedback_completeness) / 100,
      })
      setOutcomeResult(saved)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleRunMultiCycleSimulation() {
    setBusy(true)
    setError('')
    try {
      const res = await api.runClosedLoopDemo()
      setDemoResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleRunFourBaselineBenchmark() {
    setBusy(true)
    setError('')
    try {
      const res = await api.runBenchmarks(30, 42)
      setBenchmarkResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const analysis = cropIntel?.selected_crop_analysis
  const cropOverview = analysis?.crop_overview
  const growingStages = analysis?.growing_stages || []
  const resourceReq = analysis?.resource_requirements
  const whatToMonitor = analysis?.what_to_monitor || []
  const riskPrev = analysis?.risk_and_prevention
  const waterPlan = analysis?.water_plan
  const fertPlan = analysis?.fertilizer_plan
  const topCrops = cropIntel?.top_crops || []
  const cropSelectionErp = cropIntel?.crop_selection_erp

  const smartDayCalendar =
    DAY_BY_DAY_SMART_CALENDAR[selectedCrop] || DAY_BY_DAY_SMART_CALENDAR.default

  const currentStepNumber =
    SIDEBAR_ITEMS.find((i) => i.id === activePage)?.step || 0

  // Evidence Readiness bars for the Evidence Dashboard (Stage 7)
  const freshnessFactor = weatherAgeHours > 24 ? 0.54 : 1.0
  const evidenceReadinessBars = [
    { label: 'Humidity Evidence', pct: Math.round(95 * freshnessFactor), weight: demoResult ? 0.149 : 0.12 },
    { label: 'Rain Probability', pct: Math.round(92 * freshnessFactor), weight: demoResult ? 0.192 : 0.16 },
    { label: 'Leaf health check', pct: diseaseReport.confidence || 94, weight: 0.22 },
    { label: 'Crop Growth Stage', pct: 94, weight: 0.14 },
    { label: 'Temperature', pct: Math.round(89 * freshnessFactor), weight: 0.10 },
    { label: 'Soil Fertility (Dataset)', pct: Math.round((env.soil_fertility || 0.65) * 100), weight: 0.10 },
    { label: 'Farmer Budget', pct: 95, weight: 0.08 },
  ]
  const overallReadinessPct = decisionResult?.sufficiency
    ? Math.round(decisionResult.sufficiency.score * 100)
    : weatherAgeHours > 24
    ? 61
    : 89

  if (authView === 'welcome') {
    return <WelcomeScreen onLogin={() => { setAuthMode('login'); setAuthView('auth') }} onJoin={() => { setAuthMode('register'); setAuthView('auth') }} />
  }
  if (authView === 'auth') {
    return <AuthScreen mode={authMode} setMode={setAuthMode} onBack={() => setAuthView('welcome')} onSuccess={() => setAuthView('app')} />
  }

  // Important event and risk alerts
  const activeAlerts = [
    ...(env.rain_probability >= 35
      ? [
          {
            level: 'warn',
            title: `⚠️ High rainfall probability detected (${Math.round(env.rain_probability)}%)`,
            detail:
              'Leaf treatments can wash off if applied just before rain. Review the suggested action for a rain-safe option.',
          },
        ]
      : []),
    ...(env.air_humidity >= 75
      ? [
          {
            level: 'warn',
            title: `⚠️ Current humidity (${Math.round(env.air_humidity)}%) is unusually high for ${selectedCrop} (${cropStage} stage)`,
            detail:
              'Alert: High canopy humidity accelerates fungal spore germination (Early/Late Blight). Monitor lower leaves closely.',
          },
        ]
      : []),
    ...(weatherAgeHours > 24
      ? [
          {
            level: 'danger',
            title: '⚠️ Disease risk evidence requires updated humidity information (48h stale)',
            detail:
              'Fresh humidity and rain information is needed before confirming a high-confidence action.',
          },
        ]
      : []),
  ]

  // Learning summary rows
  const cndaDisplayRows =
    demoResult?.cycles?.[4]?.cnda?.ranked_factors ||
    outcomeResult?.cnda?.ranked_factors || [
      { factor: 'weather_rain_probability', rho_spearman: -0.89, direction: 'negative', selected: true },
      { factor: 'air_humidity', rho_spearman: -0.85, direction: 'negative', selected: true },
      { factor: 'temperature', rho_spearman: -0.12, direction: 'negative', selected: false },
      { factor: 'soil_fertility', rho_spearman: 0.04, direction: 'positive', selected: false },
    ]

  const activeRecommendedAction =
    outcomeResult?.suggested_new_treatment ||
    decisionResult?.recommendation || {
      name: 'Apply locally approved fungicide in a dry window',
      description: 'Use a contact/broad-spectrum product during a dry application window.',
      expected_outcome: 80,
      estimated_cost: 350,
    }

  const cropHealthScore = diseaseReport.detected
    ? diseaseReport.severity === 'high'
      ? 72
      : 81
    : 95

  return (
    <div className="agronexus-app">
      {/* Top bar */}
      <header className="top-navbar">
        <div className="top-navbar-brand" onClick={() => setActivePage('dashboard')}>
          <span className="brand-logo">🌱</span>
          <div>
            <strong>AgroNexus AI</strong>
            <small>Simple crop planning and field guidance</small>
          </div>
        </div>

        <div className="top-navbar-right">
          <span className="auto-sync-pill">
            ☁ Live weather & soil updates
          </span>
          <div className="farmer-profile-pill" onClick={() => setActivePage('farm')}>
            <span>👤</span>
            <div>
              <strong>{farm.name}</strong>
              <small>{farm.village_name}, {farm.district_name}</small>
            </div>
          </div>
          <button className="logout-button" type="button" onClick={handleLogout}>Log out</button>
        </div>
      </header>

      {/* ============================================================
          VISUAL JOURNEY STEPPER BAR (8 FROZEN MODULES)
         ============================================================ */}
      <div className="journey-stepper-bar">
        {JOURNEY_STEPS.map((st, idx) => {
          const isCurrent = activePage === st.id
          const isCompleted = currentStepNumber > st.step
          return (
            <div key={st.id} className="journey-step-wrapper">
              <button
                type="button"
                className={`journey-step-node ${isCurrent ? 'current' : ''} ${
                  isCompleted ? 'completed' : ''
                }`}
                onClick={() => setActivePage(st.id)}
              >
                <span className="j-dot">{isCompleted ? '●' : isCurrent ? '◉' : '○'}</span>
                <span>{st.label}</span>
              </button>
              {idx < JOURNEY_STEPS.length - 1 && (
                <div className={`journey-connector ${isCompleted ? 'done' : ''}`} />
              )}
            </div>
          )
        })}
      </div>

      {/* ============================================================
          MAIN BODY: LEFT SIDEBAR + PAGE CONTENT
         ============================================================ */}
      <div className="main-frame">
        <aside className="sidebar-menu">
          {SIDEBAR_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sidebar-btn ${activePage === item.id ? 'active' : ''}`}
              onClick={() => {
                setError('')
                setActivePage(item.id)
              }}
            >
              <span className="sb-icon">{item.icon}</span>
              <span className="sb-label">{item.label}</span>
            </button>
          ))}
        </aside>

        <main className="page-viewport">
          {error && <div className="alert-box">{error}</div>}

          {/* ============================================================
              MODULE 0: 🏠 CROP HEALTH DASHBOARD (FARMER'S MAIN HOME SCREEN)
             ============================================================ */}
          {activePage === 'dashboard' && (
            <div className="page-card-container">
              <div className="greeting-header">
                <h1>{selectedCrop} Crop Health Dashboard 👋</h1>
                <p>
                  {farm.name} ({farm.village_name}, {farm.district_name}) • Mode:{' '}
                  <strong>👨‍🌾 Simple farm view</strong>
                </p>
              </div>

              {/* Important event and risk alerts */}
              {activeAlerts.length > 0 && (
                <div className="alerts-stack">
                  <div className="alerts-header-row">
                    <strong>🔔 Important Event & Risk Alerts</strong>
                    <small>
                      Alerts highlight something that needs your attention. Review the suggested action when you are ready.
                    </small>
                  </div>
                  {activeAlerts.map((al, i) => (
                    <div key={i} className={`risk-alert-banner ${al.level}`}>
                      <div>
                        <strong>{al.title}</strong>
                        <p>{al.detail}</p>
                      </div>
                      <button
                        type="button"
                        className="secondary-cta-btn"
                        onClick={() => setActivePage('recommend')}
                      >
                        Review suggested action →
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* 📊 CROP HEALTH DASHBOARD SUMMARY CARD */}
              <div className="wireframe-card">
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">📊 Active Crop Health Overview</span>
                    <h1>
                      🍅 {selectedCrop} — {farm.area_hectares} Hectares
                    </h1>
                  </div>
                  <span className="status-ok-badge">
                    Crop Health: {cropHealthScore}%
                  </span>
                </div>

                <div className="crop-health-kv-grid">
                  <div className="ch-kv-box">
                    <span>Crop Stage</span>
                    <strong>{cropStage.toUpperCase()}</strong>
                    <small>{farm.season} Season</small>
                  </div>
                  <div className="ch-kv-box">
                    <span>Crop Health</span>
                    <strong>{cropHealthScore}%</strong>
                    <small>{diseaseReport.detected ? 'Requires Intervention' : 'Optimal Canopy'}</small>
                  </div>
                  <div className="ch-kv-box">
                    <span>Disease Status</span>
                    <strong>{diseaseReport.disease_name.split(' (')[0]}</strong>
                    <small>Severity: {diseaseReport.severity.toUpperCase()}</small>
                  </div>
                  <div className="ch-kv-box">
                    <span>Soil Condition</span>
                    <strong>Good ({farm.soil_type})</strong>
                    <small>N: {env.n_status} • P: {env.p_status} • K: {env.k_status}</small>
                  </div>
                  <div className="ch-kv-box">
                    <span>Weather Risk</span>
                    <strong>{env.rain_probability >= 35 ? 'Moderate / Rain Risk' : 'Favorable'}</strong>
                    <small>{env.temperature}°C • Rain {Math.round(env.rain_probability)}% • Hum {Math.round(env.air_humidity)}%</small>
                  </div>
                  <div className="ch-kv-box">
                    <span>Water Availability</span>
                    <strong>Adequate</strong>
                    <small>{farm.water_source} ({waterPlan ? `${waterPlan.total_farm_liters_per_day.toLocaleString()} L/d` : '112,500 L/d'})</small>
                  </div>
                  <div className="ch-kv-box">
                    <span>Available Budget</span>
                    <strong>₹{Number(farm.budget || 50000).toLocaleString()}</strong>
                    <small>Within cultivation plan</small>
                  </div>
                  <div className="ch-kv-box highlight-kv">
                    <span>Next Important Action</span>
                    <strong>→ Review disease action</strong>
                    <small>Recommendation version {decisionResult?.erp_version ?? (demoResult ? 2 : 1)}</small>
                  </div>
                </div>

                <div className="wf-footer-between">
                  <div className="rd-buttons">
                    <button
                      type="button"
                      className="secondary-cta-btn"
                      onClick={() => setActivePage('farm')}
                    >
                      1. Edit Farm Setup
                    </button>
                    <button
                      type="button"
                      className="secondary-cta-btn"
                      onClick={() => setActivePage('analysis')}
                    >
                      3. View Crop Management Plan & Calendar
                    </button>
                  </div>
                  <button
                    type="button"
                    className="primary-cta-btn"
                    onClick={() => setActivePage('recommend')}
                  >
                    Review disease action (🧠) →
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================
              MODULE 1: 🌾 FARM SETUP
             ============================================================ */}
          {activePage === 'farm' && (
            <div className="page-card-container narrow-container">
              <form className="wireframe-card" onSubmit={handleSaveFarmProfile}>
                <div className="wf-header">
                  <span className="tag-pill">Module 1 • Base Farm Context</span>
                  <h1>Farm Setup</h1>
                  <p>
                    Register your farm location, soil type, cultivated area, season, and budget. Weather, humidity, rainfall, and village soil NPK values are fetched automatically.
                  </p>
                </div>

                <div className="wf-field">
                  <label>Farm Name</label>
                  <input
                    name="name"
                    value={farm.name}
                    onChange={handleFarmField}
                    placeholder="Enter your farm name"
                    required
                  />
                </div>

                <div className="wf-grid-3">
                  <div className="wf-field">
                    <label>State</label>
                    <select name="state_name" value={farm.state_name} onChange={handleFarmField}>
                      {(locations.states?.length
                        ? locations.states
                        : ['Kerala', 'Tamil Nadu', 'Karnataka', 'Andhra Pradesh', 'Telangana']
                      ).map((st) => (
                        <option key={st} value={st}>
                          {st}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="wf-field">
                    <label>District</label>
                    <select
                      name="district_name"
                      value={farm.district_name}
                      onChange={handleFarmField}
                    >
                      {(locations.districts?.length
                        ? locations.districts
                        : [farm.district_name || 'Wayanad']
                      ).map((dist) => (
                        <option key={dist} value={dist}>
                          {dist}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="wf-field">
                    <label>Village</label>
                    <input
                      name="village_name"
                      value={farm.village_name}
                      onChange={handleFarmField}
                      list="village-list"
                      placeholder="Select or type village"
                    />
                    <datalist id="village-list">
                      {(locations.villages || []).map((v) => (
                        <option key={v} value={v} />
                      ))}
                    </datalist>
                  </div>
                </div>

                <div className="wf-grid-3">
                  <div className="wf-field">
                    <label>Area (Hectares)</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.1"
                      name="area_hectares"
                      value={farm.area_hectares}
                      onChange={handleFarmField}
                      required
                    />
                  </div>

                  <div className="wf-field">
                    <label>Soil Type</label>
                    <select name="soil_type" value={farm.soil_type} onChange={handleFarmField}>
                      <option value="loamy">Loamy Soil</option>
                      <option value="black">Black Soil</option>
                      <option value="red">Red Soil</option>
                      <option value="clay">Clay Soil</option>
                      <option value="sandy">Sandy Soil</option>
                    </select>
                  </div>

                  <div className="wf-field">
                    <label>Budget (₹ INR)</label>
                    <input
                      type="number"
                      step="1000"
                      min="2000"
                      name="budget"
                      value={farm.budget}
                      onChange={handleFarmField}
                      required
                    />
                  </div>
                </div>

                <div className="wf-grid-3">
                  <div className="wf-field">
                    <label>Growing Season</label>
                    <select name="season" value={farm.season} onChange={handleFarmField}>
                      <option value="Kharif">Kharif (Monsoon)</option>
                      <option value="Rabi">Rabi (Winter)</option>
                      <option value="Zaid">Zaid (Summer)</option>
                    </select>
                  </div>

                  <div className="wf-field">
                    <label>Available Water Source</label>
                    <select name="water_source" value={farm.water_source} onChange={handleFarmField}>
                      <option value="Borewell & Rainfed">Borewell & Rainfed</option>
                      <option value="Canal Irrigation">Canal Irrigation</option>
                      <option value="Drip Irrigation Tank">Drip Irrigation Tank</option>
                      <option value="Open Well">Open Well</option>
                      <option value="Rainfed Only">Rainfed Only</option>
                    </select>
                  </div>

                  <div className="wf-field">
                    <label>Resources & Constraints</label>
                    <input
                      name="additional_constraints"
                      value={farm.additional_constraints}
                      onChange={handleFarmField}
                      placeholder="e.g., Labour and sprayer available"
                    />
                  </div>
                </div>

                <div className="auto-fetched-strip">
                  <strong>✓ Auto-Fetched Soil & Weather for {farm.village_name || farm.district_name}:</strong>
                  <span>
                    Soil N: <b>{env.n_status}</b> • P: <b>{env.p_status}</b> • K: <b>{env.k_status}</b> • pH:{' '}
                    <b>{env.ph_status}</b> | Weather: <b>{env.temperature}°C</b> • Rain:{' '}
                    <b>{Math.round(env.rain_probability)}%</b> • Humidity: <b>{Math.round(env.air_humidity)}%</b>
                  </span>
                </div>

                <div className="wf-footer-right">
                  <button type="submit" className="primary-cta-btn" disabled={busy}>
                    {busy ? 'Saving Farm Setup…' : 'Continue to Crop Recommendation →'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* ============================================================
              MODULE 2: 🌱 CROP RECOMMENDATION (LEVEL-1 DECISION)
             ============================================================ */}
          {activePage === 'crop' && (
            <div className="page-card-container">
              <div className="wireframe-card">
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">Module 2 • Level-1 Decision (crop_selection)</span>
                    <h1>Crop Recommendation — What Should You Grow?</h1>
                    <p>
                      Ranked for <strong>{farm.village_name}, {farm.district_name}</strong> ({farm.area_hectares} ha,{' '}
                      {farm.soil_type} soil, {farm.season} season, Budget ₹{Number(farm.budget || 50000).toLocaleString()}).
                    </p>
                  </div>
                  <span className="status-ok-badge">
                    Evidence Readiness:{' '}
                    {cropSelectionErp
                      ? `${Math.round(cropSelectionErp.sufficiency_score * 100)}%`
                      : '90%'}{' '}
                    ✓
                  </span>
                </div>

                {viewMode === 'research' && cropSelectionErp && (
                  <div className="erp-explain-card">
                    <div className="erp-explain-top">
                      <div>
                        <strong>📋 Crop Selection ERP (Evidence Requirement Profile → A0 → A1)</strong>
                        <p>
                          ERP weights for <code>decision_type = crop_selection</code> before ranking suitable crops:
                        </p>
                      </div>
                      <div className="suff-meter-inline">
                        <span>
                          Sufficiency: <b>{Math.round(cropSelectionErp.sufficiency_score * 100)}%</b> (Req: 70%)
                        </span>
                        <div className="suff-bar-track">
                          <div
                            className="suff-bar-fill"
                            style={{ width: `${Math.round(cropSelectionErp.sufficiency_score * 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                    <div className="erp-weights-pill-grid">
                      {cropSelectionErp.weights.map((w) => (
                        <div key={w.attribute} className="erp-weight-chip">
                          <div className="ewc-top">
                            <span>{w.label}</span>
                            <strong>w = {w.weight.toFixed(2)}</strong>
                          </div>
                          <small>{w.value}</small>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="top-crops-grid">
                  {topCrops.map((item, index) => {
                    const cleanName = item.crop.split(' (')[0]
                    const isSelected = selectedCrop.toLowerCase() === cleanName.toLowerCase()
                    const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉'
                    return (
                      <div
                        key={item.crop}
                        className={`crop-rec-card ${isSelected ? 'selected' : ''}`}
                        onClick={() => setSelectedCrop(cleanName)}
                      >
                        <div className="crop-card-top">
                          <span className="rank-badge">
                            {medal} Rank #{index + 1}
                          </span>
                          <span className="suitability-pill">{item.suitability_score}% Match</span>
                        </div>
                        <div className="crop-icon-title">
                          <span className="crop-big-icon">{item.icon}</span>
                          <div>
                            <h3>{item.crop}</h3>
                            <small>{item.variety || `Duration: ${item.growth_duration_days}`}</small>
                          </div>
                        </div>
                        <p className="crop-reason">{item.reason}</p>

                        <div className="why-crop-box">
                          <strong>Why {cleanName}?</strong>
                          <ul>
                            {(item.why_this_crop || [
                              '✓ Suitable soil',
                              '✓ Suitable climate',
                              '✓ Good seasonal suitability',
                              '✓ Fits farmer budget',
                            ]).map((chk, i) => (
                              <li key={i}>{chk}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="crop-mini-specs">
                          <div>
                            <span>Seasonal Water</span>
                            <strong>{item.water_mm_season} mm</strong>
                          </div>
                          <div>
                            <span>Base NPK</span>
                            <strong>
                              {item.base_npk_kg_ha.N}:{item.base_npk_kg_ha.P}:{item.base_npk_kg_ha.K} kg/ha
                            </strong>
                          </div>
                        </div>
                        <button
                          type="button"
                          className={isSelected ? 'primary-cta-btn full-w' : 'secondary-cta-btn full-w'}
                          onClick={(e) => {
                            e.stopPropagation()
                            handleSelectCropAndAnalyze(item.crop)
                          }}
                        >
                          {isSelected
                            ? `View ${cleanName} Management Plan & Calendar →`
                            : `Select ${cleanName} →`}
                        </button>
                      </div>
                    )
                  })}
                </div>

                <div className="wf-footer-between">
                  <button
                    type="button"
                    className="secondary-cta-btn"
                    onClick={() => setActivePage('farm')}
                  >
                    ← Back to Farm Setup
                  </button>
                  <button
                    type="button"
                    className="primary-cta-btn"
                    onClick={() => handleSelectCropAndAnalyze(selectedCrop)}
                  >
                    Continue with {selectedCrop} to Crop Management Plan →
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================
              MODULE 3: 📅 CROP MANAGEMENT PLAN & SMART CROP CALENDAR
             ============================================================ */}
          {activePage === 'analysis' && (
            <div className="page-card-container">
              <div className="wireframe-card">
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">Module 3 • Crop Management Plan & Smart Crop Calendar</span>
                    <h1>
                      {selectedCrop} — Complete Growing Plan & Smart Calendar
                    </h1>
                    <p>
                      Knowledge & resource guide for growing <strong>{selectedCrop}</strong> across{' '}
                      <strong>{farm.area_hectares} hectares</strong> in{' '}
                      <strong>{farm.village_name}, {farm.district_name}</strong>.
                    </p>
                  </div>
                  <span className="status-ok-badge">
                    {cropOverview?.suitability_score ?? 94}% Suitability Match ✓
                  </span>
                </div>

                {/* 1. 🌱 CROP OVERVIEW */}
                {cropOverview && (
                  <section className="cmp-section">
                    <h2 className="cmp-title">1. 🌱 Crop Overview</h2>
                    <div className="overview-grid-4">
                      <div className="ov-item">
                        <span>Crop & Variety</span>
                        <strong>
                          {cropOverview.icon} {cropOverview.crop_name}
                        </strong>
                        <small>{cropOverview.recommended_variety}</small>
                      </div>
                      <div className="ov-item">
                        <span>Suitable Season & Duration</span>
                        <strong>{cropOverview.suitable_season}</strong>
                        <small>Duration: {cropOverview.crop_duration}</small>
                      </div>
                      <div className="ov-item">
                        <span>Expected Harvest Yield</span>
                        <strong>{cropOverview.expected_total_yield}</strong>
                        <small>{cropOverview.expected_yield_per_ha}</small>
                      </div>
                      <div className="ov-item">
                        <span>Suitable Soil & Temperature</span>
                        <strong>{cropOverview.suitable_soil_type}</strong>
                        <small>Temp Range: {cropOverview.temperature_range}</small>
                      </div>
                    </div>
                  </section>
                )}

                {/* 2. 📅 SMART DAY-BY-DAY CROP CALENDAR */}
                <section className="cmp-section">
                  <h2 className="cmp-title">
                    2. 📅 Smart Crop Calendar & Stage Monitoring ({selectedCrop})
                  </h2>
                  <div className="stages-table-wrapper">
                    <table className="cmp-table">
                      <thead>
                        <tr>
                          <th>Timeline</th>
                          <th>Growth Phase</th>
                          <th>Key Agronomic Tasks</th>
                          <th>🔍 What to Monitor at This Stage</th>
                        </tr>
                      </thead>
                      <tbody>
                        {smartDayCalendar.map((row, idx) => (
                          <tr key={idx}>
                            <td>
                              <span className="cal-week-badge">{row.days}</span>
                            </td>
                            <td>
                              <strong>{row.phase}</strong>
                            </td>
                            <td>{row.action}</td>
                            <td className="risk-cell">{row.monitor}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {/* 3. 💧 RESOURCE, WATER & NPK FERTILIZER REQUIREMENTS */}
                <section className="cmp-section">
                  <h2 className="cmp-title">3. 💧 Resource, Water & NPK Fertilizer Plan</h2>

                  {resourceReq && (
                    <div className="overview-grid-4" style={{ marginBottom: '12px' }}>
                      <div className="ov-item">
                        <span>Seed Quantity & Spacing</span>
                        <strong>{resourceReq.seed_quantity}</strong>
                        <small>Spacing: {resourceReq.spacing}</small>
                      </div>
                      <div className="ov-item">
                        <span>Irrigation Frequency</span>
                        <strong>{resourceReq.irrigation_frequency}</strong>
                        <small>Source: {farm.water_source}</small>
                      </div>
                      <div className="ov-item">
                        <span>Labour Requirement</span>
                        <strong>{resourceReq.labour_requirement}</strong>
                        <small>Land prep through harvest</small>
                      </div>
                      <div className="ov-item">
                        <span>Estimated Cost vs. Budget</span>
                        <strong>{resourceReq.total_estimated_cost}</strong>
                        <small>
                          Budget: {resourceReq.farmer_budget} ({resourceReq.budget_status})
                        </small>
                      </div>
                    </div>
                  )}

                  <div className="analysis-two-col">
                    {waterPlan && (
                      <div className="analysis-panel water-panel">
                        <div className="ap-header">
                          <span>💧 Daily & Seasonal Water Requirement</span>
                          <h3>{waterPlan.total_farm_liters_per_day.toLocaleString()} Liters / Day</h3>
                          <small>
                            For {farm.area_hectares} ha ({waterPlan.liters_per_ha_per_day.toLocaleString()} L/ha/day •{' '}
                            {waterPlan.daily_stage_need_mm} mm/day)
                          </small>
                        </div>
                        <ul className="ap-list">
                          <li>
                            <strong>Seasonal Crop Water Need:</strong> {waterPlan.seasonal_water_mm} mm total
                          </li>
                          <li>
                            <strong>Recommended Irrigation Method:</strong> {waterPlan.recommended_method}
                          </li>
                          <li>
                            <strong>Available Water Source:</strong> {waterPlan.water_source_used}
                          </li>
                        </ul>
                        <div className="ap-guidance-box">
                          <strong>Rain-Adjusted Irrigation Schedule:</strong>
                          <p>{waterPlan.schedule_guidance}</p>
                        </div>
                      </div>
                    )}

                    {fertPlan && (
                      <div className="analysis-panel fert-panel">
                        <div className="ap-header">
                          <span>🧪 Soil-Adjusted NPK Fertilizer Plan</span>
                          <h3>
                            N: {fertPlan.nitrogen_n_kg_ha} • P: {fertPlan.phosphorus_p_kg_ha} • K:{' '}
                            {fertPlan.potassium_k_kg_ha} kg/ha
                          </h3>
                          <small>
                            Total for {farm.area_hectares} ha: N={fertPlan.total_farm_npk_kg.N_kg} kg, P=
                            {fertPlan.total_farm_npk_kg.P_kg} kg, K={fertPlan.total_farm_npk_kg.K_kg} kg
                          </small>
                        </div>
                        <ul className="ap-list">
                          <li>
                            <strong>Dataset Soil Baseline:</strong> {fertPlan.village_soil_status}
                          </li>
                          <li>
                            <strong>Recommended Products:</strong> {fertPlan.recommended_products}
                          </li>
                          <li>
                            <strong>pH Amendment:</strong> {fertPlan.ph_amendment}
                          </li>
                        </ul>
                        <div className="ap-guidance-box">
                          <strong>Split Fertilizer Schedule:</strong>
                          <p>{fertPlan.application_schedule}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                {/* 4. 🧑‍🌾 COMPLETE STAGE-BY-STAGE GROWING PLAN */}
                {growingStages.length > 0 && (
                  <section className="cmp-section">
                    <h2 className="cmp-title">
                      4. 🧑‍🌾 Detailed Stage-by-Stage Growing Plan
                    </h2>
                    <div className="stages-table-wrapper">
                      <table className="cmp-table">
                        <thead>
                          <tr>
                            <th>Stage</th>
                            <th>What to Do</th>
                            <th>What the Crop Needs</th>
                            <th>What to Monitor</th>
                            <th>Important Risks</th>
                            <th>Expected Condition</th>
                          </tr>
                        </thead>
                        <tbody>
                          {growingStages.map((st) => (
                            <tr key={st.stage_num}>
                              <td>
                                <strong>
                                  Stage {st.stage_num}: {st.stage}
                                </strong>
                              </td>
                              <td>{st.what_to_do}</td>
                              <td>{st.what_crop_needs}</td>
                              <td>{st.what_to_monitor}</td>
                              <td className="risk-cell">{st.important_risks}</td>
                              <td>{st.expected_condition}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                )}

                {/* 5. 🚨 RISK & PREVENTION */}
                {riskPrev && (
                  <section className="cmp-section">
                    <h2 className="cmp-title">5. 🚨 Proactive Risk & Prevention Profile</h2>
                    <div className="overview-grid-4">
                      <div className="ov-item">
                        <span>Common Diseases</span>
                        <strong>{riskPrev.diseases[0]}</strong>
                        <small>{riskPrev.diseases.slice(1).join(' • ')}</small>
                      </div>
                      <div className="ov-item">
                        <span>Common Pests</span>
                        <strong>{riskPrev.pests[0]}</strong>
                        <small>{riskPrev.pests.slice(1).join(' • ')}</small>
                      </div>
                      <div className="ov-item">
                        <span>Abiotic Stress Risks</span>
                        <strong>Weather & Moisture</strong>
                        <small>{riskPrev.abiotic_stress.join(' • ')}</small>
                      </div>
                      <div className="ov-item">
                        <span>Preventive Protocol</span>
                        <strong>Canopy & Root Care</strong>
                        <small>{riskPrev.prevention}</small>
                      </div>
                    </div>
                  </section>
                )}

                <div className="wf-footer-between">
                  <button
                    type="button"
                    className="secondary-cta-btn"
                    onClick={() => setActivePage('crop')}
                  >
                    ← Back to Crop Recommendation
                  </button>
                  <button
                    type="button"
                    className="primary-cta-btn"
                    onClick={() => setActivePage('monitoring')}
                  >
                    Proceed to Continuous Crop Monitoring (📊 Module 4) →
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================
              MODULE 4: 📊 CONTINUOUS CROP MONITORING & RISK ALERTS
             ============================================================ */}
          {activePage === 'monitoring' && (
            <div className="page-card-container">
              <div className="wireframe-card">
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">Module 4 • Continuous Crop Monitoring & Event Alerts</span>
                    <h1>{selectedCrop} — Live Field Monitoring & Alerts</h1>
                    <p>
                      Tracks the field information that helps us give timely, practical guidance.
                    </p>
                  </div>
                  <div className="inline-stage-select">
                    <label>
                      <strong>Active Growth Stage:</strong>
                    </label>
                    <select
                      value={cropStage}
                      onChange={(e) => {
                        const nextStage = e.target.value
                        setCropStage(nextStage)
                        runAdieDecisionEngine(null, diseaseReport, selectedCrop, nextStage)
                      }}
                    >
                      <option value="seedling">Seedling</option>
                      <option value="vegetative">Vegetative</option>
                      <option value="flowering">Flowering</option>
                      <option value="fruiting">Fruiting</option>
                    </select>
                  </div>
                </div>

                {/* 🔔 IMPORTANT EVENT / RISK ALERTS */}
                <div className="alerts-stack">
                  <div className="alerts-header-row">
                    <strong>🔔 Active Field Events & Risk Alerts</strong>
                    <small>
                      Alerts notify you about environmental or crop-stage risks; a suggested action is prepared when you ask for help.
                    </small>
                  </div>
                  {activeAlerts.map((al, i) => (
                    <div key={i} className={`risk-alert-banner ${al.level}`}>
                      <div>
                        <strong>{al.title}</strong>
                        <p>{al.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* 🔍 9 MONITORED PARAMETERS CONNECTED TO ERP */}
                <section className="cmp-section">
                  <h2 className="cmp-title">
                    🔍 Monitored Field Information
                  </h2>
                  <div className="calendar-timeline-grid">
                    {whatToMonitor.map((m, idx) => (
                      <div key={idx} className="calendar-card">
                        <span className="cal-week-badge">✓ Monitored</span>
                        <h4>{m.parameter}</h4>
                        <p>
                          <strong>Current:</strong> {m.status}
                        </p>
                        {viewMode === 'research' && (
                          <small className="muted-erp-note">{m.erp_role}</small>
                        )}
                      </div>
                    ))}
                  </div>
                </section>

                <div className="wf-footer-between">
                  <button
                    type="button"
                    className="secondary-cta-btn"
                    onClick={() => setActivePage('analysis')}
                  >
                    ← Back to Crop Management Plan
                  </button>
                  <button
                    type="button"
                    className="primary-cta-btn"
                    onClick={() => setActivePage('image')}
                  >
                    Inspect Crop Leaves for Disease (📷 Module 5: Disease Detection) →
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================
              MODULE 5: 📷 DISEASE & RISK DETECTION
             ============================================================ */}
          {activePage === 'image' && (
            <div className="page-card-container">
              <div className="wireframe-card">
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">Module 5 • Leaf health check</span>
                    <h1>Crop Disease & Symptom Detection — {selectedCrop}</h1>
                    <p>
                      Upload a leaf image or select a field sample. We will identify visible symptoms and then explain the most suitable next step.
                    </p>
                  </div>
                </div>

                <div className="upload-dropzone">
                  <label className="upload-label">
                    <input type="file" accept="image/*" onChange={handleImageUpload} hidden />
                    <span className="upload-icon">📷</span>
                    <strong>[ Upload Leaf Image ] — POST /api/evidence/image</strong>
                    <small>
                      {uploadedImageName
                        ? `Image checked: ${uploadedImageName}`
                        : 'Click to upload a crop leaf photo or select one of the field inspection samples below'}
                    </small>
                  </label>
                  {uploadedImagePreview && (
                    <img
                      src={uploadedImagePreview}
                      alt="Uploaded crop leaf"
                      className="leaf-preview-img"
                    />
                  )}
                </div>

                <h3 className="sub-heading">Or Select a Field Canopy Inspection Sample:</h3>
                <div className="sample-cards-grid">
                  {LEAF_INSPECTION_SAMPLES.map((samp) => (
                    <div
                      key={samp.id}
                      className={`sample-card ${selectedSampleId === samp.id ? 'selected' : ''}`}
                      onClick={() => handleSelectSamplePreset(samp)}
                    >
                      <div className="sample-top">
                        <strong>{samp.title}</strong>
                        <span className={`pill-badge ${samp.detected ? 'warn' : 'ok'}`}>
                          {samp.health_label}
                        </span>
                      </div>
                      <p>{samp.summary}</p>
                      <small>
                        Severity: <b>{samp.severity.toUpperCase()}</b> • Confidence:{' '}
                        <b>{samp.confidence}%</b>
                      </small>
                    </div>
                  ))}
                </div>

                <div className="detection-result-banner">
                  <div>
                    <span className="tag-pill">
                      Leaf check result
                    </span>
                    <h3>
                      {diseaseReport.detected ? 'Disease Detected: ' : ''}
                      {diseaseReport.disease_name}
                    </h3>
                    <p>{diseaseReport.summary}</p>
                    <p className="detected-treatment-line">
                      <strong>Confidence:</strong> {diseaseReport.confidence}% •{' '}
                      <strong>Severity:</strong> {diseaseReport.severity.toUpperCase()} •{' '}
                      <strong>Growth Stage:</strong> {cropStage.toUpperCase()}
                    </p>
                  </div>
                  <div className="rd-buttons">
                    <button
                      type="button"
                      className="secondary-cta-btn"
                      onClick={() => setActivePage('monitoring')}
                    >
                      ← Back to Monitoring
                    </button>
                    <button
                      type="button"
                      className="primary-cta-btn"
                      disabled={busy}
                      onClick={() =>
                        runAdieDecisionEngine('recommend', diseaseReport, selectedCrop, cropStage)
                      }
                    >
                      {busy
                        ? 'Preparing your suggested action…'
                        : 'Continue to Suggested Action (🧠 Module 6) →'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================
              MODULE 6: 🧠 SUGGESTED ACTION
             ============================================================ */}
          {activePage === 'recommend' && (
            <div className="page-card-container">
              <div className="wireframe-card">
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">
                      Module 6 • Evidence check, action suggestion & explanation
                    </span>
                    <h1>
                      Intelligent Decision — {selectedCrop} ({cropStage})
                    </h1>
                    <p>
                      Checks the available information, removes unsuitable options, and suggests the safest practical action.
                    </p>
                  </div>
                  <div className="rd-buttons">
                    {weatherAgeHours <= 24 ? (
                      <button
                        type="button"
                        className="secondary-cta-btn"
                        onClick={() => {
                          setWeatherAgeHours(48.0)
                          runAdieDecisionEngine(null, diseaseReport, selectedCrop, cropStage, 48.0)
                        }}
                      >
                        Simulate Stale Humidity (48h)
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="primary-cta-btn"
                        onClick={() => {
                          setWeatherAgeHours(1.0)
                          runAdieDecisionEngine(null, diseaseReport, selectedCrop, cropStage, 1.0)
                        }}
                      >
                        ↻ Refresh Weather Evidence
                      </button>
                    )}
                  </div>
                </div>

                {weatherAgeHours > 24 && (
                  <div className="stale-warning-banner">
                    <strong>⚠ Fresh weather information required:</strong> Current humidity and rain information is 48 hours old. Refresh it before confirming an action.
                  </div>
                )}

                {/* 🔬 4. EVIDENCE READINESS DASHBOARD (ERP VISUALIZED) */}
                <section className="cmp-section">
                  <div className="wf-header-split">
                    <div>
                      <h2 className="cmp-title">🔬 Information Readiness</h2>
                      <small style={{ color: '#4b6556' }}>
                        {overallReadinessPct >= 68
                          ? '✓ The system has sufficient reliable evidence to make this decision.'
                          : '⚠ Evidence readiness is below optimal threshold; refresh stale weather telemetry.'}
                      </small>
                    </div>
                    <span className={`status-ok-badge ${overallReadinessPct < 68 ? 'warn-badge' : ''}`}>
                      Decision Readiness: {overallReadinessPct}% (Required: 68%)
                    </span>
                  </div>

                  <div className="evidence-readiness-grid">
                    {evidenceReadinessBars.map((eb) => (
                      <div key={eb.label} className="er-bar-card">
                        <div className="er-bar-top">
                          <strong>{eb.label}</strong>
                          <span>
                            {viewMode === 'research' && (
                              <small className="muted-erp-note">Importance {Math.round(eb.weight * 100)}% • </small>
                            )}
                            <b>{eb.pct}%</b>
                          </span>
                        </div>
                        <div className="suff-bar-track">
                          <div
                            className="suff-bar-fill"
                            style={{
                              width: `${eb.pct}%`,
                              background: eb.pct < 65 ? '#d97706' : '#1f6e43',
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* 🧠 5. PRIMARY ADIE RECOMMENDATION + NATURAL-LANGUAGE EXPLANATION */}
                <div className="treatment-hero-box">
                  <span className="rec-overline">
                    🧠 Recommended action
                  </span>
                  <h2>
                    🥇{' '}
                    {diseaseReport.detected
                      ? activeRecommendedAction.name
                      : 'Continue Preventive Bio-Shield & Scheduled Drip Fertigation'}
                  </h2>
                  <p>{activeRecommendedAction.description}</p>

                  {/* EXPLICIT "WHY THIS WAS SELECTED" EXPLANATION BOX */}
                  <div className="why-selected-explanation">
                    <strong>🧠 Why this action was selected:</strong>
                    <p>
                      {diseaseReport.detected
                        ? `${activeRecommendedAction.name} was selected because it achieves the highest context-conditioned effectiveness (${activeRecommendedAction.expected_outcome ?? 80}%) for ${diseaseReport.disease_name} under current humidity (${Math.round(env.air_humidity)}%) and rainfall (${Math.round(env.rain_probability)}%) conditions, fits your ₹${Number(farm.budget || 50000).toLocaleString()} budget (Cost: ₹${activeRecommendedAction.estimated_cost ?? 350}), and satisfies all A2 safety/weather constraints.`
                        : `No foliar disease was detected (${diseaseReport.confidence}% confidence), so AgroNexus avoids unnecessary chemical sprays and maintains preventive crop care.`}
                    </p>
                  </div>

                  <div className="treatment-metrics-row">
                    <div className="tm-box">
                      <span>Expected Effectiveness</span>
                      <strong>
                        {diseaseReport.detected
                          ? activeRecommendedAction.expected_outcome ?? 80
                          : 94}
                        %
                      </strong>
                    </div>
                    <div className="tm-box">
                      <span>Decision Readiness</span>
                      <strong>{overallReadinessPct}%</strong>
                    </div>
                    <div className="tm-box">
                      <span>Estimated Cost</span>
                      <strong>₹{activeRecommendedAction.estimated_cost ?? 350}</strong>
                    </div>
                    <div className="tm-box">
                      <span>Execution Boundary</span>
                      <strong>Farmer Executes Externally</strong>
                    </div>
                  </div>
                </div>

                {/* 🔄 6. "WHY DID THE RECOMMENDATION CHANGE?" (VISIBLE WHEN ADAPTATION OCCURRED) */}
                {(outcomeResult || demoResult) && (
                  <div className="why-changed-card">
                    <div className="wc-header">
                      <span className="tag-pill">🔄 Adaptive Shift Explanation</span>
                      <h3>Why Did the Recommendation Change?</h3>
                    </div>
                    <div className="wc-comparison-row">
                      <div className="wc-col prev">
                        <span>Initial Cycle Recommendation</span>
                        <strong>Apply locally approved fungicide in a dry window</strong>
                        <small>Prior Expected: 80% → Realized in Rain/Humidity: 40–45%</small>
                      </div>
                      <div className="eo-arrow">⇒</div>
                      <div className="wc-col curr">
                        <span>Adapted Recommendation Today</span>
                        <strong>
                          {outcomeResult?.suggested_new_treatment?.name ||
                            demoResult?.summary?.subsequent_selected_action ||
                            'Apply systemic bio-fungicide and canopy sanitation'}
                        </strong>
                        <small>Rain-fast systemic protection + canopy sanitation (Expected: 75%)</small>
                      </div>
                    </div>
                    <div className="wc-reasons-grid">
                      <div>↑ <b>Humidity became more important</b> for future decisions</div>
                      <div>↑ <b>Rain probability became more important</b> for future decisions</div>
                      <div>↓ <b>Historical effectiveness of Contact Spray dropped</b> in wet contexts</div>
                      <div>↑ <b>Systemic + Sanitation ranked #1</b> under high humidity/rain</div>
                    </div>
                    <div className="wc-status-strip">
                      <span>Information priorities updated: <b>Yes</b></span>
                      <span>Action guidance updated: <b>Yes</b></span>
                    </div>
                  </div>
                )}

                {/* CANDIDATE ALTERNATIVES TABLE (A2 & A3) */}
                <section className="cmp-section">
                  <h2 className="cmp-title">⚖️ Other suitable actions considered</h2>
                  <div className="alternatives-list">
                    {(
                      outcomeResult?.updated_alternatives ||
                      decisionResult?.alternatives || [
                        {
                          action_id: '1',
                          name: 'Apply locally approved fungicide in a dry window',
                          description: 'Use a contact/broad-spectrum product during a dry window.',
                          feasible: true,
                          expected_outcome: 80,
                          estimated_cost: 350,
                        },
                        {
                          action_id: '2',
                          name: 'Apply systemic bio-fungicide and canopy sanitation',
                          description:
                            'Use rain-fast systemic protection with lower-leaf pruning; resilient under humid or moderate rain windows.',
                          feasible: true,
                          expected_outcome: 75,
                          estimated_cost: 260,
                        },
                        {
                          action_id: '3',
                          name: 'Remove visibly affected leaves',
                          description: 'Sanitize canopy by removing visibly infected foliage.',
                          feasible: true,
                          expected_outcome: 65,
                          estimated_cost: 80,
                        },
                      ]
                    ).map((cand, idx) => (
                      <div
                        key={cand.action_id || idx}
                        className={`alt-option-card ${idx === 0 ? 'top-choice' : ''}`}
                      >
                        <div>
                          <div className="alt-title-row">
                            <strong>
                              #{idx + 1} {cand.name}
                            </strong>
                            <span className={`pill-badge ${cand.feasible ? 'ok' : 'warn'}`}>
                              {cand.feasible ? 'Feasible (Passed A2)' : 'Pruned by A2 Constraint'}
                            </span>
                          </div>
                          <p>{cand.description}</p>
                        </div>
                        <div className="alt-stats">
                          <span>
                            Expected result: <b>{cand.expected_outcome}%</b>
                          </span>
                          <span>
                            Cost: <b>₹{cand.estimated_cost}</b>
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                <div className="wf-footer-between">
                  <button
                    type="button"
                    className="secondary-cta-btn"
                    onClick={() => setActivePage('image')}
                  >
                    ← Back to Disease Detection
                  </button>
                  <button
                    type="button"
                    className="primary-cta-btn"
                    onClick={() => setActivePage('feedback')}
                  >
                    Farmer Executes Externally → Report Outcome & View Learning (🔄 Module 7) →
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================
              MODULE 7: 🔄 OUTCOME REPORTING & ADAPTIVE LEARNING (ACER + CNDA + R(a,c) + ERP + HISTORY)
             ============================================================ */}
          {activePage === 'feedback' && (
            <div className="page-card-container">
              <div className="analysis-two-col">
                {/* LEFT COLUMN: STAGE 11 OUTCOME REPORTING FORM */}
                <form className="wireframe-card" onSubmit={handleSubmitFeedback}>
                  <div className="wf-header">
                    <span className="tag-pill">Step 7 • Tell us what happened</span>
                      <h1>How did the crop respond?</h1>
                    <p>
                        Your answer helps AgroNexus give better guidance the next time you grow this crop.
                    </p>
                  </div>

                  <div className="previously-received-box">
                    <span>Action you followed</span>
                    <h3>
                      {decisionResult?.recommendation?.name ||
                        'Apply locally approved fungicide in a dry window'}
                    </h3>
                    <p>
                      Expected result:{' '}
                      <strong>{decisionResult?.recommendation?.expected_outcome ?? 80}%</strong>
                    </p>
                  </div>

                  <div className="wf-field">
                    <div className="slider-label-row">
                      <label>How well did it work?</label>
                      <strong>{feedbackForm.observed_outcome}%</strong>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      className="wf-slider"
                      value={feedbackForm.observed_outcome}
                      onChange={(e) =>
                        setFeedbackForm((prev) => ({
                          ...prev,
                          observed_outcome: Number(e.target.value),
                        }))
                      }
                    />
                  </div>

                  <div className="wf-field">
                    <label>What did you notice?</label>
                    <div className="radio-group-row">
                      {[
                        { value: 'improved', label: 'Improved' },
                        { value: 'unchanged', label: 'Unchanged' },
                        { value: 'worse', label: 'Worse' },
                      ].map((opt) => (
                        <label
                          key={opt.value}
                          className={`radio-pill ${
                            feedbackForm.outcome_status === opt.value ? 'selected' : ''
                          }`}
                        >
                          <input
                            type="radio"
                            name="outcome_status"
                            value={opt.value}
                            checked={feedbackForm.outcome_status === opt.value}
                            onChange={(e) => {
                              const val = e.target.value
                              const defaultObs =
                                val === 'improved' ? 82 : val === 'unchanged' ? 65 : 40
                              setFeedbackForm((prev) => ({
                                ...prev,
                                outcome_status: val,
                                observed_outcome: defaultObs,
                              }))
                            }}
                          />
                          <span>
                            {feedbackForm.outcome_status === opt.value ? '●' : '○'} {opt.label}
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="wf-field">
                    <label className="check-inline">
                      <input
                        type="checkbox"
                        checked={feedbackForm.rain_after_spray}
                        onChange={(e) =>
                          setFeedbackForm((prev) => ({
                            ...prev,
                            rain_after_spray: e.target.checked,
                          }))
                        }
                      />
                      <span>
                        Rain or very humid weather came after the treatment
                      </span>
                    </label>
                  </div>

                  <div className="wf-field">
                    <label>Anything else to share?</label>
                    <textarea
                      rows="2"
                      value={feedbackForm.notes}
                      onChange={(e) =>
                        setFeedbackForm((prev) => ({ ...prev, notes: e.target.value }))
                      }
                    />
                  </div>

                  <button type="submit" className="primary-cta-btn full-w" disabled={busy}>
                    {busy ? 'Saving your update…' : 'Save my update →'}
                  </button>
                </form>

                {/* RIGHT COLUMN: STAGE 12, 13 & 14 (ACER + CNDA + JOINT UPDATE — FARMER vs RESEARCH VIEW) */}
                <div className="wireframe-card">
                  <div className="wf-header-split">
                    <div>
                      <span className="tag-pill">Learning from your results</span>
                      <h1>AgroNexus Adaptive Learning</h1>
                    </div>
                    <span className="status-ok-badge">
                      👨‍🌾 Your farm learning
                    </span>
                  </div>

                  {/* EXPECTED -> OBSERVED -> Δ */}
                  <div className="exp-obs-comparison">
                    <div className="eo-box">
                      <span>Expected</span>
                      <strong>{outcomeResult?.expected_outcome ?? 80}%</strong>
                    </div>
                    <div className="eo-arrow">→</div>
                    <div className="eo-box observed">
                      <span>Observed</span>
                      <strong>
                        {outcomeResult?.observed_outcome ?? feedbackForm.observed_outcome}%
                      </strong>
                    </div>
                    <div className="eo-arrow">⇒</div>
                    <div className="eo-box">
                      <span>Difference</span>
                      <strong className="neg-diff">
                        {outcomeResult?.deviation ?? feedbackForm.observed_outcome - 80}%
                      </strong>
                    </div>
                  </div>

                  {/* FARMER MODE vs RESEARCH MODE DISPLAY OF CNDA & JOINT UPDATE */}
                  {viewMode === 'farmer' ? (
                    <div className="farmer-friendly-learning-box">
                      <h3>👨‍🌾 What we learned for your farm</h3>
                      <p>
                        ⚠️ <strong>Weather affected the result:</strong> High humidity ({Math.round(env.air_humidity)}%) and rainfall ({Math.round(env.rain_probability)}%) may have reduced the result from 80% to {outcomeResult?.observed_outcome ?? feedbackForm.observed_outcome}%.
                      </p>
                      <p>
                        ✅ <strong>What will change next time:</strong>
                      </p>
                      <ul className="ap-list">
                        <li>
                          <strong>1. Smarter Weather Checks:</strong> AgroNexus now gives higher priority to fresh humidity and rain forecasts before recommending any foliar spray.
                        </li>
                        <li>
                          <strong>2. Better Action Selection:</strong> Next time your {selectedCrop} crop has {diseaseReport.disease_name.split(' (')[0]} during humid or rainy weather, AgroNexus automatically switches to <strong>{outcomeResult?.suggested_new_treatment?.name || 'Apply systemic bio-fungicide and canopy sanitation'}</strong> (Expected: 75%).
                        </li>
                      </ul>
                    </div>
                  ) : (
                    <>
                      {/* RESEARCH VIEW: ACER + CNDA SPEARMAN CORRELATIONS */}
                      <div className="erp-explain-card">
                        <strong>
                          Stage 12 & 13 — ACER #{outcomeResult?.acer_id ? outcomeResult.acer_id.slice(0, 6).toUpperCase() : '105'} & BallTree CNDA Attribution (N ≥ 5 Gated)
                        </strong>
                        <div className="cnda-bars-list">
                          {cndaDisplayRows.slice(0, 4).map((row) => {
                            const rho = Number(row.rho_spearman ?? row.association_value ?? 0)
                            const isStrong = Math.abs(rho) >= 0.35 || row.selected
                            return (
                              <div key={row.factor} className="cnda-factor-row">
                                <div className="cnda-row-top">
                                  <strong>{row.factor.replace(/_/g, ' ')}</strong>
                                  <span>
                                    ρ = <b>{rho.toFixed(2)}</b> • N = <b>{demoResult ? 5 : 5}</b> •{' '}
                                    <span className={`pill-badge ${isStrong ? 'warn' : 'ok'}`}>
                                      {isStrong ? 'Attributed → Update ERP' : 'Weak'}
                                    </span>
                                  </span>
                                </div>
                                <div className="suff-bar-track">
                                  <div
                                    className="suff-bar-fill"
                                    style={{
                                      width: `${Math.min(100, Math.round(Math.abs(rho) * 100))}%`,
                                      background: isStrong ? '#d97706' : '#94a3b8',
                                    }}
                                  />
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>

                      {/* RESEARCH VIEW: SINGLE-ACER JOINT UPDATE SUMMARY */}
                      <div className="erp-explain-card">
                        <strong>Stage 14 — Single-ACER Joint Adaptation (R(a,c) + ERP v1 → v2)</strong>
                        <ul className="ap-list">
                          <li>
                            <strong>R(a,c) Wet Context Update:</strong> Contact Fungicide 80% → 48% ↓ | Systemic + Sanitation 75% (Rank #1)
                          </li>
                          <li>
                            <strong>ERP Weight Update:</strong> Rain Probability <code>0.160 → 0.192 ↑</code> • Air Humidity <code>0.120 → 0.149 ↑</code>
                          </li>
                        </ul>
                      </div>
                    </>
                  )}

                  <div className="new-suggested-treatment-card">
                    <span className="tag-pill">Next time you need help</span>
                    <h3>
                      🥇{' '}
                      {outcomeResult?.suggested_new_treatment?.name ||
                        'Apply systemic bio-fungicide and canopy sanitation'}
                    </h3>
                    <div className="rd-buttons" style={{ marginTop: '10px' }}>
                      <button
                        type="button"
                        className="primary-cta-btn"
                        onClick={() =>
                          runAdieDecisionEngine('recommend', diseaseReport, selectedCrop, cropStage)
                        }
                      >
                        Use updated guidance for the next decision (🧠 Module 6) →
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Learning history */}
              <div className="wireframe-card" style={{ marginTop: '18px' }}>
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">Your farm history</span>
                    <h2>Step-by-step learning history</h2>
                    <p>
                      A clear history of how field results improve future crop guidance.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="secondary-cta-btn"
                    onClick={() => setActivePage('benchmark')}
                  >
                    See how guidance improves →
                  </button>
                </div>

                {/* VISUAL LEARNING CHAIN */}
                <div className="learning-chain-flow">
                  <div className="lc-step">
                    <span>Suggested action</span>
                    <strong>Expected result: {outcomeResult?.expected_outcome ?? 80}%</strong>
                  </div>
                  <span className="lc-arrow">→</span>
                  <div className="lc-step">
                    <span>Your result</span>
                    <strong>Observed result: {outcomeResult?.observed_outcome ?? feedbackForm.observed_outcome}%</strong>
                  </div>
                  <span className="lc-arrow">→</span>
                  <div className="lc-step warn">
                    <span>Result recorded</span>
                    <strong>Difference: {outcomeResult?.deviation ?? feedbackForm.observed_outcome - 80}%</strong>
                  </div>
                  <span className="lc-arrow">→</span>
                  <div className="lc-step">
                    <span>What affected it</span>
                    <strong>Rain and humidity</strong>
                  </div>
                  <span className="lc-arrow">→</span>
                  <div className="lc-step ok">
                    <span>Next time</span>
                    <strong>Future guidance updated</strong>
                  </div>
                </div>

                {acerLedger?.acer_records?.length > 0 && (
                  <div className="stages-table-wrapper">
                    <table className="cmp-table">
                      <thead>
                        <tr>
                          <th>Action followed</th>
                          <th>Expected</th>
                          <th>Your result</th>
                          <th>Difference</th>
                        </tr>
                      </thead>
                      <tbody>
                        {acerLedger.acer_records.slice(0, 6).map((rec) => (
                          <tr key={rec.acer_id}>
                            <td>
                              <strong>{rec.action_name}</strong>
                            </td>
                            <td>{rec.expected_outcome}%</td>
                            <td>{rec.observed_outcome}%</td>
                            <td className={rec.deviation < 0 ? 'neg-diff' : 'pos-diff'}>
                              <strong>{rec.deviation > 0 ? `+${rec.deviation}` : rec.deviation}%</strong>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ============================================================
              MODULE 8: 🧪 ANALYTICS, CLOSED-LOOP SIMULATION & 4-SYSTEM BENCHMARK LAB
             ============================================================ */}
          {activePage === 'benchmark' && (
            <div className="page-card-container">
              {/* PART 1: LEARNING EXAMPLE */}
              <div className="wireframe-card">
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">Step 8 • See how guidance improves</span>
                    <h1>How AgroNexus improves over time</h1>
                    <p>
                      This example shows how the guidance becomes more useful after several crop results are recorded.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="primary-cta-btn"
                    onClick={handleRunMultiCycleSimulation}
                    disabled={busy}
                  >
                    {busy ? 'Preparing example…' : '▶ Show an example'}
                  </button>
                </div>

                {demoResult && (
                  <div className="sim-results-panel">
                    <div className="overview-grid-4">
                      <div className="ov-item">
                        <span>First suggestion</span>
                        <strong>{demoResult.summary.initial_selected_action}</strong>
                        <small>Before learning from results</small>
                      </div>
                      <div className="ov-item">
                        <span>Later suggestion</span>
                        <strong>{demoResult.summary.subsequent_selected_action}</strong>
                        <small>After learning from results ✓</small>
                      </div>
                      <div className="ov-item">
                        <span>What became more important</span>
                        <strong>
                          Fresh weather checks
                        </strong>
                        <small>
                          Rain and humidity receive more attention when they affect results
                        </small>
                      </div>
                      <div className="ov-item">
                        <span>Important field conditions</span>
                        <strong>{demoResult.summary.cnda_selected_factors.join(', ').replaceAll('_', ' ')}</strong>
                        <small>Found from recorded crop results</small>
                      </div>
                    </div>

                    <div className="stages-table-wrapper" style={{ marginTop: '12px' }}>
                      <table className="cmp-table">
                        <thead>
                          <tr>
                            <th>Example</th>
                            <th>Suggested action</th>
                            <th>Expected</th>
                            <th>Observed</th>
                            <th>Difference</th>
                            <th>What was learned</th>
                            <th>Guidance changed?</th>
                          </tr>
                        </thead>
                        <tbody>
                          {demoResult.cycles.map((c) => (
                            <tr key={c.cycle}>
                              <td>
                                <strong>Example {c.cycle}</strong>
                              </td>
                              <td>{c.selected_action}</td>
                              <td>{c.expected_outcome}%</td>
                              <td>{c.observed_outcome}%</td>
                              <td className="neg-diff">
                                <strong>{c.deviation}%</strong>
                              </td>
                              <td>
                                {c.cnda.selected_factors?.length
                                  ? 'Weather conditions were important'
                                  : 'More results are needed'}
                              </td>
                              <td>
                                {c.erp_update.updated ? (
                                  <span className="pill-badge ok">Yes</span>
                                ) : (
                                  <span className="pill-badge warn">Not yet</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>

              {/* PART 2: PRACTICAL PERFORMANCE REVIEW */}
              <div className="wireframe-card" style={{ marginTop: '18px' }}>
                <div className="wf-header-split">
                  <div>
                    <span className="tag-pill">Step 8 • Practical performance review</span>
                    <h1>Which guidance works best?</h1>
                    <p>
                      This review compares different ways of preparing crop guidance so the most helpful approach can be used.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="primary-cta-btn"
                    onClick={handleRunFourBaselineBenchmark}
                    disabled={busy}
                  >
                    {busy ? 'Preparing review…' : '▶ Compare guidance'}
                  </button>
                </div>

                {benchmarkResult ? (
                  <div className="stages-table-wrapper">
                    <table className="cmp-table">
                      <thead>
                        <tr>
                          <th>Guidance style</th>
                          <th>Information used</th>
                          <th>Helpful result</th>
                          <th>Best-action rate</th>
                          <th>Response time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.values(benchmarkResult.baselines || {}).map((b) => {
                          const isProposed = b.name.includes('B4') || b.name.includes('Proposed')
                          return (
                            <tr
                              key={b.name}
                              style={
                                isProposed
                                  ? { background: '#eef9f1', fontWeight: 700 }
                                  : undefined
                              }
                            >
                              <td>
                                <strong>{getSimpleApproachName(b.name)}</strong>
                              </td>
                              <td>
                                {b.avg_evidence_items_processed} details
                              </td>
                              <td className={isProposed ? 'pos-diff' : ''}>
                                <strong>{b.mean_realized_outcome}%</strong>
                              </td>
                              <td>
                                <strong>{Math.round(b.optimal_action_rate * 100)}%</strong>
                              </td>
                              <td>{b.avg_balltree_query_ms} ms</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="auto-fetched-strip">
                    <span>
                      Click <strong>▶ Run performance review (30 cycles)</strong> above to generate live comparison metrics.
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
