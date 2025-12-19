import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, TrendingDown, DollarSign } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://autotrade-spy.emergent.host';
const API = `${BACKEND_URL}/api`;

function ProfitLossWidget() {
  const [plSummary, setPlSummary] = useState(null);
  const [period, setPeriod] = useState('all');
  const [totalPL, setTotalPL] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchActivities();
  }, []);

  useEffect(() => {
    updatePLForPeriod();
  }, [plSummary, period]);

  const fetchActivities = async () => {
    try {
      const response = await axios.get(`${API}/account/activities`);
      const data = response.data;
      
      console.log('Activities response:', data);
      
      // Check if we have the new pl_summary structure
      if (data.data && data.data.pl_summary) {
        console.log('Found pl_summary:', data.data.pl_summary);
        setPlSummary(data.data.pl_summary);
      } else if (data.pl_summary) {
        console.log('Found pl_summary at root:', data.pl_summary);
        setPlSummary(data.pl_summary);
      } else {
        console.log('No pl_summary found, using fallback');
        // Fallback to empty summary
        setPlSummary({
          today: 0,
          week: 0,
          month: 0,
          year: 0,
          all_time: 0
        });
      }
    } catch (error) {
      console.error('Error fetching activities:', error);
      setPlSummary({
        today: 0,
        week: 0,
        month: 0,
        year: 0,
        all_time: 0
      });
    } finally {
      setLoading(false);
    }
  };

  const updatePLForPeriod = () => {
    if (!plSummary) {
      setTotalPL(0);
      return;
    }

    let pl = 0;
    switch (period) {
      case 'today':
        pl = plSummary.today || 0;
        break;
      case 'week':
        pl = plSummary.week || 0;
        break;
      case 'month':
        pl = plSummary.month || 0;
        break;
      case 'year':
        pl = plSummary.year || 0;
        break;
      case 'all':
      default:
        pl = plSummary.all_time || 0;
        break;
    }

    console.log(`P/L for ${period}:`, pl);
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
