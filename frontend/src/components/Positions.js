import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useEffect, useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function Positions({ positions: initialPositions }) {
  const [profitTarget, setProfitTarget] = useState(50);
  const [stopLoss, setStopLoss] = useState(25);
  const [entrySignal, setEntrySignal] = useState(null);
  const [zones, setZones] = useState(null);
  const [sellLoading, setSellLoading] = useState(false);
  const [livePositions, setLivePositions] = useState(initialPositions);

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
    
    // Fetch entry signal and zones
    const fetchBotData = async () => {
      try {
        const response = await axios.get(`${API}/bot/status`);
        setEntrySignal(response.data.last_entry_signal);
        setZones(response.data.zones);
      } catch (error) {
        console.error('Error fetching bot data:', error);
      }
    };
    
    // Fetch live positions data (every 5 seconds)
    const fetchPositions = async () => {
      try {
        const response = await axios.get(`${API}/account`);
        setLivePositions(response.data.positions || []);
      } catch (error) {
        console.error('Error fetching positions:', error);
      }
    };
    
    fetchSettings();
    fetchBotData();
    fetchPositions(); // Initial fetch
    
    // Refresh positions every 5 seconds for real-time pricing
    const positionsInterval = setInterval(fetchPositions, 5000);
    
    // Refresh bot data every 30 seconds (less frequent)
    const botDataInterval = setInterval(fetchBotData, 30000);
    
    return () => {
      clearInterval(positionsInterval);
      clearInterval(botDataInterval);
    };
  }, []);

  // Update local positions when prop changes (from dashboard refresh)
  useEffect(() => {
    if (initialPositions) {
      setLivePositions(initialPositions);
    }
  }, [initialPositions]);

  const handleSellPosition = async (tickerId) => {
    console.log('Sell button clicked! Ticker ID:', tickerId);
    
    if (!window.confirm('Are you sure you want to sell this position at market price?')) {
      console.log('User cancelled sell');
      return;
    }

    setSellLoading(true);
    console.log('Sending sell request to:', `${API}/trade/sell-position`);
    console.log('Request body:', { ticker_id: tickerId });
    
    try {
      const response = await axios.post(`${API}/trade/sell-position`, {
        ticker_id: tickerId
      });
      
      console.log('Sell response:', response.data);
      
      if (response.data.success) {
        alert(`Position sold successfully!\nQuantity: ${response.data.quantity}\nPrice: $${response.data.price.toFixed(2)}`);
        // Refresh the page to update positions
        window.location.reload();
      } else {
        alert('Sell request completed but success flag was false');
      }
    } catch (error) {
      console.error('Error selling position:', error);
      console.error('Error response:', error.response);
      alert(`Failed to sell position: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSellLoading(false);
    }
  };

  const positions = livePositions;

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
        <CardTitle className="text-slate-200 flex items-center gap-2">
          Current Positions
          <span className="text-xs text-slate-500 font-normal">(Updates every 5s)</span>
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
                  
                  {/* Entry Signal Info */}
                  {entrySignal ? (
                    <div className="mt-3 pt-3 border-t border-slate-700">
                      <p className="text-xs text-slate-500 mb-2">Entry Signal:</p>
                      <div className="p-2 rounded bg-blue-500/10 border border-blue-500/30">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-semibold text-blue-300">{entrySignal.signal_type}</span>
                          <span className="text-xs text-blue-400">Grade: {entrySignal.grade}</span>
                        </div>
                        <p className="text-xs text-blue-200">{entrySignal.reasons}</p>
                        
                        {/* Grade Breakdown */}
                        {entrySignal.grade_breakdown && (
                          <div className="mt-2 pt-2 border-t border-blue-500/30">
                            <p className="text-xs text-slate-400 mb-1">Technical Breakdown:</p>
                            <div className="grid grid-cols-4 gap-2 text-xs">
                              <div className="text-center p-1 rounded bg-slate-700/30">
                                <div className="text-slate-400">RSI</div>
                                <div className="text-blue-300 font-semibold">{entrySignal.grade_breakdown.rsi}</div>
                              </div>
                              <div className="text-center p-1 rounded bg-slate-700/30">
                                <div className="text-slate-400">MACD</div>
                                <div className="text-blue-300 font-semibold">{entrySignal.grade_breakdown.macd}</div>
                              </div>
                              <div className="text-center p-1 rounded bg-slate-700/30">
                                <div className="text-slate-400">Candle</div>
                                <div className="text-blue-300 font-semibold">{entrySignal.grade_breakdown.candle}</div>
                              </div>
                              <div className="text-center p-1 rounded bg-slate-700/30">
                                <div className="text-slate-400">Volume</div>
                                <div className="text-blue-300 font-semibold">{entrySignal.grade_breakdown.volume}</div>
                              </div>
                            </div>
                          </div>
                        )}
                        
                        {/* SPY Entry Price */}
                        {entrySignal.entry_price && (
                          <div className="mt-2 pt-2 border-t border-blue-500/30">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-slate-400">SPY Entry Price:</span>
                              <span className="text-sm font-mono font-semibold text-cyan-400">${entrySignal.entry_price.toFixed(2)}</span>
                            </div>
                          </div>
                        )}
                        
                        {entrySignal.zones && (
                          <div className="mt-2 pt-2 border-t border-blue-500/30">
                            <p className="text-xs text-slate-400 mb-1">Entry Zones:</p>
                            <div className="grid grid-cols-2 gap-2 text-xs">
                              <div>
                                <span className="text-red-400">Supply: </span>
                                <span className="text-slate-300">${entrySignal.zones.supply_bottom.toFixed(2)}-${entrySignal.zones.supply_top.toFixed(2)}</span>
                              </div>
                              <div>
                                <span className="text-green-400">Demand: </span>
                                <span className="text-slate-300">${entrySignal.zones.demand_bottom.toFixed(2)}-${entrySignal.zones.demand_top.toFixed(2)}</span>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    // Show current zones for old positions (before entry tracking was added)
                    <div className="mt-3 pt-3 border-t border-slate-700">
                      <p className="text-xs text-slate-500 mb-2">Current S/D Zones:</p>
                      <div className="p-2 rounded bg-slate-700/30 border border-slate-600">
                        <p className="text-xs text-amber-400 mb-2">⚠️ Entry zones not tracked for this position</p>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-red-400">Supply: </span>
                            <span className="text-slate-300">
                              {zones && zones.supply_top > 0 
                                ? `$${zones.supply_bottom.toFixed(2)}-$${zones.supply_top.toFixed(2)}`
                                : 'Calculating...'}
                            </span>
                          </div>
                          <div>
                            <span className="text-green-400">Demand: </span>
                            <span className="text-slate-300">
                              {zones && zones.demand_top > 0 
                                ? `$${zones.demand_bottom.toFixed(2)}-$${zones.demand_top.toFixed(2)}`
                                : 'Calculating...'}
                            </span>
                          </div>
                        </div>
                        <p className="text-xs text-slate-500 mt-2">Showing latest calculated zones</p>
                      </div>
                    </div>
                  )}
                  
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
                  
                  {/* Manual Sell Button */}
                  <div className="pt-3 border-t border-slate-700">
                    <button
                      onClick={() => handleSellPosition(position.ticker.tickerId)}
                      disabled={sellLoading}
                      className="w-full py-2 px-4 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                      {sellLoading ? (
                        <>
                          <div className="spinner w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                          <span>Selling...</span>
                        </>
                      ) : (
                        <>
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                          </svg>
                          <span>Sell at Market</span>
                        </>
                      )}
                    </button>
                    <p className="text-xs text-slate-500 text-center mt-2">
                      Close position at current market price
                    </p>
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
