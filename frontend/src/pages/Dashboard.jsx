import React, { useState, useEffect } from 'react';
import JobForm from '../components/JobForm';
import LiveLog from '../components/LiveLog';
import ResultsTable from '../components/ResultsTable';
import CompareTable from '../components/CompareTable';
import { Loader } from 'lucide-react';
import { apiUrl } from '../lib/api';

export default function Dashboard() {
  const [currentJob, setCurrentJob] = useState(null);
  const [products, setProducts] = useState([]);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [compareData, setCompareData] = useState(null);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [compareError, setCompareError] = useState('');
  const [compareInfo, setCompareInfo] = useState('');

  const handleJobCreated = (job) => {
    setCurrentJob(job);
    setProducts([]);
    setCompareData(null);
    setCompareError('');
    setCompareInfo('');
    console.log('Job created:', job);
  };

  const handleCompare = async () => {
    try {
      setLoadingCompare(true);
      setCompareError('');
      setCompareInfo('');
      const response = await fetch(apiUrl('/api/compare/latest'));
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Error comparando');
      }
      const data = await response.json();
      if (data?.message) {
        setCompareInfo(data.message);
      }
      setCompareData(data);
    } catch (error) {
      setCompareError(error.message || 'Error comparando');
    } finally {
      setLoadingCompare(false);
    }
  };

  // Poll for job status and products
  useEffect(() => {
    if (!currentJob) return;

    const interval = setInterval(async () => {
      try {
        // Check job status
        const jobResponse = await fetch(
          apiUrl(`/api/jobs/${currentJob.id}`)
        );

        if (jobResponse.ok) {
          const updatedJob = await jobResponse.json();
          setCurrentJob(updatedJob);

          // If job is running or completed, fetch products
          if (updatedJob.status === 'running' || updatedJob.status === 'completed') {
            setLoadingProducts(true);

            const productsResponse = await fetch(
              apiUrl(`/api/products/${currentJob.id}`)
            );

            if (productsResponse.ok) {
              const productsData = await productsResponse.json();
              setProducts(productsData);
            }

            setLoadingProducts(false);
          }
        }
      } catch (error) {
        console.error('Error polling job:', error);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [currentJob]);

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto animate-fade-in">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-5xl font-semibold mb-3 flex items-center gap-3">
            <span className="text-3xl">🛍️</span>
            <span className="bg-gradient-to-r from-cyan-300 via-emerald-300 to-teal-200 text-transparent bg-clip-text">
              EcomScraper
            </span>
          </h1>
          <p className="text-[color:var(--muted)] text-lg">
            Herramienta profesional de scraping de ecommerce en tiempo real
          </p>
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Form and Logs */}
          <div className="lg:col-span-1 space-y-8">
            <JobForm onJobCreated={handleJobCreated} />
            {currentJob && <LiveLog jobId={currentJob.id} />}
          </div>

          {/* Right Column - Results */}
          <div className="lg:col-span-2">
            {!currentJob ? (
              <div className="card p-12 flex items-center justify-center h-96">
                <div className="text-center">
                  <p className="text-[color:var(--muted)] text-lg mb-4">
                    Crea un nuevo job de scraping para ver resultados
                  </p>
                  <p className="text-slate-500 text-sm">
                    Usa el formulario a la izquierda para comenzar
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Job Status Card */}
                <div className="card p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-2xl font-semibold text-[color:var(--text)]">📋 Estado del Job</h2>
                    <span
                      className={`px-4 py-2 rounded-full font-semibold text-sm capitalize border ${
                        currentJob.status === 'completed'
                          ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                          : currentJob.status === 'running'
                          ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
                          : currentJob.status === 'failed'
                          ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                          : 'bg-slate-700/30 text-slate-300 border-slate-600/40'
                      }`}
                    >
                      {currentJob.status === 'running' && (
                        <span className="flex items-center gap-2">
                          <Loader size={16} className="animate-spin" />
                          {currentJob.status}
                        </span>
                      )}
                      {currentJob.status !== 'running' && currentJob.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-[color:var(--muted)] text-sm">Plataforma</p>
                      <p className="text-[color:var(--text)] font-semibold capitalize">
                        {currentJob.source}
                      </p>
                    </div>
                    <div>
                      <p className="text-[color:var(--muted)] text-sm">Guardados</p>
                      <p className="text-[color:var(--text)] font-semibold">
                        {loadingProducts ? '...' : currentJob.saved_count ?? currentJob.total_products}
                      </p>
                    </div>
                    <div>
                      <p className="text-[color:var(--muted)] text-sm">Encontrados</p>
                      <p className="text-[color:var(--text)] font-semibold">
                        {currentJob.found_count ?? '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-[color:var(--muted)] text-sm">Búsqueda</p>
                      <p className="text-[color:var(--text)] font-semibold truncate text-sm">
                        {currentJob.query_string || currentJob.query_url}
                      </p>
                    </div>
                    <div>
                      <p className="text-[color:var(--muted)] text-sm">Duplicados</p>
                      <p className="text-[color:var(--text)] font-semibold">
                        {currentJob.duplicate_count ?? '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-[color:var(--muted)] text-sm">Errores</p>
                      <p className="text-[color:var(--text)] font-semibold">
                        {currentJob.error_count ?? '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-[color:var(--muted)] text-sm">Creado</p>
                      <p className="text-[color:var(--text)] font-semibold text-sm">
                        {new Date(currentJob.created_at).toLocaleTimeString('es-AR')}
                      </p>
                    </div>
                  </div>

                  {currentJob.error_message && (
                    <div className="mt-4 p-3 bg-rose-900/20 border border-rose-700/50 rounded-lg text-rose-300 text-sm">
                      {currentJob.error_message}
                    </div>
                  )}
                </div>

                {/* Results Table */}
                <ResultsTable products={products} jobId={currentJob.id} source={currentJob.source} />

                {/* Compare Section */}
                <div className="card p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="text-xl font-semibold text-[color:var(--text)]">
                        🧩 Comparar MercadoLibre vs Amazon
                      </h3>
                      <p className="text-sm text-[color:var(--muted)]">
                        Usa los últimos jobs completados de cada plataforma
                      </p>
                    </div>
                    <button
                      onClick={handleCompare}
                      disabled={loadingCompare}
                      className="btn-primary px-4 py-2 rounded-lg font-semibold disabled:opacity-50"
                    >
                      {loadingCompare ? 'Comparando...' : 'Comparar ahora'}
                    </button>
                  </div>

                  {compareError && (
                    <div className="mt-2 p-3 bg-rose-900/20 border border-rose-700/50 rounded-lg text-rose-300 text-sm">
                      {compareError}
                    </div>
                  )}

                  {compareInfo && (
                    <div className="mt-2 p-3 bg-cyan-900/20 border border-cyan-700/50 rounded-lg text-cyan-200 text-sm">
                      {compareInfo}
                    </div>
                  )}

                  {compareData?.results && (
                    <div className="mt-6">
                      <CompareTable results={compareData.results} />
                    </div>
                  )}
                </div>

                {currentJob.status === 'running' && (
                  <div className="card p-8 flex items-center justify-center">
                    <div className="text-center">
                      <Loader size={48} className="text-[color:var(--primary)] animate-spin mx-auto mb-4" />
                      <p className="text-[color:var(--text)]">
                        Scraping en curso...
                      </p>
                      <p className="text-[color:var(--muted)] text-sm mt-2">
                        Esto puede tomar unos minutos
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
