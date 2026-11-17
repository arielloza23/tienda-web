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


### Editar productos existentes

`PUT /api/v1/products/{product_id}` requiere un administrador autenticado y devuelve
el producto actualizado. Envía los atributos del formulario completos, incluyendo
`variants` e `images`; ambas listas son obligatorias y `[]` significa vaciarlas.
Las variantes existentes deben incluir su `id`; las nuevas lo omiten. Se conservan
los IDs y los importes y etiquetas históricos de los pedidos.

Una variante vinculada a pedidos no se puede quitar: la API devuelve 409 sin
aplicar ningún cambio. Los conflictos de identificador o SKU también devuelven
409. No se intercambian SKU entre variantes en una misma petición; primero guarda
un SKU libre. Quitar fotos del producto no borra los archivos del almacenamiento.
No requiere migraciones. Las ediciones simultáneas conservan el último guardado.


## Clientes y opiniones de productos

El checkout sigue siendo público: `POST /api/v1/orders` acepta pedidos sin token
ni cuenta, conserva la clave de reintento y no atribuye el pedido a un usuario.
Iniciar sesión es necesario únicamente para publicar o actualizar opiniones.
El registro (`POST /users`), acceso (`POST /auth/login`) y perfil (`GET /auth/me`)
se reutilizan. El registro siempre crea clientes; no concede permisos de admin.

- `GET /api/v1/products/{id}/reviews?limit=10&offset=0`: lectura pública de un
  producto activo, devuelve `items`, `total`, `average_rating`, `limit`, `offset`.
  El límite máximo es 50; la media contempla todas las calificaciones y es `null`
  si todavía no hay votos.
- `GET /api/v1/products/{id}/reviews/me`: opinión propia o `null`, con Bearer.
- `PUT /api/v1/products/{id}/reviews/me`: crea o actualiza la opinión propia,
  con `{ "rating": 5, "comment": "Comentario" }` y Bearer de usuario activo.
  La calificación es un entero estricto de 1 a 5 y el comentario es opcional,
  texto plano de hasta 2000 caracteres. No se exige compra previa.

Una restricción única garantiza una opinión por cliente y producto; actualizarla
no añade un segundo voto. El autor procede de la sesión y no del cuerpo recibido.
La lectura pública solo muestra el nombre visible, estrellas, comentario y fechas;
no publica correos ni identificadores de usuario. Los borradores no admiten
reseñas públicas ni nuevas opiniones. Las cuentas inactivas no pueden publicar.

La migración `20261115_product_reviews` agrega `product_reviews` y sus restricciones,
sin modificar pedidos o productos existentes. Se valida en bases temporales.
Antes de publicar hay que respaldar la base y ejecutar `alembic upgrade head`.
Un downgrade de esta revisión elimina las reseñas; no se usa sobre datos reales
como mecanismo de prueba. Moderación y verificación de correo no están incluidas.


## Confirmación de precios, medidas y recuperación de acceso

`POST /orders` admite `expected_unit_price_cents` opcional por línea (entero estricto
entre 0 y 2147483647). El servidor sigue calculando el importe. Si difiere, devuelve
409 con `detail.code = "price_changed"`, `message`, `items` (producto, variante,
precio esperado y actual) y `subtotal_cents` actual, sin crear ningún pedido.
El cliente debe mostrar el cambio y pedir otra confirmación. Los reintentos con una
clave ya registrada devuelven el pedido original antes de consultar precios.
Las solicitudes antiguas sin precio esperado conservan su hash de idempotencia.
En PostgreSQL, creación y edición bloquean el mismo producto hasta terminar para
que una edición concurrente no cambie el importe durante la confirmación.

Cada variante admite `bust_cm`, `waist_cm` y `hip_cm`, números opcionales mayores
que cero y hasta 300, con un decimal como máximo. Son **contornos de la prenda**
en centímetros, no medidas corporales ni una tabla inventada por talla. No se
rellenan automáticamente datos existentes. Enviar `null` elimina una medida.

- `POST /auth/forgot-password`, `{ "email": "cliente@example.com" }`: 202 con
  mensaje genérico para cuentas existentes, inactivas o desconocidas. Sin SMTP
  configurado devuelve 503 para todos; no afirma haber enviado un correo.
- `POST /auth/reset-password`, `{ "token": "...", "password": "..." }`: cambia
  la contraseña (8 a 128 caracteres), devuelve 200 con `message`; un enlace
  inexistente, usado o vencido devuelve 400 con un mensaje genérico.

Configura `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USER`, `SMTP_PASSWORD`
(secreto) y `SMTP_STARTTLS=true` para el puerto 587. Con `SMTP_STARTTLS=false`
solo se permite SMTP sobre TLS en el puerto 465. Se verifica el certificado TLS.
`PASSWORD_RESET_URL` debe ser la URL fija de tu frontend terminada en
`/#/reset-password`, sin parámetros: el backend agrega el token al fragmento.
Se permite HTTP únicamente para localhost. Estas variables se preparan en
`.env.example`; las pruebas simulan el transporte y no envían correo real.
El envío se ejecuta después de responder 202, sin compartir la sesión de base de
datos ni exponer por latencia SMTP si existe el correo. Es una tarea en memoria:
un reinicio puede interrumpirla; el cliente puede solicitar otro enlace.
Si el proveedor falla, se conserva la respuesta genérica y el log no expone
correos, tokens ni URLs; se puede volver a solicitar después de un minuto.

Los enlaces duran 30 minutos, son de un solo uso y se almacena únicamente su
SHA-256. Una nueva solicitud revoca los enlaces anteriores. El cambio invalida
las sesiones JWT previas de esa cuenta. Hay un intervalo mínimo de 60 segundos
por cuenta y un límite básico de diez solicitudes por hora y dirección de red,
sin revelar la existencia de la cuenta. El límite por dirección está en memoria
por proceso: una instalación con varios procesos debe añadir un límite común
en el proxy o proveedor. No hay envío ni configuración automática del proveedor.

La migración `20261116_checkout_recovery` conserva productos, pedidos y usuarios,
añade columnas opcionales, una versión de sesión y la tabla de enlaces de
recuperación. Upgrade/downgrade/reupgrade se valida solo en bases temporales.
El downgrade descarta las medidas y los enlaces de recuperación: no se usa
sobre una base real como prueba.

Las transiciones administrativas de pedidos se guardan con comparación del estado
previo: si otro administrador lo cambió simultáneamente, se rechaza el segundo
cambio y se solicita actualizar la bandeja. No sobrescribe una cancelación o envío.
