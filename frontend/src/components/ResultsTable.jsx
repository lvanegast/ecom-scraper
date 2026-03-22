import React, { useMemo, useState } from 'react';
import { Download, ChevronUp, ChevronDown, Star, DollarSign, Package } from 'lucide-react';
import { apiUrl } from '../lib/api';

export default function ResultsTable({ products, jobId, source }) {
  const [sortBy, setSortBy] = useState('scraped_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [filterMinPrice, setFilterMinPrice] = useState('');
  const [filterMaxPrice, setFilterMaxPrice] = useState('');
  const [filterMinRating, setFilterMinRating] = useState('');
  const [groupedView, setGroupedView] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({});

  const isMercadoLibre = (source || '').toLowerCase() === 'mercadolibre';

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

  const getHost = (url) => {
    if (!url) return '';
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch (e) {
      return '';
    }
  };

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const STOPWORDS = useMemo(() => new Set([
    'nuevo', 'nueva', 'oferta', 'promocion', 'garantia', 'envio', 'gratis',
    'portatil', 'laptop', 'notebook', 'computador', 'pc', 'tablet',
    'con', 'sin', 'de', 'para', 'y', 'el', 'la', 'los', 'las',
    'color', 'edition', 'version',
    'ram', 'ssd', 'hdd', 'nvme', 'fhd', 'uhd', 'ips', 'wuxga', 'touch',
    'windows', 'win', 'home', 'pro', 'gen', 'pulgadas', 'pulg', 'inch', 'in'
  ]), []);

  const normalizeText = (text) => {
    if (!text) return '';
    return text
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  };

  const extractFeatures = (title) => {
    const t = normalizeText(title);
    const tokens = t.split(' ').filter(Boolean);

    const ramMatch = t.match(/(\d{1,2})\s?gb\s*ram|\bram\s*(\d{1,2})\s?gb/);
    const ram = ramMatch ? (ramMatch[1] || ramMatch[2]) + 'gb' : '';

    const storageMatch = t.match(/(\d{1,2})(\s?tb|\s?gb)\s*(ssd|hdd|nvme|almacenamiento|storage)?/);
    let storage = '';
    if (storageMatch) {
      const num = storageMatch[1];
      const unit = storageMatch[2].replace(/\s/g, '');
      const hasStorageKeyword = storageMatch[3] || /ssd|hdd|nvme|almacenamiento|storage/.test(t);
      if (hasStorageKeyword || unit === 'tb') storage = `${num}${unit}`;
    }

    const screenMatch = t.match(/(\d{1,2}(?:\.\d)?)\s?(?:\"|pulg|pulgadas|in)/);
    const screen = screenMatch ? screenMatch[1] : '';

    const filteredTokens = tokens.filter((tok) => !STOPWORDS.has(tok));
    const alphanumTokens = filteredTokens.filter(
      (tok) =>
        tok.length >= 3 &&
        /[a-z]/.test(tok) &&
        /[0-9]/.test(tok)
    );

    const brand = filteredTokens.find((tok) => /^[a-z]+$/.test(tok)) || '';

    const coreTokens = [];
    for (const tok of filteredTokens) {
      if (tok.includes('gb') || tok.includes('tb')) continue;
      if (tok === 'ram' || tok === 'ssd' || tok === 'hdd' || tok === 'nvme') continue;
      if (tok.length < 4) continue;
      if (coreTokens.length < 6) coreTokens.push(tok);
    }
    const core = coreTokens.join(' ');

    return { ram, storage, screen, core, tokens: filteredTokens, alphanumTokens, brand };
  };

  const tokenSimilarity = (aTokens, bTokens) => {
    const aSet = new Set(aTokens);
    const bSet = new Set(bTokens);
    if (aSet.size === 0 || bSet.size === 0) return 0;
    let inter = 0;
    for (const t of aSet) if (bSet.has(t)) inter += 1;
    const union = aSet.size + bSet.size - inter;
    return union === 0 ? 0 : inter / union;
  };

  const tokenOverlap = (aTokens, bTokens) => {
    const aSet = new Set(aTokens);
    const bSet = new Set(bTokens);
    let inter = 0;
    for (const t of aSet) if (bSet.has(t)) inter += 1;
    return inter;
  };

  const groupProducts = (items) => {
    const groups = [];
    for (const p of items) {
      const f = extractFeatures(p.title || '');
      const baseTokens = f.tokens.filter((tok) => tok.length >= 2);
      const strongAlphaNum = f.alphanumTokens.filter((tok) => tok.length >= 4);
      const strongTokens = baseTokens.filter(
        (tok) => tok.length >= 5 || strongAlphaNum.includes(tok)
      );
      const signatureTokens = [
        f.brand,
        ...strongAlphaNum,
        f.ram,
        f.storage,
        f.screen,
        ...strongTokens.slice(0, 8),
      ].filter(Boolean);

      let matched = null;
      for (const g of groups) {
        if (f.brand && g.brand && f.brand !== g.brand) continue;
        const sim = tokenSimilarity(signatureTokens, g.signatureTokens);
        const modelOverlap = strongAlphaNum.some((t) => g.strongAlphaNum.has(t));
        const strongOverlap = tokenOverlap(strongTokens, Array.from(g.strongTokens));
        const ramOk = !f.ram || !g.ram || f.ram === g.ram;
        const storageOk = !f.storage || !g.storage || f.storage === g.storage;
        const screenOk = !f.screen || !g.screen || f.screen === g.screen;
        const price = p.price ?? 0;
        const priceOk = g.minPrice && g.maxPrice
          ? price >= g.minPrice * 0.6 && price <= g.maxPrice * 1.4
          : true;
        if (
          priceOk &&
          ramOk && storageOk && screenOk &&
          (
            modelOverlap ||
            strongOverlap >= 2 ||
            sim >= 0.35
          )
        ) {
          matched = g;
          break;
        }
      }

      if (!matched) {
        const fallbackKey = signatureTokens[0] || normalizeText(p.title || '').split(' ')[0] || 'x';
        matched = {
          key: `${fallbackKey}:${signatureTokens.join('-')}`,
          items: [],
          brand: f.brand || '',
          signatureTokens: new Set(signatureTokens),
          strongAlphaNum: new Set(strongAlphaNum),
          strongTokens: new Set(strongTokens),
          ram: f.ram || '',
          storage: f.storage || '',
          screen: f.screen || '',
          minPrice: 0,
          maxPrice: 0,
        };
        groups.push(matched);
      }

      matched.items.push(p);
      signatureTokens.forEach((t) => matched.signatureTokens.add(t));
      strongAlphaNum.forEach((t) => matched.strongAlphaNum.add(t));
      strongTokens.forEach((t) => matched.strongTokens.add(t));
      const price = p.price ?? 0;
      if (!matched.minPrice || price < matched.minPrice) matched.minPrice = price;
      if (!matched.maxPrice || price > matched.maxPrice) matched.maxPrice = price;
    }

    return groups.map((g) => {
      const prices = g.items.map((i) => i.price).filter((v) => v !== null && v !== undefined);
      const minPrice = prices.length ? Math.min(...prices) : 0;
      const maxPrice = prices.length ? Math.max(...prices) : 0;
      const best = g.items.reduce((acc, cur) => {
        if (!acc) return cur;
        return (cur.price ?? Infinity) < (acc.price ?? Infinity) ? cur : acc;
      }, null);
      const bestRating = g.items.reduce((acc, cur) => {
        if (!cur.rating) return acc;
        return Math.max(acc, cur.rating);
      }, 0);
      const itemsSorted = [...g.items].sort((a, b) => (a.price ?? 0) - (b.price ?? 0));
      return {
        ...g,
        minPrice,
        maxPrice,
        count: g.items.length,
        best,
        bestRating: bestRating || null,
        itemsSorted,
      };
    });
  };

  const filteredProducts = products.filter((p) => {
    if (filterMinPrice && p.price < parseFloat(filterMinPrice)) return false;
    if (filterMaxPrice && p.price > parseFloat(filterMaxPrice)) return false;
    if (filterMinRating && p.rating && p.rating < parseFloat(filterMinRating))
      return false;
    return true;
  });

  const sortedProducts = [...filteredProducts].sort((a, b) => {
    let aValue = a[sortBy];
    let bValue = b[sortBy];

    if (aValue === null || aValue === undefined) aValue = 0;
    if (bValue === null || bValue === undefined) bValue = 0;

    if (sortOrder === 'asc') {
      return aValue > bValue ? 1 : -1;
    } else {
      return aValue < bValue ? 1 : -1;
    }
  });

  const groupedProducts = useMemo(() => {
    if (!isMercadoLibre) return [];
    const groups = groupProducts(products);
    return groups.filter((g) => {
      if (filterMinPrice && g.minPrice < parseFloat(filterMinPrice)) return false;
      if (filterMaxPrice && g.maxPrice > parseFloat(filterMaxPrice)) return false;
      if (filterMinRating && g.bestRating && g.bestRating < parseFloat(filterMinRating))
        return false;
      return true;
    });
  }, [products, isMercadoLibre, filterMinPrice, filterMaxPrice, filterMinRating]);

  const groupedSorted = useMemo(() => {
    if (!groupedProducts.length) return [];
    const sorted = [...groupedProducts];
    sorted.sort((a, b) => {
      let aValue = a[sortBy];
      let bValue = b[sortBy];
      if (sortBy === 'price') {
        aValue = a.minPrice;
        bValue = b.minPrice;
      } else if (sortBy === 'max_price') {
        aValue = a.maxPrice;
        bValue = b.maxPrice;
      } else if (sortBy === 'rating') {
        aValue = a.bestRating || 0;
        bValue = b.bestRating || 0;
      }
      if (aValue === null || aValue === undefined) aValue = 0;
      if (bValue === null || bValue === undefined) bValue = 0;
      if (sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });
    return sorted;
  }, [groupedProducts, sortBy, sortOrder]);

  const handleExport = async (format) => {
    try {
      const response = await fetch(apiUrl('/api/export'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          job_id: jobId,
          format,
        }),
      });

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `products_${jobId}.${format === 'csv' ? 'csv' : 'json'}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export error:', error);
    }
  };

  const resultsCount = groupedView && isMercadoLibre ? groupedSorted.length : sortedProducts.length;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-2xl font-semibold text-[color:var(--text)]">
          📊 Resultados ({resultsCount})
        </h3>
        <div className="flex gap-2">
          {isMercadoLibre && (
            <button
              onClick={() => setGroupedView(!groupedView)}
              className="px-4 py-2 rounded-lg font-medium transition border border-cyan-500/40 text-cyan-200 bg-cyan-500/10 hover:bg-cyan-500/20"
            >
              {groupedView ? 'Ver lista' : 'Agrupar similares'}
            </button>
          )}
          <button
            onClick={() => handleExport('csv')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30"
          >
            <Download size={18} /> CSV
          </button>
          <button
            onClick={() => handleExport('json')}
            className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30"
          >
            <Download size={18} /> JSON
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 pb-6 border-b border-[color:var(--border)]">
        <div>
          <label className="text-sm font-semibold text-[color:var(--muted)] mb-1 block">
            Precio Mínimo
          </label>
          <input
            type="number"
            value={filterMinPrice}
            onChange={(e) => setFilterMinPrice(e.target.value)}
            placeholder="0"
            className="input-field w-full px-3 py-2 rounded-lg placeholder-[color:var(--muted)] focus:outline-none focus:ring-2 focus:ring-[color:var(--primary)]"
          />
        </div>
        <div>
          <label className="text-sm font-semibold text-[color:var(--muted)] mb-1 block">
            Precio Máximo
          </label>
          <input
            type="number"
            value={filterMaxPrice}
            onChange={(e) => setFilterMaxPrice(e.target.value)}
            placeholder="∞"
            className="input-field w-full px-3 py-2 rounded-lg placeholder-[color:var(--muted)] focus:outline-none focus:ring-2 focus:ring-[color:var(--primary)]"
          />
        </div>
        <div>
          <label className="text-sm font-semibold text-[color:var(--muted)] mb-1 block">
            Rating Mínimo
          </label>
          <input
            type="number"
            min="0"
            max="5"
            step="0.1"
            value={filterMinRating}
            onChange={(e) => setFilterMinRating(e.target.value)}
            placeholder="0"
            className="input-field w-full px-3 py-2 rounded-lg placeholder-[color:var(--muted)] focus:outline-none focus:ring-2 focus:ring-[color:var(--primary)]"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <div className="mb-2 text-xs text-[color:var(--muted)] md:hidden">
          Desliza horizontalmente para ver todas las columnas →
        </div>
        {groupedView && isMercadoLibre ? (
          <table className="w-full text-sm table-fixed min-w-[980px]">
            <thead className="border-b border-[color:var(--border)]">
              <tr className="text-left text-[color:var(--muted)] font-semibold uppercase tracking-wider text-xs">
                <th className="pb-3 px-4 w-[42%]">Grupo</th>
                <th
                  onClick={() => handleSort('price')}
                  className="pb-3 px-4 w-[14%] cursor-pointer hover:text-[color:var(--primary)] transition"
                >
                  <div className="flex items-center gap-1">
                    Precio Mín
                    {sortBy === 'price' && (
                      sortOrder === 'asc' ? <ChevronUp size={16} /> : <ChevronDown size={16} />
                    )}
                  </div>
                </th>
                <th
                  onClick={() => handleSort('max_price')}
                  className="pb-3 px-4 w-[14%] cursor-pointer hover:text-[color:var(--primary)] transition"
                >
                  <div className="flex items-center gap-1">
                    Precio Máx
                    {sortBy === 'max_price' && (
                      sortOrder === 'asc' ? <ChevronUp size={16} /> : <ChevronDown size={16} />
                    )}
                  </div>
                </th>
                <th className="pb-3 px-4 w-[12%]">Publicaciones</th>
                <th
                  onClick={() => handleSort('rating')}
                  className="pb-3 px-4 w-[10%] cursor-pointer hover:text-[color:var(--primary)] transition"
                >
                  <div className="flex items-center gap-1">
                    Rating
                    {sortBy === 'rating' && (
                      sortOrder === 'asc' ? <ChevronUp size={16} /> : <ChevronDown size={16} />
                    )}
                  </div>
                </th>
                <th className="pb-3 px-4 w-[8%] text-right">Link</th>
              </tr>
            </thead>
            <tbody>
              {groupedSorted.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-[color:var(--muted)]">
                    No hay grupos para mostrar
                  </td>
                </tr>
              ) : (
                groupedSorted.map((group) => {
                  const rep = group.best || group.items[0];
                  const host = getHost(rep?.product_url);
                  const isOpen = !!expandedGroups[group.key];
                  return (
                    <React.Fragment key={group.key}>
                      <tr className="border-b border-[color:var(--border)] hover:bg-white/5 transition">
                        <td className="py-4 px-4">
                          <div className="flex gap-3">
                            {rep?.image_url && (
                              <img
                                src={rep.image_url}
                                alt={rep.title}
                                className="w-12 h-12 rounded object-cover bg-gray-800"
                                onError={(e) => (e.target.style.display = 'none')}
                              />
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="text-[color:var(--text)] font-medium truncate text-sm leading-tight">
                                {rep?.title || 'Grupo'}
                              </p>
                              <p className="text-[color:var(--muted)] text-xs mt-1 truncate">
                                {host || rep?.product_url}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="py-4 px-4 whitespace-nowrap">
                          <span className="text-[color:var(--text)] font-semibold">
                            {formatPrice(group.minPrice, rep?.currency)}
                          </span>
                        </td>
                        <td className="py-4 px-4 whitespace-nowrap">
                          <span className="text-[color:var(--text)]">
                            {formatPrice(group.maxPrice, rep?.currency)}
                          </span>
                        </td>
                        <td className="py-4 px-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <span className="text-[color:var(--text)] font-semibold">
                              {group.count}
                            </span>
                            <button
                              onClick={() =>
                                setExpandedGroups((prev) => ({
                                  ...prev,
                                  [group.key]: !prev[group.key],
                                }))
                              }
                              className="text-xs px-2 py-1 rounded-md border border-slate-600/60 text-slate-200 hover:bg-white/5"
                            >
                              {isOpen ? 'Ocultar' : 'Ver'}
                            </button>
                          </div>
                        </td>
                        <td className="py-4 px-4 whitespace-nowrap">
                          {group.bestRating ? (
                            <div className="flex items-center gap-1">
                              <Star size={16} className="text-yellow-400 fill-yellow-400" />
                              <span className="text-yellow-300 font-semibold">
                                {group.bestRating.toFixed(1)}
                              </span>
                            </div>
                          ) : (
                            <span className="text-[color:var(--muted)]">-</span>
                          )}
                        </td>
                        <td className="py-4 px-4 text-right whitespace-nowrap">
                          {rep?.product_url ? (
                            <a
                              href={rep.product_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[color:var(--primary)] hover:text-[color:var(--primary-strong)] transition text-xs font-medium"
                            >
                              Abrir →
                            </a>
                          ) : (
                            <span className="text-[color:var(--muted)]">-</span>
                          )}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr className="border-b border-[color:var(--border)] bg-white/2">
                          <td colSpan="6" className="px-4 pb-4">
                            <div className="mt-2 grid grid-cols-1 gap-2">
                              {group.itemsSorted.map((item) => {
                                const itemHost = getHost(item.product_url);
                                return (
                                  <div
                                    key={item.id}
                                    className="flex items-center justify-between gap-3 rounded-lg border border-[color:var(--border)] px-3 py-2"
                                  >
                                    <div className="flex items-center gap-3 min-w-0">
                                      {item.image_url && (
                                        <img
                                          src={item.image_url}
                                          alt={item.title}
                                          className="w-10 h-10 rounded object-cover bg-gray-800"
                                          onError={(e) => (e.target.style.display = 'none')}
                                        />
                                      )}
                                      <div className="min-w-0">
                                        <p className="text-[color:var(--text)] text-sm truncate">
                                          {item.title}
                                        </p>
                                        <p className="text-[color:var(--muted)] text-xs truncate">
                                          {itemHost || item.product_url}
                                        </p>
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0">
                                      <span className="text-[color:var(--text)] font-semibold text-sm">
                                        {formatPrice(item.price, item.currency)}
                                      </span>
                                      {item.product_url && (
                                        <a
                                          href={item.product_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-[color:var(--primary)] hover:text-[color:var(--primary-strong)] transition text-xs font-medium"
                                        >
                                          Abrir →
                                        </a>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        ) : (
          <table className="w-full text-sm table-fixed min-w-[1100px]">
            <thead className="border-b border-[color:var(--border)]">
              <tr className="text-left text-[color:var(--muted)] font-semibold uppercase tracking-wider text-xs">
                <th className="pb-3 px-4 w-[32%]">Producto</th>
                <th
                  onClick={() => handleSort('price')}
                  className="pb-3 px-4 w-[12%] cursor-pointer hover:text-[color:var(--primary)] transition"
                >
                  <div className="flex items-center gap-1">
                    Precio
                    {sortBy === 'price' && (
                      sortOrder === 'asc' ? <ChevronUp size={16} /> : <ChevronDown size={16} />
                    )}
                  </div>
                </th>
                <th className="pb-3 px-4 w-[12%]">Precio Original</th>
                <th className="pb-3 px-4 w-[10%]">Descuento</th>
                <th className="pb-3 px-4 w-[10%]">Stock</th>
                <th
                  onClick={() => handleSort('rating')}
                  className="pb-3 px-4 w-[12%] cursor-pointer hover:text-[color:var(--primary)] transition"
                >
                  <div className="flex items-center gap-1">
                    Rating
                    {sortBy === 'rating' && (
                      sortOrder === 'asc' ? <ChevronUp size={16} /> : <ChevronDown size={16} />
                    )}
                  </div>
                </th>
                <th className="pb-3 px-4 w-[12%] text-right">Link</th>
              </tr>
            </thead>
            <tbody>
              {sortedProducts.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-[color:var(--muted)]">
                    No hay productos para mostrar
                  </td>
                </tr>
              ) : (
                sortedProducts.map((product) => (
                  (() => {
                    const host = getHost(product.product_url);
                    return (
                  <tr
                    key={product.id}
                    className="border-b border-[color:var(--border)] hover:bg-white/5 transition"
                  >
                    <td className="py-4 px-4">
                      <div className="flex gap-3">
                        {product.image_url && (
                          <img
                            src={product.image_url}
                            alt={product.title}
                            className="w-12 h-12 rounded object-cover bg-gray-800"
                            onError={(e) => (e.target.style.display = 'none')}
                          />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-[color:var(--text)] font-medium truncate text-sm leading-tight">
                            {product.title}
                          </p>
                          <p className="text-[color:var(--muted)] text-xs mt-1 truncate">
                            {host || product.product_url}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-1">
                        <DollarSign size={16} className="text-emerald-400" />
                        <span className="text-[color:var(--text)] font-semibold">
                          {formatPrice(product.price, product.currency)}
                        </span>
                      </div>
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      {product.original_price ? (
                        <span className="text-[color:var(--text)]">
                          {formatPrice(product.original_price, product.currency)}
                        </span>
                      ) : (
                        <span className="text-[color:var(--muted)]">-</span>
                      )}
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      {product.discount_pct ? (
                        <div className="flex items-center gap-1">
                          <Package size={16} className="text-amber-400" />
                          <span className="text-amber-300 font-semibold">
                            -{product.discount_pct.toFixed(1)}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-[color:var(--muted)]">-</span>
                      )}
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      {product.stock_status ? (
                        <span className="text-[color:var(--text)]">{product.stock_status}</span>
                      ) : (
                        <span className="text-[color:var(--muted)]">-</span>
                      )}
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      {product.rating ? (
                        <div className="flex items-center gap-1">
                          <Star size={16} className="text-yellow-400 fill-yellow-400" />
                          <span className="text-yellow-300 font-semibold">
                            {product.rating.toFixed(1)}
                          </span>
                          {product.review_count && (
                            <span className="text-[color:var(--muted)] text-xs">
                              ({product.review_count})
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-[color:var(--muted)]">-</span>
                      )}
                    </td>
                    <td className="py-4 px-4 text-right whitespace-nowrap">
                      {product.product_url ? (
                        <a
                          href={product.product_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[color:var(--primary)] hover:text-[color:var(--primary-strong)] transition text-xs font-medium"
                        >
                          Abrir →
                        </a>
                      ) : (
                        <span className="text-[color:var(--muted)]">-</span>
                      )}
                    </td>
                  </tr>
                    );
                  })()
                ))
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
