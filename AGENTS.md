# Agentes para programar la tienda

## Proyecto

- Frontend Angular y TypeScript en `frontend/`. Consulta `frontend/package.json`.
- Backend FastAPI, SQLAlchemy y Alembic en `backend/`. Consulta `backend/README.md` y `backend/requirements.txt`.
- Conserva la arquitectura existente y los cambios locales del usuario. Comunica avances y resultados en espanol.

## Coordinacion

Para tareas complejas con partes independientes, delega en los agentes de `.codex/agents/`:

- `tienda_arquitecto`: analiza la estructura, define contratos y prepara planes de cambios entre capas.
- `tienda_frontend`: interfaz, componentes, estilos, servicios y experiencia movil.
- `tienda_backend`: API, reglas de negocio, autenticacion, modelos y migraciones.
- `tienda_revisor`: revision de errores, seguridad y validacion, sin editar codigo.

El agente principal coordina e integra los resultados. Para tareas pequenas, trabaja directamente.
Para cambios que afecten varias capas o el esquema de datos, pide primero un plan a `tienda_arquitecto`; usa ese plan para repartir la implementacion y revisar el resultado.
Asigna archivos distintos a cada agente que edite. Acuerda primero los contratos entre frontend y backend.
Espera los resultados antes de integrar. Ejecuta la revision final despues de terminar los cambios.
Los agentes heredan el modelo de la sesion salvo configuracion explicita del usuario.

## Validacion

- Frontend: desde `frontend`, ejecuta `npm run build` cuando cambies codigo.
- Backend: desde `backend`, ejecuta `..\.venv\Scripts\python.exe -m pytest -q` o las pruebas pertinentes al cambio.
- Los cambios de esquema requieren migraciones Alembic y validacion con bases temporales.
- Informa que comprobaste y que quedo sin verificar. Una compilacion no prueba el funcionamiento en navegador.

## Datos y alcance

- No publiques credenciales ni contenido de `.env`.
- Usa datos temporales para pruebas; conserva bases `.db` e imagenes del usuario.
- Esta configuracion no autoriza por si misma despliegues, publicaciones ni cambios en servicios externos.

## Uso

Ejemplo de arquitectura: "Usa tienda_arquitecto para analizar esta funcionalidad y preparar el plan antes de programarla."

Ejemplo: "Usa los agentes de la tienda para mejorar el carrito: frontend para la interfaz, backend si requiere cambios de API y revisor al terminar."

Tras agregar estos archivos, inicia una nueva sesion de Codex en esta carpeta para que descubra la configuracion.
