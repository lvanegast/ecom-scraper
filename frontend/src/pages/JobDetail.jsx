import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ResultsTable from '../components/ResultsTable';
import PriceChart from '../components/PriceChart';
import { ArrowLeft, Loader } from 'lucide-react';
import { apiUrl } from '../lib/api';

export default function JobDetail() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedProduct, setSelectedProduct] = useState(null);

  useEffect(() => {
    const fetchJobDetail = async () => {
      try {
        const response = await fetch(apiUrl(`/api/jobs/${jobId}`));
        if (!response.ok) throw new Error('Job not found');

        const jobData = await response.json();
        setJob(jobData);

        // Fetch products
        const productsResponse = await fetch(
          apiUrl(`/api/products/${jobId}`)
        );

        if (productsResponse.ok) {
          const productsData = await productsResponse.json();
          setProducts(productsData);
          if (productsData.length > 0) {
            setSelectedProduct(productsData[0].id);
          }
        }
      } catch (error) {
        console.error('Error fetching job:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchJobDetail();
  }, [jobId]);

  if (loading) {
    return (
      <div className="min-h-screen p-8 flex items-center justify-center">
        <Loader size={48} className="text-[color:var(--primary)] animate-spin" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-[color:var(--primary)] hover:text-[color:var(--primary-strong)] mb-8"
          >
            <ArrowLeft size={20} /> Volver
          </button>
          <div className="text-center text-[color:var(--muted)]">Job no encontrado</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto animate-fade-in">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-[color:var(--primary)] hover:text-[color:var(--primary-strong)] mb-6"
          >
            <ArrowLeft size={20} /> Volver al Dashboard
          </button>

          <h1 className="text-4xl font-semibold text-[color:var(--text)] mb-2">
            Detalle del Job #{job.id}
          </h1>
          <p className="text-[color:var(--muted)]">
            {job.query_string || job.query_url}
          </p>
        </div>

        {/* Job Info */}
        <div className="card p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div>
              <p className="text-[color:var(--muted)] text-sm mb-1">Plataforma</p>
              <p className="text-[color:var(--text)] font-semibold capitalize">{job.source}</p>
            </div>
            <div>
              <p className="text-[color:var(--muted)] text-sm mb-1">Estado</p>
              <span
                className={`px-3 py-1 rounded-full font-semibold text-sm capitalize inline-block border ${
                  job.status === 'completed'
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                    : job.status === 'running'
                    ? 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30'
                    : job.status === 'failed'
                    ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                    : 'bg-slate-700/30 text-slate-300 border-slate-600/40'
                }`}
              >
                {job.status}
              </span>
            </div>
            <div>
              <p className="text-[color:var(--muted)] text-sm mb-1">Guardados</p>
              <p className="text-[color:var(--text)] font-semibold">{job.saved_count ?? job.total_products}</p>
            </div>
            <div>
              <p className="text-[color:var(--muted)] text-sm mb-1">Encontrados</p>
              <p className="text-[color:var(--text)] font-semibold">{job.found_count ?? '—'}</p>
            </div>
            <div>
              <p className="text-[color:var(--muted)] text-sm mb-1">Duplicados</p>
              <p className="text-[color:var(--text)] font-semibold">{job.duplicate_count ?? '—'}</p>
            </div>
            <div>
              <p className="text-[color:var(--muted)] text-sm mb-1">Errores</p>
              <p className="text-[color:var(--text)] font-semibold">{job.error_count ?? '—'}</p>
            </div>
            <div>
              <p className="text-[color:var(--muted)] text-sm mb-1">Creado</p>
              <p className="text-[color:var(--text)] font-semibold text-sm">
                {new Date(job.created_at).toLocaleString('es-AR')}
              </p>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left: Product List */}
          <div className="lg:col-span-1">
            <div className="card p-4 max-h-96 overflow-y-auto">
              <h3 className="font-semibold text-[color:var(--text)] mb-4">Productos</h3>
              <div className="space-y-2">
                {products.map((product) => (
                  <button
                    key={product.id}
                    onClick={() => setSelectedProduct(product.id)}
                    className={`w-full text-left p-3 rounded-lg transition ${
                      selectedProduct === product.id
                        ? 'bg-[color:var(--primary-strong)] text-[#051923]'
                        : 'bg-[color:var(--surface-2)] text-[color:var(--text)] hover:bg-[color:var(--surface)]'
                    }`}
                  >
                    <p className="text-sm font-medium truncate">
                      {product.title}
                    </p>
                    <p className="text-xs mt-1 font-bold text-emerald-300">
                      ${product.price.toFixed(2)}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Right: Chart */}
          <div className="lg:col-span-2">
            {selectedProduct && (
              <PriceChart productId={selectedProduct} />
            )}
          </div>
        </div>

        {/* Results Table */}
        <div className="mt-8">
          <ResultsTable products={products} jobId={job.id} source={job.source} />
        </div>
      </div>
    </div>
  );
}
