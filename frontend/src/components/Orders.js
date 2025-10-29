import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { X } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function Orders({ orders, onRefresh }) {
  const handleCancel = async (orderId) => {
    try {
      await axios.delete(`${API}/trade/order/${orderId}`);
      toast.success('Order cancelled successfully');
      onRefresh();
    } catch (error) {
      toast.error('Failed to cancel order');
    }
  };

  if (!orders || orders.length === 0) {
    return (
      <Card className="glass border-slate-700" data-testid="orders-card">
        <CardHeader>
          <CardTitle className="text-slate-200">Open Orders</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-slate-400">
            <p>No open orders</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="glass border-slate-700" data-testid="orders-card">
      <CardHeader>
        <CardTitle className="text-slate-200 flex items-center justify-between">
          <span>Open Orders</span>
          <Badge variant="outline" className="text-amber-400 border-amber-700">
            {orders.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-4">
            {orders.map((order, index) => {
              const symbol = order.ticker?.symbol || 'N/A';
              const action = order.action || 'N/A';
              const orderType = order.orderType || 'N/A';
              const quantity = order.totalQuantity || 0;
              const price = parseFloat(order.lmtPrice || 0);
              const status = order.status || 'Working';

              return (
                <div
                  key={index}
                  className="p-4 bg-slate-800/50 rounded-lg border border-slate-700"
                  data-testid={`order-${index}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h4 className="font-semibold text-white">{symbol}</h4>
                      <p className="text-sm text-slate-400">
                        {action} {quantity} @ ${price.toFixed(2)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-amber-400 border-amber-700">
                        {status}
                      </Badge>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0 text-red-400 hover:text-red-300 hover:bg-red-900/20"
                        onClick={() => handleCancel(order.orderId)}
                        data-testid={`cancel-order-${index}`}
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="text-sm">
                    <span className="text-slate-400">Type: </span>
                    <span className="text-white">{orderType}</span>
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

export default Orders;
