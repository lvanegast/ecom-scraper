# EcomScraper

Herramienta de scraping ecommerce con backend en FastAPI, frontend en React y PostgreSQL. El proyecto permite lanzar jobs de scraping sobre MercadoLibre y Amazon, ver logs en vivo, explorar resultados, comparar productos y exportar datos.

## Estado actual

- MercadoLibre es la fuente principal y la más estable.
- Amazon funciona con Playwright en modo best-effort.
- El stack completo ya puede correr con Docker.
- La agrupación de productos en MercadoLibre es visual y heurística.

## Inicio rápido

### Docker completo

Este es el flujo recomendado.

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

Credenciales de pgAdmin:

- email: `admin@ecomscraper.local`
- password: `admin`

Validación rápida:

1. Abre `http://localhost:3000`
2. Crea un job desde la UI
3. Revisa el panel de logs y la tabla de resultados

## Servicios Docker

`docker-compose.yml` levanta:

- `postgres`
- `backend`
- `frontend`
- `pgadmin`

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

## Desarrollo local alterno

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
cp .env.example .env
./venv/bin/alembic upgrade head
python main.py
```

### Frontend local

```bash
cd frontend
npm install
npm run dev
```

## Variables de entorno

Con Docker completo, no necesitas crear `.env` manualmente para arrancar el proyecto local.

Los archivos `.env` quedan como opción para:

- desarrollo local fuera de Docker
- cambiar configuración sin editar código
- preparar despliegue en EC2 o ambientes distintos

### Backend local

Archivo opcional: `backend/.env`

```env
DATABASE_URL=postgresql+asyncpg://scraper:scraper@localhost:5432/ecom_scraper
PYTHONUNBUFFERED=1
ENVIRONMENT=development
```

Variable útil para Amazon:

```bash
AMAZON_MAX_PAGES=3 python main.py
```

### Frontend local

Archivo opcional: `frontend/.env`

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
- Infra: PostgreSQL 16, pgAdmin, Docker Compose

## Notas importantes

- El frontend en Docker se sirve con Nginx y hace proxy a `/api` y `/ws`.
- El backend en Docker usa una imagen con Playwright + Chromium.
- Si cambias lógica de scraping, debes correr jobs nuevos para ver el efecto en la base.
- Amazon puede devolver resultados inconsistentes o activar bloqueos anti-bot.
- MercadoLibre cambia HTML con frecuencia, así que algunos selectores pueden requerir mantenimiento.
- La captura de imágenes de MercadoLibre es best-effort.

## Archivos clave

- Backend principal: [/home/lvanegas/Downloads/scrap/ecom-scraper/backend/main.py](/home/lvanegas/Downloads/scrap/ecom-scraper/backend/main.py)
- Jobs: [/home/lvanegas/Downloads/scrap/ecom-scraper/backend/jobs.py](/home/lvanegas/Downloads/scrap/ecom-scraper/backend/jobs.py)
- Scraper MercadoLibre: [/home/lvanegas/Downloads/scrap/ecom-scraper/backend/scraper/mercadolibre.py](/home/lvanegas/Downloads/scrap/ecom-scraper/backend/scraper/mercadolibre.py)
- Scraper Amazon: [/home/lvanegas/Downloads/scrap/ecom-scraper/backend/scraper/amazon.py](/home/lvanegas/Downloads/scrap/ecom-scraper/backend/scraper/amazon.py)
- Comparación: [/home/lvanegas/Downloads/scrap/ecom-scraper/backend/compare.py](/home/lvanegas/Downloads/scrap/ecom-scraper/backend/compare.py)
- Tabla de resultados: [/home/lvanegas/Downloads/scrap/ecom-scraper/frontend/src/components/ResultsTable.jsx](/home/lvanegas/Downloads/scrap/ecom-scraper/frontend/src/components/ResultsTable.jsx)

## Troubleshooting

### `Address already in use`

Algún proceso local ya ocupa el puerto.

```bash
lsof -i :8000
lsof -i :3000
```

### `FATAL: database "scraper" does not exist`

El `healthcheck` de Docker debe apuntar a `ecom_scraper`, no a `scraper`.

### `Failed to fetch`

Verifica:

- frontend activo en `http://localhost:3000`
- backend activo en `http://localhost:8000/api/health`

### Playwright falla en Docker o servidor

Revisa:

```bash
docker-compose logs -f backend
```

## Licencia

MIT
