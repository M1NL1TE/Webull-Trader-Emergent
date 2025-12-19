import { useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { ArrowUpCircle, ArrowDownCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function TradePanel({ onTradeComplete }) {
  const [formData, setFormData] = useState({
    symbol: 'SPY',
    option_type: 'call',
    trade_grade: 'A'
  });
  const [loading, setLoading] = useState(false);

  const handleTrade = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API}/trade/option`, formData);
      if (response.data.success) {
        toast.success(
          `${formData.option_type.toUpperCase()} order placed successfully! ` +
          `Quantity: ${response.data.quantity}, Price: $${response.data.price.toFixed(2)}`
        );
        onTradeComplete();
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to place trade';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="trade-panel">
      <Card className="glass border-slate-700">
        <CardHeader>
          <CardTitle className="text-slate-200">Place Option Trade</CardTitle>
          <CardDescription className="text-slate-400">
            Execute trades based on your analysis
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label className="text-slate-200">Symbol</Label>
            <Select value={formData.symbol} onValueChange={(value) => setFormData({ ...formData, symbol: value })}>
              <SelectTrigger className="bg-slate-800 border-slate-700 text-white" data-testid="symbol-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="SPY">SPY - S&P 500 ETF</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-slate-200">Option Type</Label>
            <div className="grid grid-cols-2 gap-4">
              <button
                data-testid="call-option-button"
                onClick={() => setFormData({ ...formData, option_type: 'call' })}
                className={`p-6 rounded-lg border-2 transition-all ${
                  formData.option_type === 'call'
                    ? 'border-green-500 bg-green-500/10'
                    : 'border-slate-700 bg-slate-800 hover:border-slate-600'
                }`}
              >
                <ArrowUpCircle className={`w-8 h-8 mx-auto mb-2 ${
                  formData.option_type === 'call' ? 'text-green-400' : 'text-slate-400'
                }`} />
                <div className={`font-semibold ${
                  formData.option_type === 'call' ? 'text-green-400' : 'text-slate-400'
                }`}>
                  CALL
                </div>
                <div className="text-xs text-slate-500 mt-1">Bullish bet</div>
              </button>

              <button
                data-testid="put-option-button"
                onClick={() => setFormData({ ...formData, option_type: 'put' })}
                className={`p-6 rounded-lg border-2 transition-all ${
                  formData.option_type === 'put'
                    ? 'border-red-500 bg-red-500/10'
                    : 'border-slate-700 bg-slate-800 hover:border-slate-600'
                }`}
              >
                <ArrowDownCircle className={`w-8 h-8 mx-auto mb-2 ${
                  formData.option_type === 'put' ? 'text-red-400' : 'text-slate-400'
                }`} />
                <div className={`font-semibold ${
                  formData.option_type === 'put' ? 'text-red-400' : 'text-slate-400'
                }`}>
                  PUT
                </div>
                <div className="text-xs text-slate-500 mt-1">Bearish bet</div>
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-slate-200">Trade Grade (Confidence Level)</Label>
            <Select value={formData.trade_grade} onValueChange={(value) => setFormData({ ...formData, trade_grade: value })}>
              <SelectTrigger className="bg-slate-800 border-slate-700 text-white" data-testid="grade-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="A+">A+ (Highest confidence - 20% capital)</SelectItem>
                <SelectItem value="A">A (High confidence - 18% capital)</SelectItem>
                <SelectItem value="B+">B+ (Good confidence - 15% capital)</SelectItem>
                <SelectItem value="B">B (Moderate confidence - 15% capital)</SelectItem>
                <SelectItem value="C+">C+ (Low confidence - 12% capital)</SelectItem>
                <SelectItem value="C">C (Very low confidence - 10% capital)</SelectItem>
                <SelectItem value="D+">D+ (Minimal confidence - 5% capital)</SelectItem>
                <SelectItem value="D">D (Test trade - 5% capital)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button
            onClick={handleTrade}
            className="w-full btn-primary text-white font-semibold py-6 text-lg"
            disabled={loading}
            data-testid="place-trade-button"
          >
            {loading ? (
              <><span className="spinner mr-2"></span>Placing Trade...</>
            ) : (
              `Place ${formData.option_type.toUpperCase()} Trade`
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Trade Info Card */}
      <Card className="glass border-slate-700">
        <CardHeader>
          <CardTitle className="text-slate-200">Trade Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 bg-cyan-500/10 border border-cyan-700/30 rounded-lg">
            <h4 className="text-cyan-400 font-semibold mb-2">ℹ️ How It Works</h4>
            <p className="text-sm text-slate-300">
              The system will automatically:
            </p>
            <ul className="text-sm text-slate-400 mt-2 space-y-1 list-disc list-inside">
              <li>Find the best options based on volume and strike price</li>
              <li>Calculate position size based on your trade grade</li>
              <li>Place a limit order at the ask price</li>
              <li>Set appropriate stop-loss levels</li>
            </ul>
          </div>

          <div className="p-4 bg-amber-500/10 border border-amber-700/30 rounded-lg">
            <h4 className="text-amber-400 font-semibold mb-2">⚠️ Important Notes</h4>
            <ul className="text-sm text-slate-400 space-y-1 list-disc list-inside">
              <li>Options expire - monitor your positions</li>
              <li>Trade grade determines capital allocation</li>
              <li>Stop-loss percentages vary by grade</li>
              <li>Only trade with capital you can afford to lose</li>
            </ul>
          </div>

          <div className="p-4 bg-slate-800/50 border border-slate-700 rounded-lg">
            <h4 className="text-white font-semibold mb-3">Capital Allocation by Grade</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">A+ / A:</span>
                <span className="text-green-400 font-semibold">18-20% per trade</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">B+ / B:</span>
                <span className="text-blue-400 font-semibold">15% per trade</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">C+ / C:</span>
                <span className="text-yellow-400 font-semibold">10-12% per trade</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">D+ / D:</span>
                <span className="text-red-400 font-semibold">5% per trade</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default TradePanel;
