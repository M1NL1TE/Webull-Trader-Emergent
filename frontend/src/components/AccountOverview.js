import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { DollarSign, TrendingUp, TrendingDown, Activity } from 'lucide-react';

function AccountOverview({ account }) {
  if (!account || !account.accountMembers) {
    return null;
  }

  const accountData = account.accountMembers.reduce((acc, item) => {
    acc[item.key] = item.value;
    return acc;
  }, {});

  const netLiquidation = parseFloat(accountData.netLiquidation || 0);
  const totalPL = parseFloat(accountData.unrealizedProfitLoss || 0);
  const cashBalance = parseFloat(accountData.cashBalance || 0);
  const buyingPower = parseFloat(accountData.buyingPower || 0);

  const stats = [
    {
      title: 'Account Value',
      value: `$${netLiquidation.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      icon: DollarSign,
      color: 'text-cyan-400',
      bgColor: 'bg-cyan-500/10'
    },
    {
      title: 'Total P/L',
      value: `$${Math.abs(totalPL).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      icon: totalPL >= 0 ? TrendingUp : TrendingDown,
      color: totalPL >= 0 ? 'text-green-400' : 'text-red-400',
      bgColor: totalPL >= 0 ? 'bg-green-500/10' : 'bg-red-500/10',
      prefix: totalPL >= 0 ? '+' : '-'
    },
    {
      title: 'Cash Balance',
      value: `$${cashBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      icon: DollarSign,
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/10'
    },
    {
      title: 'Buying Power',
      value: `$${buyingPower.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      icon: Activity,
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/10'
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="account-overview">
      {stats.map((stat, index) => {
        const Icon = stat.icon;
        return (
          <Card key={index} className="glass border-slate-700 card-hover" data-testid={`stat-card-${stat.title.toLowerCase().replace(/\s+/g, '-')}`}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">
                {stat.title}
              </CardTitle>
              <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                <Icon className={`w-4 h-4 ${stat.color}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${stat.color}`}>
                {stat.prefix || ''}{stat.value}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

export default AccountOverview;
