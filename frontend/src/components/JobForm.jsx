import React, { useState } from 'react';
import { AlertCircle, Check } from 'lucide-react';
import { apiUrl } from '../lib/api';

export default function JobForm({ onJobCreated }) {
  const [source, setSource] = useState('mercadolibre');
  const [queryInput, setQueryInput] = useState('');
  const [isUrlInput, setIsUrlInput] = useState(false);
  const [filterMode, setFilterMode] = useState('smart');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const payload = {
        source,
        query_url: isUrlInput ? queryInput : null,
        query_string: !isUrlInput ? queryInput : null,
        filter_mode: filterMode,
      };

      const response = await fetch(apiUrl('/api/jobs'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Failed to create job');
      }

      const job = await response.json();
      onJobCreated(job);
      setQueryInput('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card p-6">
      <h2 className="text-2xl font-semibold text-[color:var(--text)] mb-6 flex items-center gap-2">
        <span className="text-[color:var(--primary)]">⚙️</span> Crear Nuevo Job
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Source Selection */}
        <div>
          <label className="block text-sm font-semibold text-[color:var(--muted)] mb-2">
            Plataforma
          </label>
          <div className="flex gap-4">
            {['mercadolibre', 'amazon'].map((src) => (
              <label key={src} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  value={src}
                  checked={source === src}
                  onChange={(e) => setSource(e.target.value)}
                  className="w-4 h-4 accent-[color:var(--primary-strong)]"
                />
                <span className="text-[color:var(--text)] capitalize font-medium">
                  {src === 'mercadolibre' ? 'MercadoLibre 🇨🇴' : 'Amazon 🌎'}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Input Type Toggle */}
        <div>
          <label className="block text-sm font-semibold text-[color:var(--muted)] mb-2">
            Tipo de Búsqueda
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setIsUrlInput(false)}
              className={`px-4 py-2 rounded-lg font-medium transition ${
                !isUrlInput
                  ? 'bg-[color:var(--primary-strong)] text-[#051923]'
                  : 'bg-[color:var(--surface-2)] text-[color:var(--muted)] hover:bg-[color:var(--surface)]'
              }`}
            >
              Keyword
            </button>
            <button
              type="button"
              onClick={() => setIsUrlInput(true)}
              className={`px-4 py-2 rounded-lg font-medium transition ${
                isUrlInput
                  ? 'bg-[color:var(--primary-strong)] text-[#051923]'
                  : 'bg-[color:var(--surface-2)] text-[color:var(--muted)] hover:bg-[color:var(--surface)]'
              }`}
            >
              URL
            </button>
          </div>
        </div>

        {/* Amazon Filter Mode */}
        {source === 'amazon' && (
          <div>
            <label className="block text-sm font-semibold text-[color:var(--muted)] mb-2">
              Filtro Amazon
            </label>
            <select
              value={filterMode}
              onChange={(e) => setFilterMode(e.target.value)}
              className="input-field w-full px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-[color:var(--primary)]"
            >
              <option value="smart">Smart (recomendado)</option>
              <option value="strict">Estricto (solo match)</option>
              <option value="off">Desactivado</option>
            </select>
            <p className="text-xs text-[color:var(--muted)] mt-2">
              Smart filtra accesorios pero no deja la lista vacía.
            </p>
          </div>
        )}

        {/* Input Field */}
        <div>
          <label className="block text-sm font-semibold text-[color:var(--muted)] mb-2">
            {isUrlInput ? 'URL de Búsqueda' : 'Palabra Clave'}
          </label>
          <input
            type="text"
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            placeholder={
              isUrlInput
                ? 'https://listado.mercadolibre.com.co/...'
                : 'ej: "iPhone 15", "laptop gaming"'
            }
            className="input-field w-full px-4 py-2 rounded-lg placeholder-[color:var(--muted)] focus:outline-none focus:ring-2 focus:ring-[color:var(--primary)]"
            required
          />
        </div>

        {/* Error Message */}
        {error && (
          <div className="flex gap-2 p-3 bg-red-900/20 border border-red-700/60 rounded-lg text-red-200">
            <AlertCircle size={20} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full py-3 font-semibold rounded-lg transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin">⚙️</span> Iniciando...
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <Check size={20} /> Crear Job
            </span>
          )}
        </button>
      </form>
    </div>
  );
}
