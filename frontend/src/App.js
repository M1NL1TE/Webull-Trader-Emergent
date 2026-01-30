import { useState, useEffect } from 'react';
import '@/App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import Dashboard from '@/pages/Dashboard';
import PasswordGate from '@/components/PasswordGate';
import { Toaster } from '@/components/ui/sonner';
import { toast } from 'sonner';

// Use environment variable with fallback to production URL
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function App() {
  const [hasAppAccess, setHasAppAccess] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sessionStatus, setSessionStatus] = useState(null);

  useEffect(() => {
    // Check if user has app access token
    const appAccessToken = localStorage.getItem('app_access_token');
    if (appAccessToken) {
      setHasAppAccess(true);
    }
    
    // Try to initialize session on app load
    const initializeSession = async () => {
      if (!appAccessToken) {
        setLoading(false);
        return;
      }
      
      try {
        // Check session status
        const statusResponse = await axios.get(`${API}/auth/session-status`);
        setSessionStatus(statusResponse.data);
        
        if (statusResponse.data.has_session) {
          // Try to restore session silently
          try {
            const restoreResponse = await axios.post(`${API}/auth/restore`);
            if (restoreResponse.data.success) {
              console.log('✅ Session restored');
              toast.success(`Connected! Mode: ${restoreResponse.data.is_paper ? 'PAPER' : 'LIVE'}`);
            }
          } catch (restoreError) {
            console.log('Session restore info:', restoreError.message);
            // Try force login as fallback
            try {
              await axios.post(`${API}/auth/force-login`);
              toast.info('Dashboard access granted');
            } catch (forceError) {
              console.log('Force login info:', forceError.message);
            }
          }
        } else {
          toast.info('No Webull session - some features may be limited');
        }
      } catch (error) {
        console.log('Session check:', error.message);
      } finally {
        setLoading(false);
      }
    };
    
    initializeSession();
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

  // Go directly to dashboard - no login page needed
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route
            path="/"
            element={<Dashboard sessionStatus={sessionStatus} />}
          />
          {/* Redirect any other routes to dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" />
    </div>
  );
}

export default App;
