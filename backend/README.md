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


## Seguridad y reintentos de pedidos

- Define `APP_ENV=production` en producción. El arranque exige autenticación
  administrativa activa y una `SECRET_KEY` aleatoria de al menos 32 caracteres.
  El Blueprint local incluye este entorno; no se han aplicado cambios remotos.
  Desarrollo y pruebas pueden usar `development` y `test` respectivamente.
- El checkout público acepta `user_id` solo omitido o `null`: no permite atribuir
  pedidos a una cuenta a través del cuerpo de la solicitud.
- Máximo 50 líneas y 100 unidades por producto/variante, incluyendo líneas repetidas.
  El importe calculado no puede superar 2147483647 centavos.
- `POST /api/v1/orders` admite `Idempotency-Key` con formato UUID. Una clave y
  cuerpo idénticos (con espacios exteriores de contacto normalizados) devuelven
  el mismo pedido con 201. Reutilizarla con otro cuerpo devuelve 409. Sin cabecera
  se conserva la compatibilidad, sin protección frente a pedidos duplicados.
  Tratar la clave como dato confidencial y usar UUID aleatorios; no aparece en las
  respuestas. El cliente genera una nueva clave cuando cambia el pedido.

La revisión `20261115_order_idempotency` añade columnas opcionales y un índice
único, sin modificar pedidos existentes. Antes de usar el código contra una base
existente, respaldarla y aplicar `alembic upgrade head`. El downgrade conserva
los pedidos, pero elimina sus claves e historial de reintentos. La validación
local usa bases temporales; no aplicar migraciones sobre bases reales como prueba.


## Módulo de administración de productos

La interfaz está en `/#/admin` (en Pages, `/tienda-web/#/admin`). Permite iniciar
sesión con un administrador, crear productos activos o borradores, agregar sus
variantes, subir portada y hasta 12 fotos de galería, y ordenar las fotos.
El precio base y los ajustes se muestran en USD; la API recibe centavos enteros.
No incorpora stock ni crea cuentas administrativas desde el navegador.

- `GET /api/v1/products/admin`: listado privado con activos e inactivos.
- `POST /api/v1/products`: creación con sus atributos y variantes.
- `POST /api/v1/products/images`: carga multipart con campo `file`, requiere
  un administrador autenticado incluso si el bypass de desarrollo está activo.
- El identificador del producto y los SKU deben ser únicos; los conflictos
  devuelven 409. Los IDs y las posiciones de fotos son gestionados por el servidor.

Para crear el primer administrador, usa el comando existente desde `backend`,
con el entorno apuntando a la base correcta (no pegues contraseñas en comandos):

```powershell
..\.venv\Scripts\python.exe -m app.create_admin TU_CORREO "TU NOMBRE"
```

La contraseña se pide de forma interactiva. No hay una contraseña predeterminada.
El navegador mantiene el token solo en memoria; recargar requiere iniciar sesión.

### Fotos persistentes

Configura en el entorno del backend, mediante su gestor de secretos:

- `AWS_ENDPOINT_URL_S3`: endpoint HTTPS de la rama de Neon Object Storage.
- `AWS_REGION`: región del almacenamiento.
- `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`: credencial con permiso de escritura.
- `PRODUCT_IMAGES_BUCKET`: bucket con lectura pública y escritura autenticada.
- `PRODUCT_IMAGES_PUBLIC_URL`: URL HTTPS base pública del bucket, sin barra final.
  Puede ser un CDN. Se agrega a esa base la clave `products/<uuid>.webp`.

Las credenciales S3 se usan únicamente en el servidor. No guardar la conexión o
claves en el frontend, Git o la documentación. No se configura ACL por objeto;
configura el acceso público en el bucket. Ningún archivo depende del disco efímero
de Render. Sin configuración, la carga devuelve 503, sin simular un éxito.

Se aceptan JPEG, PNG, WebP y AVIF hasta 8 MiB y 20 megapíxeles. El servidor
comprueba el contenido, rechaza animaciones, orienta la foto, elimina metadatos
(incluido GPS), reduce a un máximo de 2400 píxeles por lado y convierte a WebP.
Las claves son nuevas por cada carga; las respuestas se pueden almacenar en caché.

Subir una foto y abandonar el formulario puede dejar un objeto sin producto.
No se borran automáticamente fotos: cualquier limpieza futura debe comprobar
referencias a portadas y galería antes de eliminar objetos.

Este cambio no requiere migraciones de tablas. Antes de publicarlo deben estar
configurados el bucket y la cuenta administradora. Las pruebas automatizadas usan
almacenamiento simulado y bases temporales, nunca las bases del usuario.
