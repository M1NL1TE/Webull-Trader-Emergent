import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, Clock, TrendingUp, AlertCircle, CheckCircle, XCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function BotStatusWidget() {
  const [botStatus, setBotStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBotStatus();
    // Refresh every 10 seconds
    const interval = setInterval(fetchBotStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchBotStatus = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      setBotStatus(response.data);
    } catch (error) {
      console.error('Error fetching bot status:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="glass border-slate-700 card-hover" data-testid="bot-status-widget">
        <CardContent className="flex items-center justify-center py-6">
          <div className="spinner"></div>
        </CardContent>
      </Card>
    );
  }

  if (!botStatus) {
    return (
      <Card className="glass border-slate-700 card-hover" data-testid="bot-status-widget">
        <CardHeader>
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Trading Bot Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-slate-400 text-sm">Unable to fetch bot status</p>
        </CardContent>
      </Card>
    );
  }

  const getMarketStatusColor = (status) => {
    if (status === 'Open') return 'bg-green-500';
    if (status.includes('Closed')) return 'bg-red-500';
    if (status === 'Pre-Market') return 'bg-yellow-500';
    return 'bg-slate-500';
  };

  const formatLastCheckTime = (isoString) => {
    if (!isoString) return 'Never';
    try {
      const date = new Date(isoString);
      const now = new Date();
      
      // Validate the date
      if (isNaN(date.getTime())) return 'Invalid time';
      
      const diffSeconds = Math.floor((now - date) / 1000);
      
      // If time difference is negative or too large, something is wrong
      if (diffSeconds < 0) return 'Just now';
      if (diffSeconds > 86400) return date.toLocaleTimeString(); // Over 24 hours, show actual time
      
      if (diffSeconds < 60) return `${diffSeconds}s ago`;
      if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
      return `${Math.floor(diffSeconds / 3600)}h ago`;
    } catch (e) {
      return 'Unknown';
    }
  };

  return (
    <Card className="glass border-slate-700 card-hover" data-testid="bot-status-widget">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            Trading Bot Status
          </CardTitle>
          <div className="flex items-center gap-2">
            {botStatus.running ? (
              <Badge className="bg-green-500/20 text-green-400 border-green-500/50 flex items-center gap-1">
                <CheckCircle className="w-3 h-3" />
                Running
              </Badge>
            ) : (
              <Badge className="bg-slate-500/20 text-slate-400 border-slate-500/50 flex items-center gap-1">
                <XCircle className="w-3 h-3" />
                Stopped
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Market Status */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${getMarketStatusColor(botStatus.market_status)} animate-pulse`}></div>
            <span className="text-sm text-slate-300">Market</span>
          </div>
          <span className="text-sm font-medium text-slate-100">{botStatus.market_status}</span>
        </div>

        {/* Last Check Time */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-400" />
            <span className="text-sm text-slate-300">Last Check</span>
          </div>
          <span className="text-sm font-medium text-slate-100">
            {formatLastCheckTime(botStatus.last_check_time)}
          </span>
        </div>

        {/* Current Signal/Action */}
        {botStatus.current_signal && (
          <div className="p-3 rounded-lg bg-slate-800/50">
            <div className="flex items-start gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400 mt-0.5" />
              <div>
                <p className="text-xs text-slate-400 mb-1">Current Signal</p>
                <p className="text-sm text-slate-100">{botStatus.current_signal}</p>
              </div>
            </div>
          </div>
        )}

        {/* Position Status */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50">
          <span className="text-sm text-slate-300">Position</span>
          <span className="text-sm font-medium text-slate-100">{botStatus.position_status}</span>
        </div>

        {/* Supply/Demand Zones (if available) */}
        {(botStatus.zones?.demand_top > 0 || botStatus.zones?.supply_top > 0) && (
          <div className="p-3 rounded-lg bg-slate-800/50">
            <p className="text-xs text-slate-400 mb-2">Supply/Demand Zones</p>
            <div className="space-y-1 text-xs">
              {botStatus.zones.supply_top > 0 && (
                <div className="flex justify-between">
                  <span className="text-red-400">Supply:</span>
                  <span className="text-slate-300">
                    ${botStatus.zones.supply_bottom.toFixed(2)} - ${botStatus.zones.supply_top.toFixed(2)}
                  </span>
                </div>
              )}
              {botStatus.zones.demand_top > 0 && (
                <div className="flex justify-between">
                  <span className="text-green-400">Demand:</span>
                  <span className="text-slate-300">
                    ${botStatus.zones.demand_bottom.toFixed(2)} - ${botStatus.zones.demand_top.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error Message */}
        {botStatus.error_message && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/50">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5" />
              <div>
                <p className="text-xs text-red-400 mb-1">Error</p>
                <p className="text-sm text-red-300">{botStatus.error_message}</p>
              </div>
            </div>
          </div>
        )}

        {/* Last Action */}
        {botStatus.last_action && (
          <div className="p-3 rounded-lg bg-slate-800/50">
            <p className="text-xs text-slate-400 mb-1">Last Action</p>
            <p className="text-sm text-slate-100">{botStatus.last_action}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default BotStatusWidget;
