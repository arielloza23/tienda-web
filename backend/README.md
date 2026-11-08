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
alembic upgrade head   # crea o actualiza las tablas (la API ya no las crea al arrancar)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Base de datos

La configuración por defecto usa PostgreSQL usando `DATABASE_URL` en `.env`. Para pruebas locales y desarrollo rápido, se puede usar SQLite cambiando esa variable (sin `.env` se usa `sqlite:///./tienda_web.db`).

## Migraciones con Alembic

El esquema lo gestiona solo Alembic. Tras cambiar un modelo:

```bash
alembic revision --autogenerate -m "describe el cambio"   # revisa el archivo generado
alembic upgrade head
```

Las bases antiguas creadas con `create_all` (sin tabla `alembic_version`) se adoptan
automáticamente con `alembic upgrade head`: la migración inicial no recrea tablas existentes.
`tests/test_migrations.py` comprueba que las migraciones producen exactamente el esquema de los modelos.

## Autenticación y administración

Los endpoints públicos son: catálogo (`GET /products`), registro (`POST /users`), crear pedido (`POST /orders`) y login.
El resto (listar usuarios y pedidos, ver un pedido, cambiar su estado y crear productos) requiere un usuario **admin**.

1. Define un `SECRET_KEY` largo y aleatorio en `.env` (los tokens se firman con él).
2. Crea el primer administrador:

   ```bash
   python -m app.create_admin admin@tienda.com "Nombre Admin"
   ```

3. Obtén un token y úsalo en la cabecera `Authorization: Bearer <token>`:

   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "admin@tienda.com", "password": "..."}'
   ```

   En `/docs` puedes pulsar **Authorize** y pegar el token.
