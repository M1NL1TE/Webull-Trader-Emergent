import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertCircle, Info } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function NoTradeReasonWidget() {
  const [reason, setReason] = useState('Initializing...');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReason();
    const interval = setInterval(fetchReason, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchReason = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      setReason(response.data.no_trade_reason || 'Scanning...');
    } catch (error) {
      console.error('Error fetching trade reason:', error);
      setReason('Unable to fetch status');
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

  const isExecuting = reason.toLowerCase().includes('executing');
  const isError = reason.toLowerCase().includes('error');

  return (
    <Card className={`glass card-hover ${isExecuting ? 'border-green-500' : isError ? 'border-red-500' : 'border-slate-700'}`}>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold flex items-center gap-2">
          {isExecuting ? (
            <Info className="w-5 h-5 text-green-400" />
          ) : isError ? (
            <AlertCircle className="w-5 h-5 text-red-400" />
          ) : (
            <AlertCircle className="w-5 h-5 text-blue-400" />
          )}
          Bot Analysis
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`p-4 rounded-lg ${
          isExecuting ? 'bg-green-500/10 border border-green-500/30' : 
          isError ? 'bg-red-500/10 border border-red-500/30' : 
          'bg-blue-500/10 border border-blue-500/30'
        }`}>
          <p className={`text-sm ${
            isExecuting ? 'text-green-300' : 
            isError ? 'text-red-300' : 
            'text-blue-300'
          }`}>
            {reason.split('|').map((part, index) => (
              <span key={index} className="block mb-1">
                {part.trim()}
              </span>
            ))}
          </p>
        </div>
        
        {!isExecuting && !isError && (
          <p className="text-xs text-slate-500 mt-3 text-center">
            Bot continuously scans for A-grade or better setups, ORB breakouts, and supply/demand bounces
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default NoTradeReasonWidget;
