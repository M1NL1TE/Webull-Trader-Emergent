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
  const [sellLoading, setSellLoading] = useState({}); // Changed to object to track per-position
  const [livePositions, setLivePositions] = useState(initialPositions);
  const [orderTimes, setOrderTimes] = useState({});
  const [symbolCache, setSymbolCache] = useState({}); // Cache option symbols to prevent flickering

  // Helper function to calculate DTE-based targets
  const calculateDTETargets = (dte, phase = 'initial', overrideSettings = null) => {
    if (overrideSettings && overrideSettings.override_profit_loss) {
      return {
        profit: overrideSettings.profit_percentage,
        loss: overrideSettings.loss_percentage
      };
    }
    
    if (phase === 'initial') {
      if (dte === 0) {
        return { profit: 25, loss: 25 }; // 0DTE initial
      } else {
        return { profit: 20, loss: 25 }; // 1DTE initial
      }
    } else {
      // Trailing phase
      if (dte === 0) {
        return { profit: 75, loss: 5 }; // 0DTE trailing
      } else {
        return { profit: 95, loss: 5 }; // 1DTE trailing
      }
    }
  };

  useEffect(() => {
    // Fetch settings to check for override
    const fetchSettings = async () => {
      try {
        const response = await axios.get(`${API}/settings`);
        // Don't directly use settings values - they might be overridden
        // We'll calculate targets based on DTE instead
        const hasOverride = response.data.override_profit_loss;
        if (hasOverride) {
          setProfitTarget(response.data.profit_percentage || 50);
          setStopLoss(response.data.loss_percentage || 25);
        }
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
        const positions = response.data.positions || [];
        
        // Cache option symbols to prevent flickering
        // IMPORTANT: Only cache full symbols (>10 chars), never overwrite with partial symbols
        setSymbolCache(prevCache => {
          const newCache = { ...prevCache };
          positions.forEach(pos => {
            const tickerId = pos.tickerId;
            const optionSymbol = pos.ticker?.optionSymbol;
            
            // Only cache if:
            // 1. We got a full option symbol (length > 10, like SPY251203P00682000)
            // 2. We don't already have a cached symbol, OR the new one is better
            if (optionSymbol && optionSymbol.length > 10) {
              console.log(`Caching option symbol for ${tickerId}: ${optionSymbol}`);
              newCache[tickerId] = optionSymbol;
            } else if (prevCache[tickerId]) {
              // Keep existing cache even if API didn't return full symbol this time
              console.log(`Using cached symbol for ${tickerId}: ${prevCache[tickerId]}`);
              newCache[tickerId] = prevCache[tickerId];
            }
          });
          return newCache;
        });
        
        setLivePositions(positions);
      } catch (error) {
        console.error('Error fetching positions:', error);
      }
    };
    
    // Fetch order times for positions
    const fetchOrderTimes = async () => {
      try {
        const ordersResponse = await axios.get(`${API}/orders/history`);
        const times = {};
        
        console.log('Fetching order times from history...');
        
        // Get the most recent BUY order for each ticker
        ordersResponse.data.forEach(order => {
          if (order.action === 'BUY' && order.status === 'Filled' && order.ticker?.tickerId) {
            const tickerId = order.ticker.tickerId;
            const filledTime = order.filledTime || order.createTime;
            
            // Keep the most recent time for this ticker
            if (!times[tickerId] || order.filledTime0 > times[tickerId].timestamp) {
              times[tickerId] = {
                time: filledTime,
                timestamp: order.filledTime0
              };
            }
          }
        });
        
        console.log('Order times collected:', times);
        setOrderTimes(times);
      } catch (error) {
        console.error('Error fetching order times:', error);
      }
    };
    
    fetchSettings();
    fetchBotData();
    fetchPositions(); // Initial fetch
    fetchOrderTimes(); // Fetch order entry times
    
    // Refresh positions every 5 seconds for real-time pricing
    const positionsInterval = setInterval(fetchPositions, 5000);
    
    // Refresh bot data every 30 seconds (less frequent)
    const botDataInterval = setInterval(fetchBotData, 30000);
    
    // Refresh order times every minute (timestamps don't change often)
    const orderTimesInterval = setInterval(fetchOrderTimes, 60000);
    
    return () => {
      clearInterval(positionsInterval);
      clearInterval(botDataInterval);
      clearInterval(orderTimesInterval);
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
    
    // TEMPORARILY REMOVED CONFIRMATION FOR TESTING
    // TODO: Add back confirmation after testing
    
    // Set loading state for this specific position
    setSellLoading(prev => ({ ...prev, [tickerId]: true }));
    console.log('Sending sell request to:', `${API}/trade/sell-position`);
    console.log('Request body:', { ticker_id: tickerId });
    
    try {
      const response = await axios.post(`${API}/trade/sell-position`, {
        ticker_id: tickerId
      });
      
      console.log('Sell response:', response.data);
      
      if (response.data.success) {
        alert(`Position sold successfully!\nQuantity: ${response.data.quantity}\nPrice: $${response.data.price.toFixed(2)}`);
        // Refresh positions data without full page reload
        const positionsResponse = await axios.get(`${API}/account`);
        setLivePositions(positionsResponse.data.positions || []);
      } else {
        alert('Sell request completed but success flag was false');
      }
    } catch (error) {
      console.error('Error selling position:', error);
      console.error('Error response:', error.response);
      alert(`Failed to sell position: ${error.response?.data?.detail || error.message}`);
    } finally {
      // Clear loading state for this specific position
      setSellLoading(prev => {
        const newState = { ...prev };
        delete newState[tickerId];
        return newState;
      });
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
      <CardContent className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {positions.map((position, index) => {
            console.log('Rendering position:', position);
            console.log('Ticker ID:', position?.ticker?.tickerId);
              
              const unrealizedPL = parseFloat(position.unrealizedProfitLoss || 0);
              const isProfit = unrealizedPL >= 0;
              const quantity = position.position || 0;
              const costPrice = parseFloat(position.costPrice || 0);
              const lastPrice = parseFloat(position.lastPrice || 0);
              // Use cached symbol first (prevents flickering), then optionSymbol, then regular symbol
              const tickerId = position.tickerId;
              const rawSymbol = symbolCache[tickerId] || position.ticker?.optionSymbol || position.ticker?.symbol || 'N/A';
              
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
              
              // Parse the symbol
              const parsed = parseOptionSymbol(rawSymbol);
              
              // If we have full data, update cache for this ticker
              const tickerIdForCache = position.tickerId;
              if (parsed.strike && parsed.type && !symbolCache[tickerIdForCache]) {
                // Update cache immediately in render
                symbolCache[tickerIdForCache] = rawSymbol;
              }
              
              const displaySymbol = parsed.strike ? `${parsed.ticker} ${parsed.strike} ${parsed.type}` : rawSymbol;
              const displayDate = parsed.date ? `${parsed.date}` : '';
              
              // Calculate current P/L percentage
              const plPercentage = costPrice > 0 ? ((lastPrice - costPrice) / costPrice) * 100 : 0;
              
              // Get DTE from entry signal for this position
              const positionDTE = entrySignal?.dte !== undefined ? entrySignal.dte : 1;
              const targets = calculateDTETargets(positionDTE, 'initial');
              
              // Calculate target prices using DTE-based targets
              const profitTargetPrice = costPrice * (1 + targets.profit / 100);
              const stopLossPrice = costPrice * (1 - targets.loss / 100);

              return (
                <div
                  key={index}
                  className="p-5 bg-slate-800/50 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors min-w-[320px]"
                  data-testid={`position-${index}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h4 className="font-semibold text-white text-lg">{displaySymbol}</h4>
                      {displayDate && (
                        <p className="text-xs text-slate-400">{displayDate}</p>
                      )}
                      <p className="text-sm text-slate-400 mt-1">Qty: {quantity}</p>
                      {orderTimes[position.ticker.tickerId] && (
                        <p className="text-xs text-slate-500 mt-1">
                          Opened: {orderTimes[position.ticker.tickerId].time}
                        </p>
                      )}
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
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs text-slate-500">Bot Exit Targets:</p>
                      <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                        {positionDTE}DTE
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="p-2 rounded bg-green-500/10 border border-green-500/30">
                        <div className="flex items-center justify-between">
                          <span className="text-green-400">Profit:</span>
                          <span className="text-green-300 font-semibold">+{targets.profit}%</span>
                        </div>
                        <div className="text-green-400 font-mono mt-1">
                          ${profitTargetPrice.toFixed(2)}
                        </div>
                      </div>
                      <div className="p-2 rounded bg-red-500/10 border border-red-500/30">
                        <div className="flex items-center justify-between">
                          <span className="text-red-400">Stop:</span>
                          <span className="text-red-300 font-semibold">-{targets.loss}%</span>
                        </div>
                        <div className="text-red-400 font-mono mt-1">
                          ${stopLossPrice.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Sell at Market Button - Individual for each position */}
                  <div className="pt-3 border-t border-slate-700">
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const tickerId = position.ticker.tickerId;
                        console.log('SELL BUTTON CLICKED! TickerId:', tickerId);
                        handleSellPosition(tickerId);
                      }}
                      disabled={sellLoading[position.ticker.tickerId]}
                      className="w-full py-2.5 px-4 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2 cursor-pointer text-sm"
                    >
                      {sellLoading[position.ticker.tickerId] ? (
                        <>
                          <div className="spinner w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
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
                  </div>
                </div>
              );
            })}
        </div>
      </CardContent>
    </Card>
  );
}

export default Positions;
