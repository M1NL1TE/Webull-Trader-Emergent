import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function ProfitLossWidget() {
  const [activities, setActivities] = useState([]);
  const [period, setPeriod] = useState('all');
  const [totalPL, setTotalPL] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchActivities();
  }, []);

  useEffect(() => {
    calculatePL();
  }, [activities, period]);

  const fetchActivities = async () => {
    try {
      const response = await axios.get(`${API}/account/activities`);
      const data = response.data;
      
      // Extract trades from activities
      const trades = data.data || [];
      setActivities(trades);
    } catch (error) {
      console.error('Error fetching activities:', error);
    } finally {
      setLoading(false);
    }
  };

  const calculatePL = () => {
    if (!activities || activities.length === 0) {
      setTotalPL(0);
      return;
    }

    const now = new Date();
    let startDate = new Date(0); // Beginning of time

    switch (period) {
      case 'today':
        startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        break;
      case 'week':
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        break;
      case 'month':
        startDate = new Date(now.getFullYear(), now.getMonth(), 1);
        break;
      case 'year':
        startDate = new Date(now.getFullYear(), 0, 1);
        break;
      case 'all':
      default:
        startDate = new Date(0);
        break;
    }

    // Calculate P/L from trades
    let pl = 0;
    activities.forEach(activity => {
      const activityDate = new Date(activity.transactTime || activity.createTime || 0);
      
      if (activityDate >= startDate) {
        // Check if it's a sell order with profit/loss
        if (activity.action === 'Sell' && activity.profitLoss) {
          pl += parseFloat(activity.profitLoss);
        }
        // Or calculate from transaction amount for closed positions
        else if (activity.transactionType === 'Close' && activity.transactionAmount) {
          pl += parseFloat(activity.transactionAmount);
        }
      }
    });

    setTotalPL(pl);
  };

  const getPeriodLabel = () => {
    switch (period) {
      case 'today': return 'Today';
      case 'week': return 'This Week';
      case 'month': return 'This Month';
      case 'year': return 'This Year';
      case 'all': return 'All Time';
      default: return 'All Time';
    }
  };

  if (loading) {
    return (
      <Card className="glass border-slate-700 card-hover" data-testid="pl-widget">
        <CardContent className="flex items-center justify-center py-6">
          <div className="spinner"></div>
        </CardContent>
      </Card>
    );
  }

  const isProfit = totalPL >= 0;
  const Icon = isProfit ? TrendingUp : TrendingDown;
  const colorClass = isProfit ? 'text-green-400' : 'text-red-400';
  const bgClass = isProfit ? 'bg-green-500/10' : 'bg-red-500/10';

  return (
    <Card className="glass border-slate-700 card-hover" data-testid="pl-widget">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex-1">
          <CardTitle className="text-sm font-medium text-slate-400">
            Total P/L
          </CardTitle>
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-[140px] h-8 mt-2 bg-slate-800 border-slate-700 text-xs" data-testid="pl-period-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-slate-800 border-slate-700">
              <SelectItem value="today">Today</SelectItem>
              <SelectItem value="week">This Week</SelectItem>
              <SelectItem value="month">This Month</SelectItem>
              <SelectItem value="year">This Year</SelectItem>
              <SelectItem value="all">All Time</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className={`p-2 rounded-lg ${bgClass}`}>
          <Icon className={`w-4 h-4 ${colorClass}`} />
        </div>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${colorClass}`} data-testid="pl-amount">
          {isProfit ? '+' : ''}${Math.abs(totalPL).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <p className="text-xs text-slate-500 mt-1">{getPeriodLabel()}</p>
      </CardContent>
    </Card>
  );
}

export default ProfitLossWidget;
