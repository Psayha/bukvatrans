import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Users from './pages/Users'
import UserDetail from './pages/UserDetail'
import Transcriptions from './pages/Transcriptions'
import Transactions from './pages/Transactions'
import PromoCodes from './pages/PromoCodes'
import Broadcast from './pages/Broadcast'

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_admin) return <div className="p-8 text-red-600">Access denied</div>
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAdmin>
              <Layout />
            </RequireAdmin>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="users" element={<Users />} />
          <Route path="users/:id" element={<UserDetail />} />
          <Route path="transcriptions" element={<Transcriptions />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="promo" element={<PromoCodes />} />
          <Route path="broadcast" element={<Broadcast />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
