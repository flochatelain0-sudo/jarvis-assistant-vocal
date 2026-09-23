import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './pages/App'
import './styles/global.css'

ReactDOM.createRoot(document.getElementById('racine') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
