import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import PrivateRoute from './components/PrivateRoute'
import AppLayout from './components/AppLayout'
import NewTranscription from './pages/app/NewTranscription'
import TranscriptionList from './pages/app/TranscriptionList'
import TranscriptionDetail from './pages/app/TranscriptionDetail'
import Profile from './pages/app/Profile'
import Plans from './pages/app/Plans'

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 10_000 } },
})

function AppShell({ children }: { children: React.ReactNode }) {
  return <AppLayout>{children}</AppLayout>
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route element={<PrivateRoute />}>
            <Route
              path="/app"
              element={<AppShell><NewTranscription /></AppShell>}
            />
            <Route
              path="/app/list"
              element={<AppShell><TranscriptionList /></AppShell>}
            />
            <Route
              path="/app/t/:id"
              element={<AppShell><TranscriptionDetail /></AppShell>}
            />
            <Route
              path="/app/profile"
              element={<AppShell><Profile /></AppShell>}
            />
            <Route
              path="/app/plans"
              element={<AppShell><Plans /></AppShell>}
            />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
