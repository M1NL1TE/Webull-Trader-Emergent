import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function LiveSpyPrice() {
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchQuote = async () => {
    try {
      const response = await axios.get(`${API}/quote/spy`, { 
        timeout: 5000,
        headers: { 'Cache-Control': 'no-cache' }
      });
      if (response.data && response.data.price) {
        setQuote(response.data);
        setLastUpdate(new Date());
        setLoading(false);
      }
    } catch (error) {
      console.error('Error fetching SPY quote:', error);
      setLoading(false); // Allow display even with stale data
    }
  };

  useEffect(() => {
    fetchQuote(); // Initial fetch
    
    // Refresh every 2 seconds for real-time updates
    const interval = setInterval(fetchQuote, 2000);
    
    return () => clearInterval(interval);
  }, []);

  if (loading || !quote) {
    return (
      <Card className="glass border-slate-700">
        <CardContent className="p-4">
          <div className="flex items-center justify-center">
            <div className="spinner"></div>
            <span className="ml-2 text-slate-400">Loading SPY price...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const isPositive = quote.change >= 0;
  const percentChange = (quote.changeRatio * 100).toFixed(2);
  
  // Calculate seconds since last update
  const secondsSinceUpdate = lastUpdate ? Math.floor((new Date() - lastUpdate) / 1000) : 0;

  return (
    <Card className="glass border-slate-700">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10">
              <Activity className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-400">SPY</span>
                <span className="text-xs text-slate-500">
                  Live • {secondsSinceUpdate}s ago
                </span>
                {quote.fallback && (
                  <span className="text-xs text-amber-500">(Fallback)</span>
                )}
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-3xl font-bold text-white">
                  ${quote.price.toFixed(2)}
                </span>
                <div className={`flex items-center gap-1 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                  {isPositive ? (
                    <TrendingUp className="w-4 h-4" />
                  ) : (
                    <TrendingDown className="w-4 h-4" />
                  )}
                  <span className="text-sm font-semibold">
                    {isPositive ? '+' : ''}{quote.change.toFixed(2)}
                  </span>
                  <span className="text-sm">
                    ({isPositive ? '+' : ''}{percentChange}%)
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          {/* Visual indicator for real-time updates */}
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              <span className="text-xs text-slate-500">Real-time</span>
            </div>
            <span className="text-xs text-slate-600">Updates every 2s</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default LiveSpyPrice;
