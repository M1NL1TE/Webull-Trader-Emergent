import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function SupplyDemandWidget() {
  const [zones, setZones] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(0);
  const [marketStatus, setMarketStatus] = useState('Unknown');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchZones();
    const interval = setInterval(fetchZones, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchZones = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      const data = response.data;
      
      setZones(data.zones || {});
      setCurrentPrice(data.current_price || 0);
      setMarketStatus(data.market_status || 'Unknown');
    } catch (error) {
      console.error('Error fetching zones:', error);
    } finally {
      setLoading(false);
    }
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

  const inSupplyZone = zones && currentPrice >= zones.supply_bottom && currentPrice <= zones.supply_top;
  const inDemandZone = zones && currentPrice >= zones.demand_bottom && currentPrice <= zones.demand_top;

  return (
    <Card className="glass border-slate-700 card-hover">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-cyan-400" />
          Supply/Demand Zones
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {zones && zones.supply_top > 0 ? (
          <>
            {/* Market Status Indicator */}
            {marketStatus && marketStatus.includes('Closed') && (
              <div className="mb-3 p-2 rounded bg-amber-500/10 border border-amber-500/30">
                <p className="text-xs text-amber-300">
                  📊 Market closed - Showing last calculated zones
                </p>
              </div>
            )}
            
            {/* Supply Zone */}
            <div className={`p-4 rounded-lg ${inSupplyZone ? 'bg-red-500/20 border-2 border-red-500' : 'bg-red-500/10 border border-red-500/30'}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <TrendingDown className="w-5 h-5 text-red-400" />
                  <span className="text-sm font-semibold text-red-300">Supply Zone (Resistance)</span>
                </div>
                {inSupplyZone && (
                  <span className="text-xs bg-red-500 text-white px-2 py-1 rounded">IN ZONE</span>
                )}
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Top:</span>
                  <span className="text-lg font-mono font-bold text-red-400">
                    ${zones.supply_top.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Bottom:</span>
                  <span className="text-lg font-mono font-bold text-red-400">
                    ${zones.supply_bottom.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-red-500/30">
                  <span className="text-xs text-slate-400">Zone Width:</span>
                  <span className="text-sm font-mono text-red-300">
                    ${(zones.supply_top - zones.supply_bottom).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            {/* Current Price */}
            {currentPrice > 0 && (
              <div className="p-4 rounded-lg bg-slate-700/50 border border-slate-600">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-semibold text-slate-300">Current SPY Price</span>
                  <span className="text-2xl font-mono font-bold text-cyan-400">
                    ${currentPrice.toFixed(2)}
                  </span>
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  {inSupplyZone && '🔴 In supply zone - potential reversal down'}
                  {inDemandZone && '🟢 In demand zone - potential bounce up'}
                  {!inSupplyZone && !inDemandZone && '⚪ Between zones - neutral'}
                </div>
              </div>
            )}

            {/* Demand Zone */}
            <div className={`p-4 rounded-lg ${inDemandZone ? 'bg-green-500/20 border-2 border-green-500' : 'bg-green-500/10 border border-green-500/30'}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-green-400" />
                  <span className="text-sm font-semibold text-green-300">Demand Zone (Support)</span>
                </div>
                {inDemandZone && (
                  <span className="text-xs bg-green-500 text-white px-2 py-1 rounded">IN ZONE</span>
                )}
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Top:</span>
                  <span className="text-lg font-mono font-bold text-green-400">
                    ${zones.demand_top.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Bottom:</span>
                  <span className="text-lg font-mono font-bold text-green-400">
                    ${zones.demand_bottom.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-green-500/30">
                  <span className="text-xs text-slate-400">Zone Width:</span>
                  <span className="text-sm font-mono text-green-300">
                    ${(zones.demand_top - zones.demand_bottom).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-8 text-slate-400">
            <p className="text-sm">Calculating zones...</p>
            <p className="text-xs mt-2">Bot needs to analyze price data first</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default SupplyDemandWidget;
