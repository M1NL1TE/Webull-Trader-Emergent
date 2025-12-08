import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function LiveChart() {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const supplyBoxRef = useRef(null);
  const demandBoxRef = useRef(null);
  const [zones, setZones] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [inZone, setInZone] = useState({ supply: false, demand: false });

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 600,
      layout: {
        background: { color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#1e293b',
      },
      timeScale: {
        borderColor: '#1e293b',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Add candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
    });

    candleSeriesRef.current = candleSeries;

    // Handle window resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    // Initial data fetch
    fetchChartData();
    fetchZones();

    // Update data every 5 seconds
    const dataInterval = setInterval(fetchChartData, 5000);
    const zonesInterval = setInterval(fetchZones, 5000);

    return () => {
      window.removeEventListener('resize', handleResize);
      clearInterval(dataInterval);
      clearInterval(zonesInterval);
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, []);

  const fetchChartData = async () => {
    try {
      // Fetch SPY live quote for latest price
      const quoteResponse = await axios.get(`${API}/quote/spy`);
      const latestPrice = quoteResponse.data.price;
      setCurrentPrice(latestPrice);

      // For now, we'll create a simple candlestick from current price
      // In production, you'd fetch actual historical candles from Webull
      const now = Math.floor(Date.now() / 1000);
      
      // Get existing data
      const existingData = candleSeriesRef.current.data() || [];
      
      // Add new candle every 5 seconds (demo purposes)
      if (existingData.length === 0 || now - existingData[existingData.length - 1].time > 300) {
        const newCandle = {
          time: now,
          open: latestPrice,
          high: latestPrice + 0.10,
          low: latestPrice - 0.10,
          close: latestPrice,
        };
        
        candleSeriesRef.current.update(newCandle);
      }

    } catch (error) {
      console.error('Error fetching chart data:', error);
    }
  };

  const fetchZones = async () => {
    try {
      const response = await axios.get(`${API}/bot/status`);
      const newZones = response.data.zones;
      
      if (!newZones) return;

      setZones(newZones);

      // Check if current price is in zones
      if (currentPrice) {
        const inSupply = currentPrice >= newZones.supply_bottom && currentPrice <= newZones.supply_top;
        const inDemand = currentPrice >= newZones.demand_bottom && currentPrice <= newZones.demand_top;
        setInZone({ supply: inSupply, demand: inDemand });
      }

      // Draw zone rectangles
      drawZones(newZones);

    } catch (error) {
      console.error('Error fetching zones:', error);
    }
  };

  const drawZones = (zones) => {
    if (!chartRef.current || !candleSeriesRef.current) return;

    // Remove old rectangles
    if (supplyBoxRef.current) {
      candleSeriesRef.current.removePriceLine(supplyBoxRef.current.top);
      candleSeriesRef.current.removePriceLine(supplyBoxRef.current.bottom);
    }
    if (demandBoxRef.current) {
      candleSeriesRef.current.removePriceLine(demandBoxRef.current.top);
      candleSeriesRef.current.removePriceLine(demandBoxRef.current.bottom);
    }

    // Draw supply zone (red)
    const supplyTop = candleSeriesRef.current.createPriceLine({
      price: zones.supply_top,
      color: '#ef4444',
      lineWidth: 2,
      lineStyle: 0, // Solid
      axisLabelVisible: true,
      title: 'Supply Zone',
    });

    const supplyBottom = candleSeriesRef.current.createPriceLine({
      price: zones.supply_bottom,
      color: '#ef4444',
      lineWidth: 2,
      lineStyle: 0,
      axisLabelVisible: true,
      title: '',
    });

    supplyBoxRef.current = { top: supplyTop, bottom: supplyBottom };

    // Draw demand zone (green)
    const demandTop = candleSeriesRef.current.createPriceLine({
      price: zones.demand_top,
      color: '#10b981',
      lineWidth: 2,
      lineStyle: 0,
      axisLabelVisible: true,
      title: 'Demand Zone',
    });

    const demandBottom = candleSeriesRef.current.createPriceLine({
      price: zones.demand_bottom,
      color: '#10b981',
      lineWidth: 2,
      lineStyle: 0,
      axisLabelVisible: true,
      title: '',
    });

    demandBoxRef.current = { top: demandTop, bottom: demandBottom };
  };

  return (
    <Card className="glass border-slate-700">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-2xl font-bold text-white">SPY Live Chart</CardTitle>
          <div className="flex items-center gap-3">
            {currentPrice && (
              <div className="text-right">
                <div className="text-2xl font-bold text-white">${currentPrice.toFixed(2)}</div>
                <div className="text-xs text-slate-400">5-min refresh</div>
              </div>
            )}
            {inZone.supply && (
              <Badge className="bg-red-500/20 text-red-300 border-red-700">
                In Supply Zone
              </Badge>
            )}
            {inZone.demand && (
              <Badge className="bg-green-500/20 text-green-300 border-green-700">
                In Demand Zone
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div ref={chartContainerRef} style={{ position: 'relative' }} />
        
        {zones && (
          <div className="grid grid-cols-2 gap-4 mt-4">
            <div className="p-4 bg-red-500/10 border border-red-700/30 rounded-lg">
              <div className="text-sm text-red-300 font-semibold mb-1">Supply Zone</div>
              <div className="text-xs text-red-200/80">
                ${zones.supply_bottom.toFixed(2)} - ${zones.supply_top.toFixed(2)}
              </div>
            </div>
            <div className="p-4 bg-green-500/10 border border-green-700/30 rounded-lg">
              <div className="text-sm text-green-300 font-semibold mb-1">Demand Zone</div>
              <div className="text-xs text-green-200/80">
                ${zones.demand_bottom.toFixed(2)} - ${zones.demand_top.toFixed(2)}
              </div>
            </div>
          </div>
        )}

        <div className="mt-4 p-3 bg-blue-500/10 border border-blue-700/30 rounded-lg">
          <div className="text-xs text-blue-200/80 space-y-1">
            <p><strong>How to read:</strong></p>
            <p>• <span className="text-red-400">Red lines</span> = Supply zone (resistance)</p>
            <p>• <span className="text-green-400">Green lines</span> = Demand zone (support)</p>
            <p>• Chart updates every 5 seconds with bot's zone calculations</p>
            <p>• Zones calculated from 15-min candles (195 bar lookback)</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default LiveChart;
