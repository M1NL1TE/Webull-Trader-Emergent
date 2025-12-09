import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function SupplyDemandWidget() {
  const [zones15m, setZones15m] = useState(null);
  const [zones1hr, setZones1hr] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(0);
  const [marketStatus, setMarketStatus] = useState('Unknown');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchZones();
    fetchLivePrice();
    
    const zonesInterval = setInterval(fetchZones, 5000);
    const priceInterval = setInterval(fetchLivePrice, 2000);
    
    return () => {
      clearInterval(zonesInterval);
      clearInterval(priceInterval);
    };
  }, []);

  const fetchZones = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      const data = response.data;
      
      setZones15m(data.zones || {});
      setZones1hr(data.zones_1hr || { supply_zones: [], demand_zones: [] });
      setMarketStatus(data.market_status || 'Unknown');
    } catch (error) {
      console.error('Error fetching zones:', error);
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

  if (loading) {
    return (
      <Card className="glass border-slate-700 card-hover">
        <CardContent className="flex items-center justify-center py-6">
          <div className="spinner"></div>
        </CardContent>
      </Card>
    );
  }

  const ZoneDisplay = ({ zone, type, index, currentPrice }) => {
    const isSupply = type === 'supply';
    const inZone = currentPrice >= zone.bottom && currentPrice <= zone.top;
    const color = isSupply ? 'red' : 'green';
    
    // Format zone timestamp if available
    const zoneDate = zone.timestamp ? new Date(zone.timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    }) : null;
    
    return (
      <div className={`p-4 rounded-lg ${inZone ? `bg-${color}-500/20 border-2 border-${color}-500` : `bg-${color}-500/10 border border-${color}-500/30`}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {isSupply ? <TrendingDown className="w-5 h-5 text-red-400" /> : <TrendingUp className="w-5 h-5 text-green-400" />}
            <span className="text-sm font-semibold text-${color}-300">
              {isSupply ? 'Supply' : 'Demand'} Zone {index > 0 ? `#${index + 1}` : ''}
            </span>
          </div>
          {inZone && (
            <span className="text-xs bg-${color}-500 text-white px-2 py-1 rounded">IN ZONE</span>
          )}
        </div>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <span className="text-xs text-slate-400">Top:</span>
            <span className={`text-lg font-mono font-bold text-${color}-400`}>
              ${zone.top.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-xs text-slate-400">Bottom:</span>
            <span className={`text-lg font-mono font-bold text-${color}-400`}>
              ${zone.bottom.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between items-center pt-2 border-t border-${color}-500/30">
            <span className="text-xs text-slate-400">Width:</span>
            <span className={`text-sm font-mono text-${color}-300`}>
              ${(zone.top - zone.bottom).toFixed(2)}
            </span>
          </div>
          {zoneDate && (
            <div className="flex justify-between items-center pt-2 border-t border-${color}-500/30">
              <span className="text-xs text-slate-400">📅 From:</span>
              <span className={`text-xs font-mono text-${color}-300`}>
                {zoneDate}
              </span>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <Card className="glass border-slate-700 card-hover">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-cyan-400" />
          Supply/Demand Zones
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="15m" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="15m">15-Min (Trading)</TabsTrigger>
            <TabsTrigger value="1hr">1-Hour (Structure)</TabsTrigger>
          </TabsList>
          
          <TabsContent value="15m" className="space-y-4">
            {zones15m && zones15m.supply_top > 0 ? (
              <>
                <div className="p-2 rounded bg-blue-500/10 border border-blue-500/30">
                  <p className="text-xs text-blue-300">
                    📊 3-day lookback (195 candles) • For trade entries
                  </p>
                </div>
                <ZoneDisplay 
                  zone={{ 
                    top: zones15m.supply_top, 
                    bottom: zones15m.supply_bottom,
                    timestamp: zones15m.supply_timestamp
                  }} 
                  type="supply" 
                  index={0}
                  currentPrice={currentPrice}
                />
                <ZoneDisplay 
                  zone={{ 
                    top: zones15m.demand_top, 
                    bottom: zones15m.demand_bottom,
                    timestamp: zones15m.demand_timestamp
                  }} 
                  type="demand" 
                  index={0}
                  currentPrice={currentPrice}
                />
              </>
            ) : (
              <p className="text-slate-400 text-center py-4">Calculating 15-min zones...</p>
            )}
          </TabsContent>
          
          <TabsContent value="1hr" className="space-y-4">
            {zones1hr && zones1hr.supply_zones && zones1hr.supply_zones.length > 0 ? (
              <>
                <div className="p-2 rounded bg-purple-500/10 border border-purple-500/30">
                  <p className="text-xs text-purple-300">
                    📊 60-day lookback (400 candles) • Top 2 zones each
                  </p>
                </div>
                
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-red-300">Supply Zones (Highest)</h3>
                  {zones1hr.supply_zones.map((zone, idx) => (
                    <ZoneDisplay 
                      key={`supply-${idx}`}
                      zone={zone} 
                      type="supply" 
                      index={idx}
                      currentPrice={currentPrice}
                    />
                  ))}
                </div>
                
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-green-300">Demand Zones (Lowest)</h3>
                  {zones1hr.demand_zones.map((zone, idx) => (
                    <ZoneDisplay 
                      key={`demand-${idx}`}
                      zone={zone} 
                      type="demand" 
                      index={idx}
                      currentPrice={currentPrice}
                    />
                  ))}
                </div>
              </>
            ) : (
              <p className="text-slate-400 text-center py-4">Calculating 1-hour zones...</p>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

export default SupplyDemandWidget;
