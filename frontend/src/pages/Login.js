import { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { TrendingUp, Lock, User, Key } from 'lucide-react';

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.device_id) {
      toast.error('Device ID is required! See instructions above for how to get it.');
      return;
    }
    
    setLoading(true);

    try {
      const response = await axios.post(`${API}/auth/login`, formData);
      if (response.data.success) {
        toast.success('Login successful!');
        setIsAuthenticated(true);
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed. Please check your credentials.';
      
      // Show detailed error with better formatting
      if (message.includes('Device ID') || message.includes('CAPTCHA') || message.includes('image verification')) {
        toast.error(message, { duration: 10000 });
      } else {
        toast.error(message);
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
                Device ID (Required for CAPTCHA bypass)
              </Label>
              <Input
                id="device_id"
                data-testid="device-id-input"
                type="text"
                value={formData.device_id}
                onChange={(e) => setFormData({ ...formData, device_id: e.target.value })}
                className="bg-slate-800 border-slate-700 text-white font-mono"
                placeholder="e.g. 97468314e9674207be4aa99b13f749c9"
              />
              <div className="p-3 bg-cyan-500/10 border border-cyan-700/30 rounded-lg text-xs">
                <p className="text-cyan-300 font-medium mb-1">📝 How to get your Device ID:</p>
                <ol className="text-slate-300 space-y-1 list-decimal list-inside">
                  <li>Login at <a href="https://app.webullbroker.com" target="_blank" rel="noopener noreferrer" className="text-cyan-400 underline">app.webullbroker.com</a></li>
                  <li>Press F12 (Developer Tools) → Network tab</li>
                  <li>Complete image verification & login</li>
                  <li>Click any API request → Headers → Request Headers</li>
                  <li>Find & copy the 'did' value (32-character hex)</li>
                </ol>
                <p className="text-amber-300 mt-2">
                  ⚠️ Required due to Webull's CAPTCHA protection
                </p>
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
                <><span className="spinner mr-2"></span>Signing In...</>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>
          
          <div className="mt-6 text-center text-sm text-slate-400">
            <p>Secure connection to Webull API</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default Login;
