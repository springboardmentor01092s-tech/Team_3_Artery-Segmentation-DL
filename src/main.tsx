import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth/AuthProvider'
import { NotificationProvider } from './features/notifications/NotificationProvider'
import { WorkspacePreferencesProvider } from './preferences/WorkspacePreferencesProvider'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <NotificationProvider><AuthProvider><WorkspacePreferencesProvider><App /></WorkspacePreferencesProvider></AuthProvider></NotificationProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
