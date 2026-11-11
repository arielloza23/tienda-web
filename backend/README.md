# Backend Tienda Web

## Requisitos

- Python 3.13 (versión del entorno local, fijada en `.python-version` en la raíz)
- PostgreSQL disponible

## Instalación

Desde la raíz del repositorio, con `uv` instalado:

```powershell
uv python install 3.13
uv venv --python 3.13 .venv
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Para ejecutar las pruebas en Windows:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

Alternativamente, desde `backend`, usando Python 3.13:

```bash
python3.13 -m venv .venv
. .venv/bin/activate  # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
cp .env.example .env
```

## Ejecutar la API

```bash
alembic upgrade head   # crea o actualiza las tablas (la API ya no las crea al arrancar)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Desplegar gratis en Render

El archivo `render.yaml` en la raíz prepara un Web Service Free con Python
3.13.18, autenticación activa, clave de firma generada por Render y comprobación
en `/health`. Al arrancar aplica las migraciones antes de iniciar la API.

1. En Render, conecta GitHub y permite acceso al repositorio privado
   `arielloza23/tienda-web`.
2. Elige **New > Blueprint**, selecciona el repositorio y la rama `master`.
   Render leerá `render.yaml`.
3. Introduce `DATABASE_URL`: la cadena PostgreSQL de una base externa, por
   ejemplo Neon Free, con `sslmode=require`. Se aceptan los prefijos
   `postgresql://`, `postgres://` y `postgresql+psycopg://`.
   Introduce la contraseña solo en Render, nunca en GitHub ni en el chat.
4. Confirma que el servicio usa **Free** y despliega. Verifica que `/health`
   devuelve `status: ok` y que `/api/v1/products` responde correctamente.

`CORS_ORIGINS` autoriza `https://arielloza23.github.io` (sin `/tienda-web`).
Si cambia el dominio del frontend, actualiza esta variable como una lista JSON.
La URL definitiva de la API se obtiene en Render tras crear el servicio;
el frontend todavía necesita configurarse para usarla.

El despliegue crea el esquema, pero no copia los productos, usuarios ni pedidos
de la base local. La creación del primer administrador se hace con
`python -m app.create_admin` desde un entorno local conectado a la base remota.

No uses SQLite en Render Free: sus archivos locales se pierden al reiniciar.
La base PostgreSQL gratuita de Render vence a los 30 días; este Blueprint no
crea una base de datos de Render. El servidor Free se suspende tras 15 minutos
sin tráfico y la primera petición puede tardar alrededor de un minuto.

Referencias: [Render Free](https://render.com/docs/free),
[Blueprints](https://render.com/docs/blueprint-spec).

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

## Fotos de productos

Cada producto puede incluir hasta 12 fotos adicionales en `images`, con `url`
(HTTPS), `alt` y `color`. El color debe coincidir con una variante del producto.
La galería muestra únicamente las fotos del color seleccionado y mantiene
`image_url` como portada. Tras actualizar el código, ejecuta `alembic upgrade head`.

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
