import { useState, useEffect } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { TrendingUp, Lock, User, Key, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function Login({ setIsAuthenticated }) {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    trade_pin: '',
    is_paper: true,
    device_id: ''
  });
  const [loading, setLoading] = useState(false);
  const [sessionStatus, setSessionStatus] = useState(null);
  const [restoringSession, setRestoringSession] = useState(false);

  // Check if there's an existing session on mount
  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await axios.get(`${API}/auth/session-status`);
        if (response.data.has_session) {
          setSessionStatus(response.data);
        }
      } catch (error) {
        // No session or error - that's fine, user can login normally
        console.log('No existing session found');
      }
    };
    checkSession();
  }, []);

  // Handle session restore (bypasses Playwright)
  const handleRestoreSession = async () => {
    setRestoringSession(true);
    try {
      const response = await axios.post(`${API}/auth/restore`);
      if (response.data.success) {
        toast.success(`Session restored! Trading mode: ${response.data.is_paper ? 'PAPER' : 'LIVE'}`);
        setIsAuthenticated(true);
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to restore session';
      toast.error(message);
      setSessionStatus(null); // Clear session status so user knows to do full login
    } finally {
      setRestoringSession(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate all required fields
    if (!formData.username || formData.username.trim() === '') {
      toast.error('Username is required');
      return;
    }
    
    if (!formData.password || formData.password.trim() === '') {
      toast.error('Password is required');
      return;
    }
    
    if (!formData.trade_pin || formData.trade_pin.trim() === '') {
      toast.error('6-digit trade PIN is required');
      return;
    }
    
    if (formData.trade_pin.length !== 6 || !/^\d{6}$/.test(formData.trade_pin)) {
      toast.error('Trade PIN must be exactly 6 digits');
      return;
    }
    
    if (!formData.device_id || formData.device_id.length !== 32) {
      toast.error('Device ID must be exactly 32 characters! See instructions above for how to get it.');
      return;
    }
    
    setLoading(true);

    try {
      toast.info('Starting automated browser login... This may take 30-60 seconds.', { duration: 5000 });
      
      const response = await axios.post(`${API}/auth/login`, formData, {
        timeout: 90000 // 90 second timeout for Playwright
      });
      
      if (response.data.success) {
        toast.success('Login successful! Redirecting to dashboard...');
        setIsAuthenticated(true);
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed. Please check your credentials.';
      
      // Show detailed error with better formatting
      if (message.includes('timeout')) {
        toast.error('Login timed out. Please try again. If this persists, your DID may be expired.', { duration: 8000 });
      } else if (message.includes('Device ID')) {
        toast.error(message, { duration: 10000 });
      } else {
        toast.error(message, { duration: 8000 });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" data-testid="login-page">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-cyan-950 to-slate-900 opacity-80"></div>
      
      <Card className="w-full max-w-md relative z-10 glass border-slate-700" data-testid="login-card">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="p-3 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600">
              <TrendingUp className="w-8 h-8 text-white" />
            </div>
          </div>
          <CardTitle className="text-3xl font-bold gradient-text">Webull Trader</CardTitle>
          <CardDescription className="text-slate-400">Sign in to start trading SPY options</CardDescription>
        </CardHeader>
        
        <CardContent>
          {/* Show session restore option if active session exists */}
          {sessionStatus?.has_session && (
            <div className="mb-6 p-4 rounded-lg bg-gradient-to-r from-green-900/50 to-cyan-900/50 border border-green-700/50">
              <div className="flex items-center gap-2 mb-2">
                <RefreshCw className="w-5 h-5 text-green-400" />
                <span className="text-green-400 font-semibold">Active Session Found!</span>
              </div>
              <p className="text-sm text-slate-300 mb-3">
                Mode: <span className={sessionStatus.is_paper ? 'text-yellow-400' : 'text-red-400'}>
                  {sessionStatus.is_paper ? 'PAPER' : 'LIVE'}
                </span>
                {sessionStatus.has_trade_token ? ' ✓ Trade token valid' : ' ⚠️ No trade token'}
              </p>
              <Button
                type="button"
                onClick={handleRestoreSession}
                disabled={restoringSession}
                className="w-full bg-gradient-to-r from-green-600 to-cyan-600 hover:from-green-500 hover:to-cyan-500"
              >
                {restoringSession ? 'Restoring...' : 'Quick Restore Session (No Login Required)'}
              </Button>
              <p className="text-xs text-slate-400 mt-2 text-center">
                Bypass browser automation - use your existing session
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-slate-200 flex items-center gap-2">
                <User className="w-4 h-4" />
                Webull Username
              </Label>
              <Input
                id="username"
                data-testid="username-input"
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="bg-slate-800 border-slate-700 text-white"
                placeholder="Email or phone number"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-slate-200 flex items-center gap-2">
                <Lock className="w-4 h-4" />
                Password
              </Label>
              <Input
                id="password"
                data-testid="password-input"
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="bg-slate-800 border-slate-700 text-white"
                placeholder="Enter your password"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="trade_pin" className="text-slate-200 flex items-center gap-2">
                <Key className="w-4 h-4" />
                6-Digit Trade PIN
              </Label>
              <Input
                id="trade_pin"
                data-testid="trade-pin-input"
                type="password"
                value={formData.trade_pin}
                onChange={(e) => setFormData({ ...formData, trade_pin: e.target.value })}
                className="bg-slate-800 border-slate-700 text-white"
                placeholder="Enter your trade PIN"
                maxLength={6}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="device_id" className="text-slate-200 font-medium">
                Device ID (Required - 32 characters)
              </Label>
              <Input
                id="device_id"
                data-testid="device-id-input"
                type="text"
                value={formData.device_id}
                onChange={(e) => setFormData({ ...formData, device_id: e.target.value })}
                className="bg-slate-800 border-slate-700 text-white font-mono text-sm"
                placeholder="e.g. 97468314e9674207be4aa99b13f749c9"
                maxLength={32}
              />
              <div className="p-3 bg-cyan-500/10 border border-cyan-700/30 rounded-lg text-xs space-y-2">
                <p className="text-cyan-300 font-medium">📝 How to get your Device ID (one-time setup):</p>
                <ol className="text-slate-300 space-y-1 list-decimal list-inside ml-2">
                  <li>Open <a href="https://webull.com" target="_blank" rel="noopener noreferrer" className="text-cyan-400 underline hover:text-cyan-300">webull.com</a> in Chrome/Firefox</li>
                  <li>Press F12 → Network tab → Check "Preserve log"</li>
                  <li>Login successfully (complete CAPTCHA if shown)</li>
                  <li>In Network tab, click any request → Headers</li>
                  <li>Under <strong>Request Headers</strong>, find & copy the <code className="bg-slate-700 px-1 rounded">did</code> value</li>
                </ol>
                <div className="mt-2 p-2 bg-amber-900/20 border border-amber-700/30 rounded">
                  <p className="text-amber-300 text-xs">
                    💡 <strong>New Method:</strong> Once you provide your DID, our system uses automated browser login (no more CAPTCHA!) Your credentials are never stored.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-lg">
              <div className="space-y-0.5">
                <Label htmlFor="is_paper" className="text-slate-200 font-medium">Paper Trading</Label>
                <p className="text-sm text-slate-400">Test mode with virtual money</p>
              </div>
              <Switch
                id="is_paper"
                data-testid="paper-trading-toggle"
                checked={formData.is_paper}
                onCheckedChange={(checked) => setFormData({ ...formData, is_paper: checked })}
              />
            </div>

            {!formData.is_paper && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                <p className="text-sm text-amber-300">⚠️ Real trading mode enabled. Real money will be used!</p>
              </div>
            )}

            <Button
              type="submit"
              data-testid="login-button"
              className="w-full btn-primary text-white font-semibold py-6 text-lg"
              disabled={loading}
            >
              {loading ? (
                <><span className="spinner mr-2"></span>Logging in via browser automation...</>
              ) : (
                'Sign In (Automated)'
              )}
            </Button>
          </form>
          
          <div className="mt-6 text-center text-xs text-slate-400 space-y-1">
            <p>🔒 Secure automated login via Playwright</p>
            <p>Your credentials are used once and never stored</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default Login;
