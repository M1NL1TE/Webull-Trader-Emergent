import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useEffect, useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function Positions({ positions }) {
  const [profitTarget, setProfitTarget] = useState(50);
  const [stopLoss, setStopLoss] = useState(25);
  const [entrySignal, setEntrySignal] = useState(null);

  useEffect(() => {
    // Fetch settings to get profit/loss targets
    const fetchSettings = async () => {
      try {
        const response = await axios.get(`${API}/settings`);
        setProfitTarget(response.data.profit_percentage || 50);
        setStopLoss(response.data.loss_percentage || 25);
      } catch (error) {
        console.error('Error fetching settings:', error);
      }
    };
    
    // Fetch entry signal
    const fetchEntrySignal = async () => {
      try {
        const response = await axios.get(`${API}/bot/status`);
        setEntrySignal(response.data.last_entry_signal);
      } catch (error) {
        console.error('Error fetching entry signal:', error);
      }
    };
    
    fetchSettings();
    fetchEntrySignal();
    
    // Refresh entry signal every 30 seconds
    const interval = setInterval(fetchEntrySignal, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!positions || positions.length === 0) {
    return (
      <Card className="glass border-slate-700" data-testid="positions-card">
        <CardHeader>
          <CardTitle className="text-slate-200">Current Positions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-slate-400">
            <p>No open positions</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="glass border-slate-700" data-testid="positions-card">
      <CardHeader>
        <CardTitle className="text-slate-200 flex items-center justify-between">
          <span>Current Positions</span>
          <Badge variant="outline" className="text-cyan-400 border-cyan-700">
            {positions.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-4">
            {positions.map((position, index) => {
              const unrealizedPL = parseFloat(position.unrealizedProfitLoss || 0);
              const isProfit = unrealizedPL >= 0;
              const quantity = position.position || 0;
              const costPrice = parseFloat(position.costPrice || 0);
              const lastPrice = parseFloat(position.lastPrice || 0);
              const rawSymbol = position.ticker?.symbol || 'N/A';
              
              // Parse option symbol: SPY251104C00683000 -> SPY $683 / 04 Nov Call
              const parseOptionSymbol = (symbol) => {
                // Format: SYMBOL+YYMMDD+C/P+STRIKEXXXXXX
                const match = symbol.match(/^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$/);
                
                if (match) {
                  const [, ticker, year, month, day, type, strikeRaw] = match;
                  const strike = parseInt(strikeRaw) / 1000; // Strike is in cents, divide by 1000
                  const optionType = type === 'C' ? 'Call' : 'Put';
                  
                  // Format date
                  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                  const monthName = months[parseInt(month) - 1];
                  
                  return {
                    ticker,
                    strike: `$${strike}`,
                    date: `${day} ${monthName}`,
                    year: `20${year}`,
                    type: optionType
                  };
                }
                
                // If not an option symbol, return as-is
                return {
                  ticker: symbol,
                  strike: '',
                  date: '',
                  year: '',
                  type: ''
                };
              };
              
              const parsed = parseOptionSymbol(rawSymbol);
              const displaySymbol = parsed.strike ? `${parsed.ticker} ${parsed.strike}` : rawSymbol;
              const displayDate = parsed.date ? `${parsed.date} ${parsed.type}` : '';
              
              // Calculate current P/L percentage
              const plPercentage = costPrice > 0 ? ((lastPrice - costPrice) / costPrice) * 100 : 0;
              
              // Calculate target prices
              const profitTargetPrice = costPrice * (1 + profitTarget / 100);
              const stopLossPrice = costPrice * (1 - stopLoss / 100);

              return (
                <div
                  key={index}
                  className="p-4 bg-slate-800/50 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors"
                  data-testid={`position-${index}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h4 className="font-semibold text-white text-lg">{displaySymbol}</h4>
                      {displayDate && (
                        <p className="text-xs text-slate-400">{displayDate}</p>
                      )}
                      <p className="text-sm text-slate-400 mt-1">Qty: {quantity}</p>
                    </div>
                    <div className="text-right">
                      <Badge className={isProfit ? 'bg-green-500/20 text-green-400 border-green-500' : 'bg-red-500/20 text-red-400 border-red-500'}>
                        {isProfit ? '+' : ''}
                        ${Math.abs(unrealizedPL).toFixed(2)}
                      </Badge>
                      <p className={`text-xs mt-1 font-semibold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                        {plPercentage >= 0 ? '+' : ''}{plPercentage.toFixed(2)}%
                      </p>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2 text-sm mb-3">
                    <div>
                      <span className="text-slate-400">Cost: </span>
                      <span className="text-white">${costPrice.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Last: </span>
                      <span className="text-white">${lastPrice.toFixed(2)}</span>
                    </div>
                  </div>
                  
                  {/* Bot Targets */}
                  <div className="pt-3 border-t border-slate-700">
                    <p className="text-xs text-slate-500 mb-2">Bot Exit Targets:</p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 rounded bg-green-500/10 border border-green-500/30">
                        <div className="flex items-center justify-between">
                          <span className="text-green-400">Profit:</span>
                          <span className="text-green-300 font-semibold">+{profitTarget}%</span>
                        </div>
                        <div className="text-green-400 font-mono mt-1">
                          ${profitTargetPrice.toFixed(2)}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-red-500/10 border border-red-500/30">
                        <div className="flex items-center justify-between">
                          <span className="text-red-400">Stop:</span>
                          <span className="text-red-300 font-semibold">-{stopLoss}%</span>
                        </div>
                        <div className="text-red-400 font-mono mt-1">
                          ${stopLossPrice.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

export default Positions;
