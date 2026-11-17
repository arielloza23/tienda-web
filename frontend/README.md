# Frontend

## API y publicación

En desarrollo, `npm start` usa `/api/v1` a través de `proxy.conf.json`.
La compilación de producción usa `https://tienda-web-api.onrender.com/api/v1`,
configurado en `src/environments/environment.production.ts`.

Para GitHub Pages, el workflow `Publicar tienda en GitHub Pages` está disponible
en **Actions > Run workflow**. Primero hay que habilitar **Settings > Pages >
GitHub Actions** en el repositorio. El plan actual no admite Pages con este
repositorio privado; hacerlo público requiere autorización del propietario.
El workflow obtiene la ruta base de Pages y publica `dist/frontend/browser`.

La API en Render carga el producto inicial «Vestido body de encaje», color vino,
talla M, a $15 mediante la migración `20261111_vestido_body`. Las cuatro fotos
se publican desde `public/productos/vestido-body-de-encaje`.

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 22.2.5.

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4200/`. The application will automatically reload whenever you modify any of the source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Vitest](https://vitest.dev/) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.


## Validación de la tienda

- `npm run build`: compilación de producción.
- `npm test -- --watch=false`: pruebas Angular/Vitest del carrito y los reintentos.

El carrito guarda en `localStorage` únicamente IDs de producto/variante y
cantidades. Al cargar el catálogo vuelve a obtener precios y disponibilidad.
Nombre, teléfono, dirección y coordenadas se mantienen en memoria.
La clave del intento de checkout se conserva en memoria tras un error de red;
recargar la página reinicia ese intento. Ante una respuesta incierta, conviene
reintentar sin recargar ni cambiar los datos para recuperar el mismo pedido.


## Administración

Abre `http://localhost:4200/#/admin` para iniciar sesión y crear productos.
Las rutas usan hash para permitir recargar la administración en GitHub Pages.
La tienda conserva su catálogo y carrito en la ruta principal.

Los productos incluyen nombre, identificador, descripción, precio USD, estado,
portada, variantes (SKU, talla, color y ajuste de precio) y galería ordenada por
color. Las fotos se seleccionan desde el equipo y se envían al backend autenticado.
Consulta `backend/README.md` para configurar almacenamiento y crear el primer admin.

