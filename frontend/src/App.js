import { useState, useEffect } from 'react';
import '@/App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import Dashboard from '@/pages/Dashboard';
import Login from '@/pages/Login';
import PasswordGate from '@/components/PasswordGate';
import { Toaster } from '@/components/ui/sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [hasAppAccess, setHasAppAccess] = useState(false);
  const [loading, setLoading] = useState(true);
  const [attemptedRestore, setAttemptedRestore] = useState(false);

  useEffect(() => {
    // Check if user has app access token
    const appAccessToken = localStorage.getItem('app_access_token');
    if (appAccessToken) {
      setHasAppAccess(true);
    }
    
    // Try to restore Webull session ONLY ONCE
    const restoreSession = async () => {
      // Only attempt restore if we're NOT explicitly on the login page
      // and haven't attempted restore yet
      if (!attemptedRestore && window.location.pathname !== '/login') {
        setAttemptedRestore(true);
        try {
          const response = await axios.post(`${API}/auth/restore`);
          if (response.data.success) {
            setIsAuthenticated(true);
          }
        } catch (error) {
          console.log('No previous session found');
          setIsAuthenticated(false);
        } finally {
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    };
    
    if (appAccessToken) {
      restoreSession();
    } else {
      setLoading(false);
    }
  }, [attemptedRestore]);

  // Show password gate first
  if (!hasAppAccess) {
    return (
      <>
        <PasswordGate onAuthenticated={() => setHasAppAccess(true)} />
        <Toaster position="top-right" />
      </>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-900 to-slate-800">
        <div className="text-xl text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              isAuthenticated ? (
                <Navigate to="/" replace />
              ) : (
                <Login setIsAuthenticated={setIsAuthenticated} />
              )
            }
          />
          <Route
            path="/"
            element={
              isAuthenticated ? (
                <Dashboard setIsAuthenticated={setIsAuthenticated} />
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" />
    </div>
  );
}

export default App;
