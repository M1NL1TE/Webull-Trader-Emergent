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
    setLoading(true);

    try {
      const response = await axios.post(`${API}/auth/login`, formData);
      if (response.data.success) {
        toast.success('Login successful!');
        setIsAuthenticated(true);
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed. Please check your credentials.';
      toast.error(message);
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
              <Label htmlFor="device_id" className="text-slate-200">Device ID (Optional)</Label>
              <Input
                id="device_id"
                data-testid="device-id-input"
                type="text"
                value={formData.device_id}
                onChange={(e) => setFormData({ ...formData, device_id: e.target.value })}
                className="bg-slate-800 border-slate-700 text-white"
                placeholder="Leave blank for auto-generation"
              />
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
