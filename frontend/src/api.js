const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const token = localStorage.getItem('agronexus-access-token')
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...options,
  })
  const body = await response.json()
  if (!response.ok) throw new Error(body.detail || 'Request failed.')
  return body
}

export const api = {
  register: async (data) => {
    const result = await request('/api/auth/register', { method: 'POST', body: JSON.stringify(data) })
    if (result.access_token) localStorage.setItem('agronexus-access-token', result.access_token)
    return result
  },
  login: async (data) => {
    const result = await request('/api/auth/login', { method: 'POST', body: JSON.stringify(data) })
    if (result.access_token) localStorage.setItem('agronexus-access-token', result.access_token)
    return result
  },
  logout: () => localStorage.removeItem('agronexus-access-token'),
  requestPasswordReset: (data) =>
    request('/api/auth/password-reset/request', { method: 'POST', body: JSON.stringify(data) }),
  confirmPasswordReset: (data) =>
    request('/api/auth/password-reset/confirm', { method: 'POST', body: JSON.stringify(data) }),
  getWeather: (latitude, longitude) => request(`/api/weather?latitude=${latitude}&longitude=${longitude}`),
  getHealth: () => request('/api/health'),
  getLocations: (stateName = '', districtName = '', villageName = '') => {
    const params = new URLSearchParams()
    if (stateName) params.set('state_name', stateName)
    if (districtName) params.set('district_name', districtName)
    if (villageName) params.set('village_name', villageName)
    const qs = params.toString()
    return request(`/api/locations${qs ? `?${qs}` : ''}`)
  },
  getCropIntelligence: ({
    state_name = 'Kerala',
    district_name = 'Wayanad',
    village_name = 'Achooranam',
    soil_type = 'loamy',
    water_source = 'Borewell & Rainfed',
    area_hectares = 2.0,
    selected_crop = '',
    crop_stage = 'flowering',
    budget = 50000,
    season = 'Kharif',
  } = {}) => {
    const params = new URLSearchParams({
      state_name: state_name || 'Kerala',
      district_name: district_name || 'Wayanad',
      village_name: village_name || '',
      soil_type: soil_type || 'loamy',
      water_source: water_source || 'Borewell & Rainfed',
      area_hectares: String(area_hectares || 2.0),
      crop_stage: crop_stage || 'flowering',
      budget: String(budget || 50000),
      season: season || 'Kharif',
    })
    if (selected_crop) params.set('selected_crop', selected_crop)
    return request(`/api/crop-intelligence?${params.toString()}`)
  },
  recommendCrops: (data) =>
    request('/api/evidence/recommend-crops', { method: 'POST', body: JSON.stringify(data) }),
  analyzeDiseaseImage: (data) =>
    request('/api/evidence/image', { method: 'POST', body: JSON.stringify(data) }),
  getScoringConfig: () => request('/api/config/scoring'),
  updateScoringConfig: (data) =>
    request('/api/config/scoring', { method: 'PUT', body: JSON.stringify(data) }),
  getErp: (decisionType = 'disease_intervention') =>
    request(`/api/erp/${encodeURIComponent(decisionType)}`),
  createFarm: (data) =>
    request('/api/farms', { method: 'POST', body: JSON.stringify(data) }),
  listFarms: () => request('/api/farms'),
  makeDecision: (data) =>
    request('/api/decisions', { method: 'POST', body: JSON.stringify(data) }),
  listDecisions: (farmId = '') =>
    request(`/api/decisions${farmId ? `?farm_id=${encodeURIComponent(farmId)}` : ''}`),
  getDecisionDetail: (id) => request(`/api/decisions/${encodeURIComponent(id)}`),
  recordOutcome: (id, data) =>
    request(`/api/decisions/${encodeURIComponent(id)}/outcome`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getAcerLedger: (decisionType = 'disease_intervention') =>
    request(`/api/acer?decision_type=${encodeURIComponent(decisionType)}`),
  runClosedLoopDemo: () =>
    request('/api/demo/closed-loop', { method: 'POST' }),
  runBenchmarks: (cycles = 30, seed = 42) =>
    request('/api/benchmarks/run', {
      method: 'POST',
      body: JSON.stringify({ cycles, seed }),
    }),
}
