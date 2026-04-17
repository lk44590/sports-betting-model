import axios from 'axios'

const API_URL = ''  // Uses relative URL - same domain for production

const api = axios.create({
  baseURL: `${API_URL}/api`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Picks API
export const picksApi = {
  getTodaysPicks: (sports, minEv = 7.0, maxPicks = 10) => 
    api.get('/picks/today', { 
      params: { sports, min_ev: minEv, max_picks: maxPicks } 
    }),
  
  evaluateBet: (candidate) => 
    api.post('/model/evaluate', candidate),
  
  evaluateBatch: (candidates) => 
    api.post('/model/evaluate-batch', candidates)
}

// Bets API
export const betsApi = {
  placeBet: (bet) => 
    api.post('/bets/place', bet),
  
  settleBet: (settlement) => 
    api.post('/bets/settle', settlement),
  
  getOpenBets: () => 
    api.get('/bets/open'),
  
  getBetHistory: (days = 30) => 
    api.get('/bets/history', { params: { days } })
}

// Performance API
export const performanceApi = {
  getSummary: () => 
    api.get('/performance/summary'),
  
  getBySport: () => 
    api.get('/performance/by-sport'),
  
  getBankrollStatus: () => 
    api.get('/bankroll/status'),
  
  getBankrollHistory: (days = 30) => 
    api.get('/bankroll/history', { params: { days } })
}

// Model API
export const modelApi = {
  getConfig: () => 
    api.get('/model/config'),
  
  updateBankroll: (newBankroll) => 
    api.post('/model/update-bankroll', null, { 
      params: { new_bankroll: newBankroll } 
    })
}

// Data API
export const dataApi = {
  getStats: () => 
    api.get('/data/stats'),
  
  getActiveSports: () => 
    api.get('/sports/active')
}

export default api
