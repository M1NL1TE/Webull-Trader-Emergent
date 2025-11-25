import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  RefreshCw,
  Settings as SettingsIcon,
  LogOut,
  ArrowUpCircle,
  ArrowDownCircle
} from 'lucide-react';
import AccountOverview from '@/components/AccountOverview';
import Positions from '@/components/Positions';
import Orders from '@/components/Orders';
import TradingSignals from '@/components/TradingSignals';
import TradePanel from '@/components/TradePanel';
import OrderHistory from '@/components/OrderHistory';
import Settings from '@/components/Settings';
import ProfitLossBySymbol from '@/components/ProfitLossBySymbol';
import BotStatusWidget from '@/components/BotStatusWidget';
import TechnicalSignalsWidget from '@/components/TechnicalSignalsWidget';
import NoTradeReasonWidget from '@/components/NoTradeReasonWidget';
import SupplyDemandWidget from '@/components/SupplyDemandWidget';
import OrbStatusWidget from '@/components/OrbStatusWidget';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function Dashboard({ setIsAuthenticated }) {
  const [account, setAccount] = useState(null);
  const [positions, setPositions] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    try {
      const [accountRes, positionsRes, ordersRes] = await Promise.all([
        axios.get(`${API}/account`),
        axios.get(`${API}/positions`),
        axios.get(`${API}/orders`)
      ]);

      setAccount(accountRes.data);
      setPositions(positionsRes.data.positions || []);
      setOrders(ordersRes.data.orders || []);
    } catch (error) {
      console.error('Error fetching data:', error);
      if (error.response?.status === 401) {
        toast.error('Session expired. Please login again.');
        setIsAuthenticated(false);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    
    // Auto-refresh every 30 seconds for general dashboard data
    // (Positions component has its own 5-second refresh for real-time pricing)
    const interval = setInterval(() => {
      fetchData();
    }, 30000);

    // Keep-alive ping during market hours to prevent platform sleep
    const keepAlivePing = async () => {
      const now = new Date();
      const estTime = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
      const hours = estTime.getHours();
      const minutes = estTime.getMinutes();
      const dayOfWeek = estTime.getDay();
      
      // Check if market hours (9:30 AM - 4:00 PM EST, Monday-Friday)
      const isWeekday = dayOfWeek >= 1 && dayOfWeek <= 5;
      const isMarketHours = (hours > 9 || (hours === 9 && minutes >= 30)) && hours < 16;
      
      if (isWeekday && isMarketHours) {
        try {
          // Make a lightweight ping to keep the backend active
          await axios.get(`${API}/bot/heartbeat`, { timeout: 5000 });
          console.log('💓 Keep-alive ping sent (market hours)');
        } catch (error) {
          console.warn('Keep-alive ping failed:', error.message);
        }
      }
    };
    
    // Ping every 45 seconds during market hours (frontend-side keep-alive)
    const keepAliveInterval = setInterval(keepAlivePing, 45000);
    keepAlivePing(); // Initial ping

    return () => {
      clearInterval(interval);
      clearInterval(keepAliveInterval);
    };
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleLogout = async () => {
    try {
      // Call backend to clear session
      await axios.post(`${API}/auth/logout`);
      setIsAuthenticated(false);
      toast.success('Logged out successfully');
    } catch (error) {
      console.error('Logout error:', error);
      // Still log out on frontend even if backend fails
      setIsAuthenticated(false);
      toast.success('Logged out');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="spinner mx-auto mb-4"></div>
          <p className="text-slate-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 p-4 md:p-6" data-testid="dashboard">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold gradient-text mb-2">
              Webull Trading Dashboard
            </h1>
            <p className="text-slate-400">SPY Options Automated Trading</p>
          </div>
          
          <div className="flex gap-2">
            <Button
              onClick={handleRefresh}
              variant="outline"
              className="border-slate-700 bg-slate-800 hover:bg-slate-700"
              disabled={refreshing}
              data-testid="refresh-button"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              onClick={handleLogout}
              variant="outline"
              className="border-red-700 text-red-400 hover:bg-red-900/20"
              data-testid="logout-button"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto">
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="bg-slate-800 border-slate-700">
            <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
            <TabsTrigger value="trade" data-testid="tab-trade">Trade</TabsTrigger>
            <TabsTrigger value="signals" data-testid="tab-signals">Signals</TabsTrigger>
            <TabsTrigger value="history" data-testid="tab-history">History</TabsTrigger>
            <TabsTrigger value="settings" data-testid="tab-settings">Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <AccountOverview account={account} />
            
            {/* Bot Control & Analysis Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <BotStatusWidget />
              <NoTradeReasonWidget />
            </div>
            
            {/* ORB & Supply/Demand Zones Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <OrbStatusWidget />
              <SupplyDemandWidget />
            </div>
            
            {/* Positions - Full Width for Better Visibility */}
            <Positions positions={positions} onRefresh={fetchData} />
            
            {/* Orders & P/L */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <Orders orders={orders} onRefresh={fetchData} />
              </div>
              <div>
                <ProfitLossBySymbol />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="trade">
            <TradePanel onTradeComplete={fetchData} />
          </TabsContent>

          <TabsContent value="signals" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <TechnicalSignalsWidget />
              <SupplyDemandWidget />
            </div>
            <TradingSignals />
          </TabsContent>

          <TabsContent value="history">
            <OrderHistory />
          </TabsContent>

          <TabsContent value="settings">
            <Settings />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default Dashboard;
