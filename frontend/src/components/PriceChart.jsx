import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { TrendingDown, TrendingUp } from 'lucide-react';
import { apiUrl } from '../lib/api';

export default function PriceChart({ productId }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [productTitle, setProductTitle] = useState('');

  useEffect(() => {
    const fetchPriceHistory = async () => {
      try {
        if (!productId) return;

        const response = await fetch(
          apiUrl(`/api/products/${productId}/price-history`)
        );

        if (!response.ok) throw new Error('Failed to fetch price history');

        const result = await response.json();
        setProductTitle(result.title);

        // Format data for Recharts
        const chartData = result.history.map((item) => ({
          date: new Date(item.scraped_at).toLocaleDateString('es-AR'),
          time: new Date(item.scraped_at).toLocaleTimeString('es-AR', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          price: item.price,
        }));

        setData(chartData);
      } catch (error) {
        console.error('Error fetching price history:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPriceHistory();
  }, [productId]);

  if (loading) {
    return (
      <div className="card p-6 h-96 flex items-center justify-center">
        <p className="text-[color:var(--muted)]">Cargando historial de precios...</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="card p-6 h-96 flex items-center justify-center">
        <p className="text-[color:var(--muted)]">Sin historial de precios</p>
      </div>
    );
  }

  const minPrice = Math.min(...data.map((d) => d.price));
  const maxPrice = Math.max(...data.map((d) => d.price));
  const currentPrice = data[data.length - 1].price;
  const previousPrice = data[0].price;
  const priceChange = currentPrice - previousPrice;
  const percentChange = ((priceChange / previousPrice) * 100).toFixed(2);

  return (
    <div className="card p-6">
      <div className="mb-6">
        <h3 className="text-2xl font-semibold text-[color:var(--text)] mb-2">📈 Historial de Precios</h3>
        <p className="text-[color:var(--muted)] text-sm">{productTitle}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 pb-6 border-b border-[color:var(--border)]">
        <div className="card-soft p-4">
          <p className="text-[color:var(--muted)] text-sm mb-1">Precio Actual</p>
          <p className="text-[color:var(--text)] text-2xl font-semibold">${currentPrice.toFixed(2)}</p>
        </div>
        <div className="card-soft p-4">
          <p className="text-[color:var(--muted)] text-sm mb-1">Precio Mínimo</p>
          <p className="text-emerald-300 text-2xl font-semibold">${minPrice.toFixed(2)}</p>
        </div>
        <div className="card-soft p-4">
          <p className="text-[color:var(--muted)] text-sm mb-1">Precio Máximo</p>
          <p className="text-amber-300 text-2xl font-semibold">${maxPrice.toFixed(2)}</p>
        </div>
        <div className="card-soft p-4">
          <p className="text-[color:var(--muted)] text-sm mb-1">Cambio Total</p>
          <div className="flex items-center gap-2">
            {priceChange < 0 ? (
              <TrendingDown size={24} className="text-emerald-300" />
            ) : (
              <TrendingUp size={24} className="text-rose-300" />
            )}
            <div>
              <p className={`text-2xl font-semibold ${priceChange < 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                ${Math.abs(priceChange).toFixed(2)}
              </p>
              <p className={`text-xs ${priceChange < 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                {percentChange}%
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={300}>
        <LineChart
          data={data}
          margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2a37" />
          <XAxis
            dataKey="date"
            stroke="#94a3b8"
            style={{ fontSize: '12px' }}
          />
          <YAxis stroke="#94a3b8" style={{ fontSize: '12px' }} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#0f172a',
              border: '1px solid #1f2a37',
              borderRadius: '8px',
              color: '#fff',
            }}
            formatter={(value) => `$${value.toFixed(2)}`}
            labelStyle={{ color: '#94a3b8' }}
          />
          <Legend wrapperStyle={{ color: '#94a3b8' }} />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#22d3ee"
            dot={{ fill: '#22d3ee', r: 4 }}
            activeDot={{ r: 6 }}
            strokeWidth={2}
            name="Precio"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
