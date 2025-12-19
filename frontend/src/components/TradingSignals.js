import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, TrendingUp, Activity } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function TradingSignals() {
  const [signals, setSignals] = useState(null);
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(true);
  const symbol = 'SPY';

  const fetchSignals = async () => {
    setLoading(true);
    try {
      const [signalsRes, quoteRes] = await Promise.all([
        axios.get(`${API}/analysis/signals/${symbol}`),
        axios.get(`${API}/market/quote/${symbol}`)
      ]);
      setSignals(signalsRes.data);
      setQuote(quoteRes.data);
    } catch (error) {
      toast.error('Failed to fetch trading signals');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 60000);
    return () => clearInterval(interval);
  }, []);

  const getGradeColor = (grade) => {
    if (grade === 'A+' || grade === 'A') return 'text-green-400 bg-green-500/10 border-green-700';
    if (grade === 'B+' || grade === 'B') return 'text-blue-400 bg-blue-500/10 border-blue-700';
    if (grade === 'C+' || grade === 'C') return 'text-yellow-400 bg-yellow-500/10 border-yellow-700';
    return 'text-red-400 bg-red-500/10 border-red-700';
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
    <div className="space-y-6" data-testid="trading-signals">
      <Card className="glass border-slate-700">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-slate-200">Trading Signals - {symbol}</CardTitle>
          <Button
            onClick={fetchSignals}
            variant="outline"
            size="sm"
            className="border-slate-700"
            data-testid="refresh-signals-button"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Current Price */}
          {quote && (
            <div className="p-6 bg-gradient-to-br from-cyan-500/10 to-blue-500/10 rounded-lg border border-cyan-700/30">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400 mb-1">Current Price</p>
                  <h3 className="text-4xl font-bold text-white">${parseFloat(quote.close || 0).toFixed(2)}</h3>
                </div>
                <div className="text-right">
                  <p className="text-sm text-slate-400 mb-1">Change</p>
                  <p className={`text-2xl font-bold ${
                    parseFloat(quote.changeRatio || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {parseFloat(quote.changeRatio || 0) >= 0 ? '+' : ''}
                    {(parseFloat(quote.changeRatio || 0) * 100).toFixed(2)}%
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Technical Indicators */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* RSI Indicator */}
            <div className="p-6 bg-slate-800/50 rounded-lg border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-purple-400" />
                  <h4 className="font-semibold text-white">RSI Indicator</h4>
                </div>
                <Badge className={getGradeColor(signals?.rsi_grade)}>
                  Grade: {signals?.rsi_grade}
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">RSI Value</span>
                  <span className="text-white font-semibold">
                    {signals?.rsi?.toFixed(2) || 'N/A'}
                  </span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-2 mt-2">
                  <div
                    className="h-2 rounded-full transition-all"
                    style={{
                      width: `${Math.min(100, Math.max(0, signals?.rsi || 0))}%`,
                      background: signals?.rsi < 30 ? '#10b981' : signals?.rsi > 70 ? '#ef4444' : '#f59e0b'
                    }}
                  ></div>
                </div>
                <div className="flex justify-between text-xs text-slate-500 mt-1">
                  <span>Oversold (&lt;30)</span>
                  <span>Overbought (&gt;70)</span>
                </div>
              </div>
            </div>

            {/* MACD Indicator */}
            <div className="p-6 bg-slate-800/50 rounded-lg border border-slate-700">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-cyan-400" />
                  <h4 className="font-semibold text-white">MACD Indicator</h4>
                </div>
                <Badge className={getGradeColor(signals?.macd_grade)}>
                  Grade: {signals?.macd_grade}
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">MACD Line</span>
                  <span className="text-white font-semibold">
                    {signals?.macd?.toFixed(2) || 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Signal Line</span>
                  <span className="text-white font-semibold">
                    {signals?.macd_signal?.toFixed(2) || 'N/A'}
                  </span>
                </div>
                <div className="mt-2">
                  {signals?.macd > signals?.macd_signal ? (
                    <div className="flex items-center gap-2 text-green-400">
                      <TrendingUp className="w-4 h-4" />
                      <span className="text-sm">Bullish Signal</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-red-400">
                      <TrendingUp className="w-4 h-4 rotate-180" />
                      <span className="text-sm">Bearish Signal</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Trading Recommendation */}
          <div className="p-6 bg-gradient-to-br from-slate-800 to-slate-900 rounded-lg border border-slate-700">
            <h4 className="font-semibold text-white mb-4">Overall Analysis</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">RSI Grade</span>
                <Badge className={getGradeColor(signals?.rsi_grade)}>{signals?.rsi_grade}</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">MACD Grade</span>
                <Badge className={getGradeColor(signals?.macd_grade)}>{signals?.macd_grade}</Badge>
              </div>
              <div className="pt-4 border-t border-slate-700">
                <p className="text-sm text-slate-400">
                  {signals?.rsi_grade === 'A+' || signals?.macd_grade === 'A+'
                    ? '🟢 Strong trading signal detected. Consider placing a trade.'
                    : signals?.rsi_grade === 'D' && signals?.macd_grade === 'D'
                    ? '🔴 Weak signals. Wait for better opportunity.'
                    : '🟡 Mixed signals. Use caution when trading.'}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default TradingSignals;
