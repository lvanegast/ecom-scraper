import React, { useEffect, useRef } from 'react';
import { AlertCircle, CheckCircle, InfoIcon, AlertTriangle } from 'lucide-react';
import { wsUrl } from '../lib/api';

const getLogIcon = (level) => {
  switch (level) {
    case 'success':
      return <CheckCircle size={18} className="text-[color:var(--success)]" />;
    case 'warning':
      return <AlertTriangle size={18} className="text-[color:var(--warning)]" />;
    case 'error':
      return <AlertCircle size={18} className="text-[color:var(--danger)]" />;
    default:
      return <InfoIcon size={18} className="text-[color:var(--primary)]" />;
  }
};

const getLogBgColor = (level) => {
  switch (level) {
    case 'success':
      return 'bg-emerald-900/20 border-l-4 border-emerald-500';
    case 'warning':
      return 'bg-amber-900/20 border-l-4 border-amber-500';
    case 'error':
      return 'bg-rose-900/20 border-l-4 border-rose-500';
    default:
      return 'bg-cyan-900/20 border-l-4 border-cyan-500';
  }
};

export default function LiveLog({ jobId }) {
  const [logs, setLogs] = React.useState([]);
  const [isConnected, setIsConnected] = React.useState(false);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!jobId) return;

    const ws = new WebSocket(wsUrl(`/ws/logs/${jobId}`));

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setLogs([]);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs((prevLogs) => [...prevLogs, data]);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket closed');
      setIsConnected(false);
    };

    wsRef.current = ws;

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [jobId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-semibold text-[color:var(--text)]">📡 Log en Vivo</h3>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
              <span className="text-sm text-emerald-300">Conectado</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 bg-slate-500 rounded-full"></span>
              <span className="text-sm text-[color:var(--muted)]">Desconectado</span>
            </>
          )}
        </div>
      </div>

      <div className="card-soft h-96 overflow-y-auto p-4 space-y-2 font-mono text-sm">
        {logs.length === 0 ? (
          <div className="text-[color:var(--muted)] text-center py-8">
            <p>Esperando logs...</p>
          </div>
        ) : (
          logs.map((log, index) => (
            <div
              key={index}
              className={`flex gap-3 p-2 rounded ${getLogBgColor(log.level)}`}
            >
              <div className="flex-shrink-0 mt-0.5">
                {getLogIcon(log.level)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start gap-2">
                  <span className="text-[color:var(--muted)] text-xs">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-[color:var(--text)] break-words">{log.message}</p>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
