import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';

function Positions({ positions }) {
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
              const symbol = position.ticker?.symbol || 'N/A';

              return (
                <div
                  key={index}
                  className="p-4 bg-slate-800/50 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors"
                  data-testid={`position-${index}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h4 className="font-semibold text-white">{symbol}</h4>
                      <p className="text-sm text-slate-400">Quantity: {quantity}</p>
                    </div>
                    <Badge className={isProfit ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                      {isProfit ? '+' : ''}
                      ${Math.abs(unrealizedPL).toFixed(2)}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-slate-400">Cost: </span>
                      <span className="text-white">${costPrice.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Last: </span>
                      <span className="text-white">${lastPrice.toFixed(2)}</span>
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