La verificación de navegador se puede repetir después de `npm run build`, desde
la raíz, con `..` ajustado a la ubicación de tu entorno Python:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe frontend/tests/admin_browser.py
```

La prueba usa Chrome instalado en Windows, los puertos 8123/8124, una base
SQLite en memoria y almacenamiento simulado. No llama a producción ni crea
productos reales. Comprueba login, carga de archivos, creación completa,
borradores, navegación de la tienda, disposición móvil y cierre de sesión.


Desde la lista del administrador, pulsa **Editar** para cargar un producto,
cambiar sus atributos y fotos y **Guardar cambios**. **Cancelar edición** vuelve
al formulario de creación sin modificar el producto. Si falla el guardado se
conservan los datos ingresados. Las variantes vinculadas a pedidos no pueden
quitarse y las imágenes existentes se conservan sin volver a subirlas.


## Compra invitada y opiniones

La compra no requiere iniciar sesión ni crear una cuenta. **Mi cuenta** permite
registrarse o entrar para calificar con 1 a 5 estrellas y comentar el producto
seleccionado. Cada cuenta tiene una opinión por producto, que puede actualizar.
Las reseñas son públicas y muestran el nombre visible elegido al registrarse.
El comentario es texto plano de hasta 2000 caracteres y puede dejarse vacío.

La sesión de cliente y la administrativa son independientes. El token solo vive
en memoria; al recargar se necesita entrar de nuevo. El carrito y los pedidos
no reciben tokens de autenticación. Las respuestas antiguas de reseñas se cancelan
al cambiar de producto para evitar mezclar opiniones.

Después de compilar, se puede comprobar el flujo con Chrome y datos temporales:

```powershell
.\.venv\Scripts\python.exe frontend/tests/customer_browser.py
```

La prueba realiza una compra invitada, registro, acceso, publicación y actualización
de una opinión, lectura pública, cambio de producto y vista móvil. Usa API local,
SQLite en memoria y respuestas simuladas para servicios externos; no toca producción.


## Carrusel de productos y galería

El carrusel principal muestra la portada de cada producto. Sus flechas, teclado y
el gesto horizontal navegan entre productos. Elegir talla o color no sustituye
la portada. Al pulsar la imagen se abre la galería con la portada y todas las
fotos adicionales de ese artículo; dentro del diálogo las flechas recorren fotos.

Tras compilar, la prueba aislada de Chrome se ejecuta desde la raíz con:

```powershell
.\.venv\Scripts\python.exe frontend/tests/showcase_browser.py
```

Usa un catálogo y respuestas simuladas; no accede a producción.


La guía **Así de sencillo** se muestra debajo del carrusel completo, con
los tres pasos de compra y el enlace **Cómo comprar** apuntando a ese bloque.
Las opiniones presentan estrellas vacías o rellenas; el selector conserva las
etiquetas accesibles y el manejo por teclado, sin números visibles en las estrellas.


**Ver opiniones** abre una ventana con el nombre y las reseñas del producto
seleccionado. Al cerrarla se desmonta el formulario; al abrir otro artículo se
consulta su propia lista y calificación. El acceso a la cuenta puede abrirse
sobre esa ventana para comentar sin perder el producto consultado.
La guía horizontal de compra está debajo del carrusel completo, con mayor ancho.


## Elegir talla y revisar el pedido

La selección muestra cada combinación real de talla y color del catálogo, sin
confundir opciones que comparten talla. El precio incluye el ajuste de la variante.
Al cambiar de producto o actualizar el catálogo se reinicia la selección.

La guía visual explica cómo tomar medidas de busto, cintura y cadera y presenta
las medidas publicadas para cada variante cuando existen. Los números son
contornos de la prenda en cm, no medidas corporales ni recomendaciones automáticas.
Sin medidas se muestra una indicación para consultarlas. No hay inventario: las
opciones del catálogo no equivalen a existencias confirmadas.

El pedido presenta talla, color, precio unitario e importe por línea. La miniatura
prioriza una foto del color elegido y recurre a la portada cuando no la hay.
El subtotal corresponde a las prendas; el envío se coordina por WhatsApp.

Después de compilar, verificar este recorrido con datos simulados desde la raíz:

```powershell
.\.venv\Scripts\python.exe frontend/tests/purchase_browser.py
```

La prueba comprueba variantes con la misma talla, ajustes de precio, dos líneas
independientes, fotos por color, cantidades, subtotal y anchuras de 320 y 390 px.
No crea pedidos ni accede a producción.


## Confirmación de precios y último comprobante

Cada línea de checkout envía `expected_unit_price_cents`. Si el precio vigente
cambió, la API devuelve 409 `detail.code=price_changed` sin registrar un pedido.
La tienda recarga el catálogo, conserva contacto y mapa, muestra los importes
anteriores y nuevos y exige otro clic en «Aceptar precios y confirmar».
No reenvía la compra automáticamente. La clave de idempotencia conserva los
reintentos del mismo cuerpo dentro de la sesión de la aplicación.

Después de recibir una confirmación, `sessionStorage` guarda durante 24 horas
el número, estado histórico, prendas e importes del último pedido de esa pestaña.
No guarda nombre, teléfono, dirección, coordenadas, token de acceso ni URL de
WhatsApp. «Último pedido» recupera el resumen y reconstruye un mensaje sin esos
datos; «Olvidar comprobante» lo borra. Volver al catálogo conserva este resumen.
Es un comprobante histórico, no un seguimiento actualizado. Cerrar la pestaña
elimina su almacenamiento de sesión; no se recupera una respuesta que nunca
llegó al navegador.

## Medidas y atención de pedidos

El administrador permite cargar `bust_cm`, `waist_cm`, `hip_cm` por variante:
valores opcionales mayores que 0 y hasta 300, con un decimal. Son contornos de
la prenda. No se precargan datos inventados. La sección «Pedidos» reutiliza
la API administrativa para consultar datos y cambiar estados permitidos.
La cancelación necesita confirmación; el pago se verifica fuera de la tienda.

## Recuperación de contraseña

En Mi cuenta, «Olvidé mi contraseña» solicita un enlace por correo. La ruta
`/#/reset-password?token=...` retira el token de la URL al abrirse y permite elegir
una contraseña nueva. El enlace vence, se consume una sola vez y el cambio
invalida sesiones anteriores. No se guarda el token en almacenamiento web.

SMTP queda pendiente de configuración privada del backend; ver `backend/README.md`.
Sin configuración la interfaz informa que el servicio no está disponible.
No se envían correos reales durante las pruebas.

Para comprobar los recorridos completos, desde la raíz, después de compilar:

```powershell
.\.venv\Scripts\python.exe frontend/tests/customer_browser.py
.\.venv\Scripts\python.exe frontend/tests/admin_browser.py
.\.venv\Scripts\python.exe frontend/tests/recovery_browser.py
```

Ejecutarlos uno por vez porque comparten puertos de pruebas. Usan SQLite en
memoria, imágenes y correo simulados. No leen ni modifican bases del usuario
ni servicios de producción.
