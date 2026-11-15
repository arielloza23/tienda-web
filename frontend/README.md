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
