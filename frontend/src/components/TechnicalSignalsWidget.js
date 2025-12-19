import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Activity, BarChart3 } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function TechnicalSignalsWidget() {
  const [signals, setSignals] = useState(null);
  const [zones, setZones] = useState(null);
  const [orbStatus, setOrbStatus] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSignals();
    fetchLivePrice(); // Initial fetch
    
    const signalsInterval = setInterval(fetchSignals, 10000);
    const priceInterval = setInterval(fetchLivePrice, 2000); // Live price every 2s
    
    return () => {
      clearInterval(signalsInterval);
      clearInterval(priceInterval);
    };
  }, []);

  const fetchSignals = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      const data = response.data;
      
      setSignals(data.technical_signals || {});
      setZones(data.zones || {});
      setOrbStatus(data.orb_status || {});
      // Don't use current_price from bot status anymore
    } catch (error) {
      console.error('Error fetching signals:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchLivePrice = async () => {
    try {
      const response = await axios.get(`${API}/quote/spy`, { timeout: 3000 });
      setCurrentPrice(response.data.price || 0);
    } catch (error) {
      console.error('Error fetching live price:', error);
    }
  };

  const getGradeColor = (grade) => {
    if (!grade) return 'bg-slate-500';
    if (grade.includes('A')) return 'bg-green-500';
    if (grade.includes('B')) return 'bg-blue-500';
    if (grade.includes('C')) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getGradeTextColor = (grade) => {
    if (!grade) return 'text-slate-300';
    if (grade.includes('A')) return 'text-green-400';
    if (grade.includes('B')) return 'text-blue-400';
    if (grade.includes('C')) return 'text-yellow-400';
    return 'text-red-400';
  };

  if (loading) {
    return (
      <Card className="glass border-slate-700 card-hover">
        <CardContent className="flex items-center justify-center py-6">
          <div className="spinner"></div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="glass border-slate-700 card-hover">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-cyan-400" />
          Technical Signals
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Technical Grades */}
        <div>
          <p className="text-xs text-slate-400 mb-2">Indicator Grades</p>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex items-center justify-between p-2 rounded bg-slate-800/50">
              <span className="text-sm text-slate-300">RSI</span>
              <Badge className={`${getGradeColor(signals?.rsi_grade)} text-white`}>
                {signals?.rsi_grade || 'D'}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-800/50">
              <span className="text-sm text-slate-300">MACD</span>
              <Badge className={`${getGradeColor(signals?.macd_grade)} text-white`}>
                {signals?.macd_grade || 'D'}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-800/50">
              <span className="text-sm text-slate-300">Candle</span>
              <Badge className={`${getGradeColor(signals?.candle_grade)} text-white`}>
                {signals?.candle_grade || 'D'}
              </Badge>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-slate-800/50">
              <span className="text-sm text-slate-300">Volume</span>
              <Badge className={`${getGradeColor(signals?.volume_grade)} text-white`}>
                {signals?.volume_grade || 'D'}
              </Badge>
            </div>
          </div>
          <div className="mt-2 p-3 rounded-lg bg-slate-800/70 border border-slate-600">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-200">Combined Grade</span>
              <Badge className={`${getGradeColor(signals?.combined_grade)} text-white text-lg px-3`}>
                {signals?.combined_grade || 'D'}
              </Badge>
            </div>
          </div>
        </div>

        {/* Supply/Demand Zones */}
        {zones && (zones.supply_top > 0 || zones.demand_top > 0) && (
          <div>
            <p className="text-xs text-slate-400 mb-2">Supply/Demand Zones</p>
            <div className="space-y-2">
              {zones.supply_top > 0 && (
                <div className="p-2 rounded bg-red-500/10 border border-red-500/30">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <TrendingDown className="w-4 h-4 text-red-400" />
                      <span className="text-sm text-red-300">Supply Zone</span>
                    </div>
                    <span className="text-sm font-mono text-red-400">
                      ${zones.supply_bottom.toFixed(2)} - ${zones.supply_top.toFixed(2)}
                    </span>
                  </div>
                </div>
              )}
              
              {currentPrice > 0 && (
                <div className="p-2 rounded bg-slate-700/50 border border-slate-600">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-300">Current Price</span>
                    <span className="text-sm font-mono text-cyan-400 font-semibold">
                      ${currentPrice.toFixed(2)}
                    </span>
                  </div>
                </div>
              )}
              
              {zones.demand_top > 0 && (
                <div className="p-2 rounded bg-green-500/10 border border-green-500/30">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-green-400" />
                      <span className="text-sm text-green-300">Demand Zone</span>
                    </div>
                    <span className="text-sm font-mono text-green-400">
                      ${zones.demand_bottom.toFixed(2)} - ${zones.demand_top.toFixed(2)}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ORB Status */}
        {orbStatus && orbStatus.high > 0 && (
          <div>
            <p className="text-xs text-slate-400 mb-2">Opening Range Breakout (ORB)</p>
            <div className="p-3 rounded-lg bg-slate-800/50">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-400">ORB High:</span>
                  <span className="text-slate-200 font-mono">${orbStatus.high.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">ORB Low:</span>
                  <span className="text-slate-200 font-mono">${orbStatus.low.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Upside:</span>
                  <Badge className={orbStatus.upside_broken ? 'bg-green-500' : 'bg-slate-600'}>
                    {orbStatus.upside_broken ? 'Broken ✓' : 'Intact'}
                  </Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Downside:</span>
                  <Badge className={orbStatus.downside_broken ? 'bg-red-500' : 'bg-slate-600'}>
                    {orbStatus.downside_broken ? 'Broken ✓' : 'Intact'}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default TechnicalSignalsWidget;
