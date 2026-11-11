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
