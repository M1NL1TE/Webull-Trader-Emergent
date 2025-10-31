import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Save } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function Settings() {
  const [settings, setSettings] = useState({
    auto_trading: false,
    profit_percentage: 50.0,
    loss_percentage: 25.0,
    sms_notifications: false
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await axios.get(`${API}/settings`);
        setSettings(response.data);
      } catch (error) {
        toast.error('Failed to load settings');
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/settings`, settings);
      toast.success('Settings saved successfully');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleAutoTradingToggle = async (checked) => {
    console.log('Auto-trading toggle clicked:', checked);
    
    // Update state immediately for UI responsiveness
    const newSettings = { ...settings, auto_trading: checked };
    setSettings(newSettings);
    
    // Auto-save the auto_trading toggle
    try {
      console.log('Sending settings update to backend...', newSettings);
      const response = await axios.post(`${API}/settings`, newSettings);
      console.log('Settings update response:', response.data);
      
      if (checked) {
        toast.success('🤖 Auto-trading enabled! Bot is starting...');
      } else {
        toast.success('🛑 Auto-trading disabled! Bot is stopping...');
      }
      
      // Log bot status after update
      setTimeout(async () => {
        try {
          const statusResponse = await axios.get(`${API}/bot/status`);
          console.log('Bot status after toggle:', statusResponse.data);
        } catch (e) {
          console.error('Failed to fetch bot status:', e);
        }
      }, 1000);
      
    } catch (error) {
      console.error('Failed to update auto-trading:', error);
      toast.error('Failed to update auto-trading setting');
      // Revert on error
      setSettings(settings);
    }
  };

  if (loading) {
    return (
      <Card className="glass border-slate-700">
        <CardContent className="flex items-center justify-center py-12">
          <div className="spinner"></div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6" data-testid="settings">
      <Card className="glass border-slate-700">
        <CardHeader>
          <CardTitle className="text-slate-200">Trading Settings</CardTitle>
          <CardDescription className="text-slate-400">
            Configure your automated trading preferences
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-lg">
            <div className="space-y-0.5">
              <Label htmlFor="auto_trading" className="text-slate-200 font-medium">
                Auto Trading
              </Label>
              <p className="text-sm text-slate-400">
                Automatically execute trades based on signals
              </p>
            </div>
            <Switch
              id="auto_trading"
              data-testid="auto-trading-toggle"
              checked={settings.auto_trading}
              onCheckedChange={handleAutoTradingToggle}
            />
          </div>

          {settings.auto_trading && (
            <div className="p-4 bg-amber-500/10 border border-amber-700/30 rounded-lg">
              <p className="text-sm text-amber-300">
                ⚠️ Auto-trading is enabled. The bot will execute trades automatically when signals are detected.
              </p>
            </div>
          )}

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="profit_percentage" className="text-slate-200">
                Take Profit Percentage
              </Label>
              <div className="flex items-center gap-4">
                <Input
                  id="profit_percentage"
                  data-testid="profit-percentage-input"
                  type="number"
                  min="1"
                  max="100"
                  step="1"
                  value={settings.profit_percentage}
                  onChange={(e) => setSettings({ ...settings, profit_percentage: parseFloat(e.target.value) })}
                  className="bg-slate-800 border-slate-700 text-white"
                />
                <span className="text-slate-400 min-w-[40px]">{settings.profit_percentage}%</span>
              </div>
              <p className="text-sm text-slate-500">
                Automatically sell when profit reaches this percentage
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="loss_percentage" className="text-slate-200">
                Stop Loss Percentage
              </Label>
              <div className="flex items-center gap-4">
                <Input
                  id="loss_percentage"
                  data-testid="loss-percentage-input"
                  type="number"
                  min="1"
                  max="100"
                  step="1"
                  value={settings.loss_percentage}
                  onChange={(e) => setSettings({ ...settings, loss_percentage: parseFloat(e.target.value) })}
                  className="bg-slate-800 border-slate-700 text-white"
                />
                <span className="text-slate-400 min-w-[40px]">{settings.loss_percentage}%</span>
              </div>
              <p className="text-sm text-slate-500">
                Automatically sell when loss reaches this percentage
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between p-4 bg-slate-800/50 rounded-lg">
            <div className="space-y-0.5">
              <Label htmlFor="sms_notifications" className="text-slate-200 font-medium">
                SMS Notifications
              </Label>
              <p className="text-sm text-slate-400">
                Receive trade notifications via SMS (Twilio required)
              </p>
            </div>
            <Switch
              id="sms_notifications"
              data-testid="sms-notifications-toggle"
              checked={settings.sms_notifications}
              onCheckedChange={(checked) => setSettings({ ...settings, sms_notifications: checked })}
            />
          </div>

          <Button
            onClick={handleSave}
            className="w-full btn-primary text-white font-semibold py-6"
            disabled={saving}
            data-testid="save-settings-button"
          >
            {saving ? (
              <><span className="spinner mr-2"></span>Saving...</>
            ) : (
              <><Save className="w-4 h-4 mr-2" />Save Settings</>
            )}
          </Button>
        </CardContent>
      </Card>

      <Card className="glass border-slate-700">
        <CardHeader>
          <CardTitle className="text-slate-200">Trading Strategy</CardTitle>
          <CardDescription className="text-slate-400">
            Overview of the automated trading strategy
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 bg-slate-800/50 rounded-lg">
            <h4 className="font-semibold text-white mb-3">Technical Indicators Used</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li className="flex items-start gap-2">
                <span className="text-cyan-400 mt-0.5">•</span>
                <span><strong className="text-slate-300">RSI (Relative Strength Index):</strong> Identifies overbought (&gt;70) and oversold (&lt;30) conditions</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-cyan-400 mt-0.5">•</span>
                <span><strong className="text-slate-300">MACD (Moving Average Convergence Divergence):</strong> Detects trend changes and momentum</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-cyan-400 mt-0.5">•</span>
                <span><strong className="text-slate-300">Candlestick Patterns:</strong> Recognizes bullish/bearish reversal patterns</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-cyan-400 mt-0.5">•</span>
                <span><strong className="text-slate-300">Supply/Demand Zones:</strong> Identifies key support and resistance levels</span>
              </li>
            </ul>
          </div>

          <div className="p-4 bg-slate-800/50 rounded-lg">
            <h4 className="font-semibold text-white mb-3">Risk Management</h4>
            <ul className="space-y-2 text-sm text-slate-400">
              <li className="flex items-start gap-2">
                <span className="text-green-400 mt-0.5">✓</span>
                <span>Position sizing based on trade grade (A+ = 20%, D = 5%)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-400 mt-0.5">✓</span>
                <span>Automatic stop-loss orders on every trade</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-400 mt-0.5">✓</span>
                <span>Only trades SPY options with high volume</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-green-400 mt-0.5">✓</span>
                <span>Maximum 1 position open at a time</span>
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default Settings;
