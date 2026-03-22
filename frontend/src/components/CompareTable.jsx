import React from 'react';

const formatPrice = (value, currency) => {
  if (value === null || value === undefined) return '-';
  const decimals = currency === 'COP' ? 0 : 2;
  try {
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: currency || 'COP',
      maximumFractionDigits: decimals,
      minimumFractionDigits: decimals,
    }).format(value);
  } catch (e) {
    return `${Number(value).toFixed(decimals)} ${currency || ''}`.trim();
  }
};

export default function CompareTable({ results }) {
  if (!results || results.length === 0) {
    return (
      <p className="text-[color:var(--muted)]">Sin resultados de comparación.</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm table-fixed min-w-[1100px]">
        <thead className="border-b border-[color:var(--border)]">
          <tr className="text-left text-[color:var(--muted)] font-semibold uppercase tracking-wider text-xs">
            <th className="pb-3 px-4 w-[30%]">MercadoLibre</th>
            <th className="pb-3 px-4 w-[10%]">Precio</th>
            <th className="pb-3 px-4 w-[30%]">Amazon</th>
            <th className="pb-3 px-4 w-[10%]">Precio</th>
            <th className="pb-3 px-4 w-[10%]">Score</th>
            <th className="pb-3 px-4 w-[10%] text-right">Δ Precio</th>
          </tr>
        </thead>
        <tbody>
          {results.map((row, idx) => {
            const ml = row.ml_product;
            const amz = row.amz_product;
            const diff = row.price_diff;
            const diffColor = diff === null
              ? 'text-[color:var(--muted)]'
              : diff > 0
              ? 'text-rose-300'
              : 'text-emerald-300';
            const confidence = row.is_confident ? 'Confianza alta' : 'Confianza baja';
            const confidenceColor = row.is_confident ? 'text-emerald-300' : 'text-amber-300';

            return (
              <tr
                key={`${ml?.id || 'ml'}-${idx}`}
                className="border-b border-[color:var(--border)] hover:bg-white/5 transition"
              >
                <td className="py-4 px-4">
                  <div className="flex gap-3">
                    {ml?.image_url && (
                      <img
                        src={ml.image_url}
                        alt={ml.title}
                        className="w-10 h-10 rounded object-cover bg-black/20"
                        onError={(e) => (e.target.style.display = 'none')}
                      />
                    )}
                    <div className="min-w-0">
                      <p className="text-[color:var(--text)] font-medium truncate">
                        {ml?.title || '—'}
                      </p>
                      {ml?.product_url && (
                        <a
                          href={ml.product_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[color:var(--primary)] text-xs hover:text-[color:var(--primary-strong)]"
                        >
                          Abrir →
                        </a>
                      )}
                    </div>
                  </div>
                </td>
                <td className="py-4 px-4 whitespace-nowrap text-[color:var(--text)]">
                  {formatPrice(ml?.price, ml?.currency)}
                </td>
                <td className="py-4 px-4">
                  {amz ? (
                    <div className="min-w-0">
                      <p className="text-[color:var(--text)] font-medium truncate">
                        {amz.title}
                      </p>
                      {amz.product_url && (
                        <a
                          href={amz.product_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[color:var(--primary)] text-xs hover:text-[color:var(--primary-strong)]"
                        >
                          Abrir →
                        </a>
                      )}
                    </div>
                  ) : (
                    <span className="text-[color:var(--muted)]">Sin match confiable</span>
                  )}
                </td>
                <td className="py-4 px-4 whitespace-nowrap text-[color:var(--text)]">
                  {formatPrice(amz?.price, amz?.currency)}
                </td>
                <td className="py-4 px-4 whitespace-nowrap text-[color:var(--text)]">
                  <div className="flex flex-col gap-1">
                    <span>{(row.score ?? 0).toFixed(2)}</span>
                    <span className={`text-[10px] ${confidenceColor}`}>{confidence}</span>
                  </div>
                </td>
                <td className={`py-4 px-4 whitespace-nowrap text-right ${diffColor}`}>
                  {diff === null ? '-' : formatPrice(Math.abs(diff), amz?.currency)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
