import { useState, useEffect } from 'react';
import '@/App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import Dashboard from '@/pages/Dashboard';
import Login from '@/pages/Login';
import PasswordGate from '@/components/PasswordGate';
import { Toaster } from '@/components/ui/sonner';
import { toast } from 'sonner';

// Use environment variable with fallback to production URL
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [hasAppAccess, setHasAppAccess] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user has app access token
    const appAccessToken = localStorage.getItem('app_access_token');
    if (appAccessToken) {
      setHasAppAccess(true);
    }
    
    // ALWAYS try to auto-restore session on app load
    const autoRestoreSession = async () => {
      if (!appAccessToken) {
        setLoading(false);
        return;
      }
      
      try {
        // First check if a session exists
        const statusResponse = await axios.get(`${API}/auth/session-status`);
        
        if (statusResponse.data.has_session) {
          // Session exists - try to restore it
          console.log('🔄 Auto-restoring existing session...');
          try {
            const restoreResponse = await axios.post(`${API}/auth/restore`);
            
            if (restoreResponse.data.success) {
              console.log('✅ Session auto-restored successfully');
              setIsAuthenticated(true);
              toast.success(`Session restored! Mode: ${restoreResponse.data.is_paper ? 'PAPER' : 'LIVE'}`);
              return;
            }
          } catch (restoreError) {
            console.log('Normal restore failed, trying force-login...', restoreError.message);
            // Try force login as fallback
            try {
              const forceResponse = await axios.post(`${API}/auth/force-login`);
              if (forceResponse.data.success) {
                console.log('✅ Force login successful');
                setIsAuthenticated(true);
                toast.success('Dashboard access granted (force login)');
                return;
              }
            } catch (forceError) {
              console.log('Force login also failed:', forceError.message);
            }
          }
        } else {
          console.log('No session found - login required');
          setIsAuthenticated(false);
        }
      } catch (error) {
        console.log('Session restore check failed:', error.message);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    };
    
    autoRestoreSession();
  }, []);

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
