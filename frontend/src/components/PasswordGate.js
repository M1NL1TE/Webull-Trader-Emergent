import { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { Lock, Shield } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function PasswordGate({ onAuthenticated }) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post(`${API}/auth/app-password`, { password });
      if (response.data.success) {
        // Store token in localStorage
        localStorage.setItem('app_access_token', response.data.token);
        toast.success('Access granted!');
        onAuthenticated();
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Invalid password';
      toast.error(message);
      setPassword('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900" data-testid="password-gate">
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-cyan-950 to-slate-900 opacity-80"></div>
      
      <Card className="w-full max-w-md relative z-10 glass border-slate-700">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="p-4 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600">
              <Shield className="w-10 h-10 text-white" />
            </div>
          </div>
          <CardTitle className="text-3xl font-bold gradient-text">Secure Access</CardTitle>
          <CardDescription className="text-slate-400">
            Enter your password to access the Webull Trading Dashboard
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="password" className="text-slate-200 flex items-center gap-2">
                <Lock className="w-4 h-4" />
                Access Password
              </Label>
              <Input
                id="password"
                data-testid="app-password-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-slate-800 border-slate-700 text-white text-lg py-6"
                placeholder="Enter your password"
                required
                autoFocus
              />
            </div>

            <Button
              type="submit"
              data-testid="password-submit-button"
              className="w-full btn-primary text-white font-semibold py-6 text-lg"
              disabled={loading}
            >
              {loading ? (
                <><span className="spinner mr-2"></span>Verifying...</>
              ) : (
                <>
                  <Shield className="w-5 h-5 mr-2" />
                  Unlock Dashboard
                </>
              )}
            </Button>
          </form>
          
          <div className="mt-6 p-3 bg-cyan-500/10 border border-cyan-700/30 rounded-lg">
            <p className="text-xs text-slate-400 text-center">
              🔒 This password protects access to your Webull trading account
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default PasswordGate;
