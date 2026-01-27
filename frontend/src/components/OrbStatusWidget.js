import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function OrbStatusWidget() {
  const [orbStatus, setOrbStatus] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOrbStatus();
    fetchLivePrice(); // Initial fetch
    
    const orbInterval = setInterval(fetchOrbStatus, 5000);
    const priceInterval = setInterval(fetchLivePrice, 2000); // Live price every 2s
    
    return () => {
      clearInterval(orbInterval);
      clearInterval(priceInterval);
    };
  }, []);

  const fetchOrbStatus = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      setOrbStatus(response.data.orb_status || {});
      // Don't use current_price from bot status anymore
    } catch (error) {
      console.error('Error fetching ORB status:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchLivePrice = async () => {
    try {
      const response = await axios.get(`${API}/quote/spy`, { timeout: 3000 });
      setCurrentPrice(response.data.price);
    } catch (error) {
      console.error('Error fetching live price:', error);
    }
  };

  if (loading) {
    return (
      <Card className="glass border-slate-700 card-hover" data-testid="orb-status-widget">
        <CardContent className="flex items-center justify-center py-6">
          <div className="spinner"></div>
        </CardContent>
      </Card>
    );
  }

  const hasOrbData = orbStatus && orbStatus.high > 0;
  const isActive = hasOrbData && !orbStatus.upside_broken && !orbStatus.downside_broken;
  const orbRange = hasOrbData ? (orbStatus.high - orbStatus.low).toFixed(2) : '0.00';

  return (
    <Card className="glass border-slate-700 card-hover" data-testid="orb-status-widget">
      <CardHeader>
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <Activity className="w-5 h-5 text-amber-400" />
          Opening Range Breakout (ORB)
        </CardTitle>
        <p className="text-xs text-slate-400 mt-1">
          9:30-9:40 AM EST • First 10 minutes
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasOrbData ? (
          <div className="text-center py-6">
            <p className="text-slate-400 text-sm mb-3">
              ⏱️ ORB Levels Not Yet Calculated
            </p>
            <p className="text-xs text-slate-500">
              ORB is calculated using the first 10 minutes (9:30-9:40 AM EST) and persists throughout the trading day.
            </p>
            <p className="text-xs text-slate-500 mt-2">
              {new Date().getHours() < 9 || (new Date().getHours() === 9 && new Date().getMinutes() < 30) 
                ? 'Will be calculated when market opens at 9:30 AM'
                : 'Bot was started after 9:45 AM - ORB levels will be available tomorrow'}
            </p>
          </div>
        ) : (
          <>
            {/* ORB Levels */}
            <div className="space-y-3">
              {/* ORB High */}
              <div className="flex items-center justify-between p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-green-400" />
                  <span className="text-sm text-slate-300">ORB High</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-lg font-mono font-bold text-green-400">
                    ${orbStatus.high.toFixed(2)}
                  </span>
                  <Badge className={orbStatus.upside_broken ? 'bg-green-500' : 'bg-slate-600'}>
                    {orbStatus.upside_broken ? 'Broken ✓' : 'Intact'}
                  </Badge>
                </div>
              </div>

              {/* Current Price (if available and in range) */}
              {currentPrice && (
                <div className="flex items-center justify-between p-2 rounded-lg bg-slate-700/30">
                  <span className="text-xs text-slate-400">Current SPY Price</span>
                  <span className="text-sm font-mono font-semibold text-cyan-400">
                    ${currentPrice.toFixed(2)}
                  </span>
                </div>
              )}

              {/* ORB Low */}
              <div className="flex items-center justify-between p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <div className="flex items-center gap-2">
                  <TrendingDown className="w-4 h-4 text-red-400" />
                  <span className="text-sm text-slate-300">ORB Low</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-lg font-mono font-bold text-red-400">
                    ${orbStatus.low.toFixed(2)}
                  </span>
                  <Badge className={orbStatus.downside_broken ? 'bg-red-500' : 'bg-slate-600'}>
                    {orbStatus.downside_broken ? 'Broken ✓' : 'Intact'}
                  </Badge>
                </div>
              </div>
            </div>

            {/* ORB Statistics */}
            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-700">
              <div className="text-center p-2 rounded-lg bg-slate-700/20">
                <p className="text-xs text-slate-400">Range Size</p>
                <p className="text-sm font-semibold text-slate-200 mt-1">${orbRange}</p>
              </div>
              <div className="text-center p-2 rounded-lg bg-slate-700/20">
                <p className="text-xs text-slate-400">Status</p>
                <Badge className={`mt-1 ${isActive ? 'bg-amber-500' : 'bg-slate-600'}`}>
                  {isActive ? 'Active' : orbStatus.upside_broken || orbStatus.downside_broken ? 'Broken' : 'Inactive'}
                </Badge>
              </div>
            </div>

            {/* Breakout Information */}
            {(orbStatus.upside_broken || orbStatus.downside_broken) && (
              <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <p className="text-xs text-blue-400 font-semibold mb-1">
                  🚨 Breakout Detected
                </p>
                <p className="text-xs text-slate-300">
                  {orbStatus.upside_broken && `Upside broken at ${new Date(orbStatus.upside_time).toLocaleTimeString()}`}
                  {orbStatus.downside_broken && `Downside broken at ${new Date(orbStatus.downside_time).toLocaleTimeString()}`}
                </p>
              </div>
            )}

            {/* ORB Logic Explanation */}
            <div className="p-3 rounded-lg bg-slate-700/20 border border-slate-600">
              <p className="text-xs text-slate-400">
                <span className="font-semibold text-slate-300">Trade Trigger:</span> When SPY breaks above ORB High → BUY CALL. When SPY breaks below ORB Low → BUY PUT.
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

export default OrbStatusWidget;
