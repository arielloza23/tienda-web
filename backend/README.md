# Backend Tienda Web

## Requisitos

- Python 3.11+
- PostgreSQL disponible

## Instalación

```bash
python -m venv .venv
. .venv/bin/activate  # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
cp .env.example .env
```

## Ejecutar la API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Base de datos

La configuración por defecto usa PostgreSQL usando `DATABASE_URL` en `.env`. Para pruebas locales y desarrollo rápido, se puede usar SQLite moviendo la variable de entorno.

## Migraciones con Alembic

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
