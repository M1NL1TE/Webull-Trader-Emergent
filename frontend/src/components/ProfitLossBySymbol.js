import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function ProfitLossBySymbol() {
  const [plBySymbol, setPlBySymbol] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPLBySymbol();
  }, []);

  const fetchPLBySymbol = async () => {
    try {
      const response = await axios.get(`${API}/account/activities`);
      const data = response.data;
      
      console.log('P/L by symbol response:', data);
      
      // Extract pl_by_symbol from response
      if (data.data && data.data.pl_by_symbol) {
        console.log('Found pl_by_symbol:', data.data.pl_by_symbol);
        setPlBySymbol(data.data.pl_by_symbol);
      } else if (data.pl_by_symbol) {
        console.log('Found pl_by_symbol at root:', data.pl_by_symbol);
        setPlBySymbol(data.pl_by_symbol);
      } else {
        console.log('No pl_by_symbol found');
        setPlBySymbol([]);
      }
    } catch (error) {
      console.error('Error fetching P/L by symbol:', error);
      setPlBySymbol([]);
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

  if (!plBySymbol || plBySymbol.length === 0) {
    return (
      <Card className="glass border-slate-700 card-hover">
        <CardHeader>
          <CardTitle className="text-lg font-semibold">P/L by Symbol</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-slate-400 text-sm">No realized P/L data available</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="glass border-slate-700 card-hover">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">P/L by Symbol</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {plBySymbol.map((item, index) => {
            const isProfit = item.pl >= 0;
            const Icon = isProfit ? TrendingUp : TrendingDown;
            const colorClass = isProfit ? 'text-green-400' : 'text-red-400';
            
            return (
              <div
                key={index}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${isProfit ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                    <Icon className={`w-4 h-4 ${colorClass}`} />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">{item.symbol}</p>
                    <p className="text-xs text-slate-500">Realized</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-semibold ${colorClass}`}>
                    {isProfit ? '+' : ''}${Math.abs(item.pl).toLocaleString('en-US', { 
                      minimumFractionDigits: 2, 
                      maximumFractionDigits: 2 
                    })}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

export default ProfitLossBySymbol;
