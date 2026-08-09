# Backend Tesis Apnea

Backend con FastAPI para consumir el modelo PyTorch `modelo_resnet_apnea_central_0-7.pth`, procesar ventanas de senal fisiologica y guardar consultas/resultados en PostgreSQL/Supabase.

## Instalacion

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con los datos sensibles de tu proyecto: conexión a la base de datos, JWT y credenciales de acceso.

La conexión se configura con `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` y `DB_SSLMODE`; no se almacena una URL con credenciales en el repositorio. Las contraseñas pueden incluir caracteres especiales: el backend las codifica de forma segura al crear la conexión.

## Ejecutar

```powershell
uvicorn app.main:app --reload
```

Documentacion interactiva:

```text
http://127.0.0.1:8000/docs
```

## Autenticación JWT

Para obtener un token usa `POST /api/v1/auth/token` con JSON:

```json
{
  "username": "admin",
  "password": "admin"
}
```

Luego usa el header `Authorization: Bearer <token>` en los endpoints protegidos como `/api/v1/predict`.

## Entrada de prediccion

`POST /api/v1/predict`

Este endpoint ahora recibe archivos `multipart/form-data` con los formatos soportados: `.edf`, `.dat` y `.apn`.

Ejemplo con `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/predict" \
  -H "Authorization: Bearer <token>" \
  -F "archivo=@/ruta/a/registro.edf" \
  -F "usuario_id=1" \
  -F "paciente_id=paciente-001" \
  -F "metadata={\"fuente\": \"frontend\"}" \
  -F "normalize=true" \
  -F "guardar_resultado=true" \
  -F "guardar_historial=true"
```

La API lee el archivo, extrae las señales esperadas y ajusta la entrada a `3840 x 3`; si faltan muestras rellena con ceros, si sobran recorta, y si hay más/menos canales adapta a 3 canales.

## Base de datos en Supabase

Ejecuta el contenido de [db/schema.sql](db/schema.sql) en **Supabase > SQL Editor > New query**. Crea las tablas `usuarios`, `resultados` e `historial_consultas`, sus claves foráneas e índices. Puedes crear un usuario inicial con el `INSERT` comentado al final del archivo.

## Despliegue en Render

Crea un **Web Service** desde este repositorio y selecciona el entorno **Docker**; Render usará el `Dockerfile` incluido. Configura estas variables de entorno en el panel de Render (no subas un `.env` real):

```text
APP_ENV=production
MODEL_PATH=./modelo_resnet_apnea_central_0-7.pth
MODEL_THRESHOLD=0.5
DB_HOST=db.TU_PROJECT_REF.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=<clave de Supabase, marcada como Secret>
DB_SSLMODE=require
CORS_ORIGINS=https://tu-frontend.onrender.com
JWT_SECRET_KEY=<valor largo, aleatorio y marcado como Secret>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRES_MINUTES=60
AUTH_USERNAME=admin
AUTH_PASSWORD=<clave robusta, marcada como Secret>
```

Usa `/` como Health Check Path en Render. El modelo `.pth` forma parte de la imagen Docker; no lo elimines del repositorio.
