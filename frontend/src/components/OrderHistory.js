import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { RefreshCw, Clock, CheckCircle, XCircle } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function OrderHistory() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API}/orders/history`);
      setOrders(response.data.orders || []);
    } catch (error) {
      toast.error('Failed to fetch order history');
      console.error('Error fetching history:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchHistory();
  };

  const getStatusColor = (status) => {
    const statusLower = (status || '').toLowerCase();
    if (statusLower.includes('filled') || statusLower.includes('complete')) {
      return 'bg-green-500/20 text-green-400 border-green-700';
    }
    if (statusLower.includes('cancel')) {
      return 'bg-red-500/20 text-red-400 border-red-700';
    }
    if (statusLower.includes('partial')) {
      return 'bg-yellow-500/20 text-yellow-400 border-yellow-700';
    }
    return 'bg-slate-500/20 text-slate-400 border-slate-700';
  };

  const getStatusIcon = (status) => {
    const statusLower = (status || '').toLowerCase();
    if (statusLower.includes('filled') || statusLower.includes('complete')) {
      return <CheckCircle className="w-4 h-4" />;
    }
    if (statusLower.includes('cancel')) {
      return <XCircle className="w-4 h-4" />;
    }
    return <Clock className="w-4 h-4" />;
  };

  if (loading) {
    return (
      <Card className="glass border-slate-700" data-testid="order-history-card">
        <CardContent className="flex items-center justify-center py-12">
          <div className="spinner"></div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="glass border-slate-700" data-testid="order-history-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-slate-200">Order History</CardTitle>
            <p className="text-sm text-slate-400 mt-1">Last 30 orders</p>
          </div>
          <Button
            onClick={handleRefresh}
            variant="outline"
            size="sm"
            className="border-slate-700"
            disabled={refreshing}
            data-testid="refresh-history-button"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {orders.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <Clock className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No order history found</p>
          </div>
        ) : (
          <ScrollArea className="h-[600px] pr-4">
            <div className="space-y-3">
              {orders.map((order, index) => {
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
                
                // Handle both stock and option orders
                let symbol = 'N/A';
                let displayDate = '';
                
                if (order.ticker && order.ticker.symbol) {
                  const rawSymbol = order.ticker.symbol;
                  const parsed = parseOptionSymbol(rawSymbol);
                  
                  if (parsed.strike) {
                    // Option format: "SPY $683 / 04 Nov Call"
                    symbol = `${parsed.ticker} ${parsed.strike}`;
                    displayDate = `${parsed.date} ${parsed.type}`;
                  } else {
                    symbol = rawSymbol;
                  }
                } else if (order.symbol) {
                  // Direct symbol field
                  const parsed = parseOptionSymbol(order.symbol);
                  if (parsed.strike) {
                    symbol = `${parsed.ticker} ${parsed.strike}`;
                    displayDate = `${parsed.date} ${parsed.type}`;
                  } else {
                    symbol = order.symbol;
                  }
                } else if (order.tickerType === 'OPTION' && order.optionType) {
                  // Option order - use looked up underlying symbol
                  const underlying = order.underlyingSymbol || 'Unknown';
                  const optType = order.optionType.toUpperCase();
                  const strike = order.optionExercisePrice || '?';
                  const expiry = order.optionExpireDate ? new Date(order.optionExpireDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
                  symbol = `${underlying} $${strike}`;
                  displayDate = `${expiry} ${optType}`;
                }
                
                const action = order.action || 'N/A';
                const orderType = order.orderType || 'N/A';
                const quantity = order.totalQuantity || order.quantity || 0;
                const filledQty = order.filledQuantity || 0;
                const price = parseFloat(order.avgFilledPrice || order.lmtPrice || 0);
                const status = order.status || order.statusStr || 'Unknown';
                const createTime = order.createTime0 || order.createTime || '';
                
                // Format date if available
                let orderDate = 'N/A';
                let orderTime = '';
                
                if (order.createTime && typeof order.createTime === 'string') {
                  // Already formatted as "10/17/2025 18:17:44 EDT"
                  const parts = order.createTime.split(' ');
                  orderDate = parts[0] || 'N/A';
                  orderTime = parts[1] || '';
                } else if (createTime && typeof createTime === 'number') {
                  const date = new Date(createTime);
                  orderDate = date.toLocaleDateString();
                  orderTime = date.toLocaleTimeString();
                }

                return (
                  <div
                    key={index}
                    className="p-4 bg-slate-800/50 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors"
                    data-testid={`history-order-${index}`}
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold text-white text-lg">{symbol}</h4>
                          <Badge variant="outline" className={action === 'BUY' ? 'text-green-400 border-green-700' : 'text-red-400 border-red-700'}>
                            {action}
                          </Badge>
                        </div>
                        {displayDate && (
                          <p className="text-xs text-slate-400">{displayDate}</p>
                        )}
                        <p className="text-xs text-slate-400 mt-1">
                          {orderDate} {orderTime}
                        </p>
                      </div>
                      <Badge className={getStatusColor(status)}>
                        <span className="flex items-center gap-1">
                          {getStatusIcon(status)}
                          {status}
                        </span>
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-slate-400">Type: </span>
                        <span className="text-white">{orderType}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Price: </span>
                        <span className="text-white">${price.toFixed(2)}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Quantity: </span>
                        <span className="text-white">{quantity}</span>
                      </div>
                      {filledQty > 0 && (
                        <div>
                          <span className="text-slate-400">Filled: </span>
                          <span className="text-white">{filledQty}</span>
                        </div>
                      )}
                    </div>

                    {/* Entry Signal Information */}
                    {order.entry_signal && action === 'BUY' && (
                      <div className="mt-3 pt-3 border-t border-slate-700">
                        <div className="text-xs text-slate-300">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-slate-400">Trade Reason:</span>
                            <Badge variant="outline" className="text-blue-400 border-blue-700 text-xs">
                              {order.entry_signal.type}
                            </Badge>
                            {order.entry_signal.grade && (
                              <Badge variant="outline" className="text-purple-400 border-purple-700 text-xs">
                                Grade: {order.entry_signal.grade}
                              </Badge>
                            )}
                          </div>
                          {order.entry_signal.reasons && (
                            <div className="text-slate-400 mt-1 text-xs">
                              {Array.isArray(order.entry_signal.reasons) ? (
                                order.entry_signal.reasons.map((reason, idx) => (
                                  <div key={idx}>• {reason}</div>
                                ))
                              ) : (
                                <div>{order.entry_signal.reasons}</div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

export default OrderHistory;
