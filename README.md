# EcomScraper

Herramienta de scraping ecommerce con backend en FastAPI, frontend en React y PostgreSQL. Permite lanzar jobs de scraping sobre MercadoLibre y Amazon, ver logs en vivo, explorar resultados, comparar productos y exportar datos.

## Estado actual

- MercadoLibre es la fuente principal y la más estable.
- Amazon funciona con Playwright en modo best-effort.
- El stack ya está dockerizado para local y para despliegue en nube.
- La agrupación de productos en MercadoLibre sigue siendo visual y heurística.

## Arquitectura

### Local

`docker-compose.yml` levanta:

- `postgres`
- `backend`
- `frontend`
- `pgadmin`

### Producción / AWS

`docker-compose.prod.yml` levanta:

- `backend`
- `frontend`

En producción la base de datos sale del contenedor y pasa a Amazon RDS mediante `DATABASE_URL`.

## Archivos de entorno

El proyecto usa solo dos archivos reales, ambos ignorados por Git:

- `.env`: configuración local con Docker
- `.env.prod`: configuración de producción para EC2 + RDS

No subas esos archivos al repositorio.

## Inicio rápido local

1. Crea `ecom-scraper/.env` con este contenido:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tu-clave-local
POSTGRES_DB=ecom_scraper
DATABASE_URL=postgresql+asyncpg://postgres:tu-clave-local@postgres:5432/ecom_scraper
ENVIRONMENT=production
AMAZON_MAX_PAGES=3
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:5173
PGADMIN_DEFAULT_EMAIL=admin@ecomscraper.local
PGADMIN_DEFAULT_PASSWORD=admin
```

2. Levanta el stack:

```bash
cd ecom-scraper
docker-compose up -d --build
```

Servicios:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Health: `http://localhost:8000/api/health`
- Docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- pgAdmin: `http://localhost:5050`

Validación rápida:

1. Abre `http://localhost:3000`
2. Crea un job desde la UI
3. Revisa logs en vivo y la tabla de resultados

Comandos útiles:

```bash
docker-compose up -d --build
docker-compose ps
docker-compose logs -f
docker-compose down
```

Si quieres borrar también el volumen de PostgreSQL:

```bash
docker-compose down -v
```

## Despliegue base en AWS EC2 + RDS

1. Crea `ecom-scraper/.env.prod` con este contenido:

```env
DATABASE_URL=postgresql+asyncpg://postgres:tu-clave-rds@ecom-scraper.cc124kes8ijq.us-east-1.rds.amazonaws.com:5432/ecom-scraper
ALLOWED_ORIGINS=http://54.87.44.159
AMAZON_MAX_PAGES=3
```

2. Levanta el stack de producción:

```bash
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Con ese archivo:

- `frontend` queda publicado en el puerto `80`
- `backend` queda accesible solo dentro de la red Docker
- `frontend` hace proxy a `/api` y `/ws` hacia `backend`
- RDS reemplaza al contenedor `postgres`

3. Validar:

- App: `http://54.87.44.159`
- Health vía frontend/proxy: `http://54.87.44.159/api/health`

4. Recomendaciones para AWS:

- Abre en el Security Group del EC2 solo `80`, `443` y `22`.
- Restringe `22` a tu IP cuando termines de configurar.
- No expongas `pgadmin` en producción.
- Permite que el Security Group de RDS acepte tráfico desde el EC2 en `5432`.
- Si vas a usar dominio, añade TLS con Nginx, Caddy o un balanceador.

## Desarrollo local alterno sin Docker completo

Si quieres desarrollar fuera de Docker, puedes levantar solo la base y correr backend/frontend localmente.

### Requisitos

- Docker y Docker Compose
- Python 3.10+
- Node.js 18+

### Base de datos

```bash
cd ecom-scraper
docker-compose up -d postgres pgadmin
```

### Backend local

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./venv/bin/alembic upgrade head
python main.py
```

Si quieres usar `backend/.env`, puedes definir por ejemplo:

```env
DATABASE_URL=postgresql+asyncpg://postgres:tu-clave-local@localhost:5432/ecom_scraper
PYTHONUNBUFFERED=1
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:5173
```

### Frontend local

```bash
cd frontend
npm install
npm run dev
```

Si quieres usar `frontend/.env`, puedes definir por ejemplo:

```env
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=EcomScraper
```

## Funcionalidades

- creación de jobs por keyword o URL
- logs en vivo por WebSocket
- tabla de resultados con filtros y orden
- exportación a CSV y JSON
- historial de precios
- comparación MercadoLibre vs Amazon
- filtro configurable para Amazon: `smart`, `strict`, `off`

## Endpoints principales

- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/products/{job_id}`
- `GET /api/products/{product_id}/price-history`
- `GET /api/compare/latest`

## Stack

- Backend: FastAPI, SQLAlchemy async, Alembic, Playwright, lxml, httpx
- Frontend: React 18, Vite, Tailwind, Recharts
- Infra local: PostgreSQL 16, pgAdmin, Docker Compose
- Infra prod: EC2 + Docker Compose + RDS

## Notas importantes

- El frontend en Docker se sirve con Nginx y hace proxy a `/api` y `/ws`.
- El backend en Docker usa una imagen con Playwright + Chromium.
- El backend soporta `ALLOWED_ORIGINS` por variable de entorno para CORS.
- Si cambias lógica de scraping, debes correr jobs nuevos para ver el efecto en la base.
- Amazon puede devolver resultados inconsistentes o activar bloqueos anti-bot.
- MercadoLibre cambia HTML con frecuencia, así que algunos selectores pueden requerir mantenimiento.
- La captura de imágenes de MercadoLibre es best-effort.

## Archivos clave

- `docker-compose.yml`
- `docker-compose.prod.yml`
- `backend/main.py`
- `backend/jobs.py`
- `backend/scraper/mercadolibre.py`
- `backend/scraper/amazon.py`
- `backend/compare.py`
- `frontend/src/components/ResultsTable.jsx`

## Troubleshooting

### `Address already in use`

Algún proceso local ya ocupa el puerto.

```bash
lsof -i :8000
lsof -i :3000
```

### `Failed to fetch`

Verifica:

- frontend activo en `http://localhost:3000`
- backend activo en `http://localhost:8000/api/health`

### Playwright falla en Docker o servidor

```bash
docker-compose logs -f backend
```

### Producción en EC2 no conecta a RDS

Revisa:

- `DATABASE_URL` correcto
- reglas del Security Group de RDS
- que el EC2 pueda salir a Internet si Playwright necesita acceso externo

## Licencia

MIT
