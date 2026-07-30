# ver-videos-twitter

Web simple para ver videos e imágenes de tweets de X/Twitter sin necesidad de tener la app ni cuenta de Twitter. Pega la URL del tweet y reproduce el contenido directamente en el navegador.

## Estado

Fase 1 completada. Funcionalidad actual: backend con FastAPI que usa `yt-dlp` para extraer URLs de medios (video/imagen) desde una URL de tweet, frontend vanilla que muestra el resultado en un player HTML5.

## Stack

- **Backend**: FastAPI (ASGI) + `yt-dlp` para extracción de medios
- **Frontend**: HTML/CSS/JS vanilla, sin frameworks
- **Hosting**: [Vercel](https://vercel.com) (gratis, serverless, zero-config)

## Por qué este stack

- **FastAPI** sobre Flask: soporte ASGI nativo en Vercel, validación con Pydantic sin código extra
- **yt-dlp**: estándar de facto para extraer medios de Twitter/X, mantenida activamente, soporta la mayoría de formatos
- **Vercel**: tier gratis cubre uso personal sin gestión (100 GB bandwidth/mes, HTTPS automático, deploys desde Git)
- **HTML vanilla**: un solo archivo, sin build step, sin dependencias de npm

## Estructura

```
ver-videos-twitter/
├── app.py               # FastAPI (serves frontend + API) — Vercel auto-detecta
├── public/
│   └── index.html       # Frontend (HTML + CSS + JS inline)
├── requirements.txt     # yt-dlp, fastapi
├── vercel.json          # Config mínima de Vercel (memory)
├── .gitignore
├── README.md
└── agents.md            # Este archivo
```

### Por qué `app.py` en raíz (no `api/index.py`)

Vercel auto-detecta `app.py` como entrypoint ASGI (FastAPI). Todas las rutas van al mismo handler:
- `GET /` → sirve el HTML del frontend
- `POST /api/media` → extrae medios con yt-dlp

No necesita rewrites ni config extra. Más simple que `api/index.py` + rewrite.

## Cómo funciona

1. Usuario pega URL del tweet (formato: `https://x.com/<user>/status/<id>` o `https://twitter.com/...`)
2. Frontend hace `POST /api/media` con `{url: "..."}`
3. Backend llama a `yt-dlp` con `download=False` → extrae metadata + URLs directas
4. Backend filtra formatos: prefiere MP4 directo sobre HLS (m3u8) para mejor compatibilidad
5. Devuelve JSON con `{type, url, thumbnail}`
6. Frontend renderiza `<video>` o `<img>` con la URL

## API

### `GET /`
Sirve el frontend HTML (desde `public/index.html`).

### `POST /api/media`

**Request:**
```json
{"url": "https://x.com/usuario/status/1234567890"}
```

**Response (video):**
```json
{
  "media": [{
    "type": "video",
    "url": "https://video.twimg.com/...mp4",
    "thumbnail": "https://pbs.twimg.com/...jpg",
    "width": 1280,
    "height": 720,
    "title": "Tweet title",
    "duration": 15.5
  }],
  "tweet_url": "https://x.com/usuario/status/1234567890"
}
```

**Response (image):**
```json
{
  "media": [{
    "type": "image",
    "url": "https://pbs.twimg.com/media/...jpg",
    "thumbnail": "https://pbs.twimg.com/media/...jpg",
    "title": "Tweet title"
  }],
  "tweet_url": "https://x.com/usuario/status/1234567890"
}
```

**Errores:**
- `400`: URL inválida (no es formato de tweet)
- `404`: Tweet no encontrado / eliminado / privado
- `422`: Error de extracción (yt-dlp no pudo acceder)
- `500`: Error inesperado

## CORS

El backend acepta cualquier origen (`allow_origins=["*"]`) para que la web funcione sin restricciones. Si en el futuro se quiere restringir, cambiar a una lista de dominios específicos.

## Limitaciones conocidas

### Tweet no encontrado / privado
`yt-dlp` falla con un `ExtractorError` si el tweet no existe, es privado o la cuenta está suspendida. El backend captura esto y devuelve 500 con mensaje genérico.

### Videos muy antiguos con NSFW gating
Twitter puede requerir login para videos marcados como sensibles. En ese caso, `yt-dlp` devolverá error. Sin auth no hay workaround (es limitación de X).

### HLS vs MP4
Algunos videos de X solo están disponibles en formato HLS (m3u8). Estos funcionan en el navegador pero pueden tardar más en empezar a reproducir. El código prioriza MP4 si está disponible.

### Timeout de Vercel
Vercel Hobby tiene 10s de timeout en funciones. `yt-dlp` extrae info en <5s para tweets normales, pero tweets con muchos medios pueden tardar más. Si esto pasa, el usuario verá error 500.

## Deploy

Ver `README.md` para instrucciones paso a paso. Resumen:

1. Push a GitHub
2. Importar en Vercel
3. Vercel detecta FastAPI automáticamente y despliega
4. Cada push a `main` redespliega

## Desarrollo local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install uvicorn  # solo para local, Vercel no lo necesita
uvicorn app:app --reload
```

Abre `http://localhost:8000`. FastAPI sirve el frontend en `/` y la API en `/api/media`.

## Próximas mejoras (no implementadas)

- Caché de resultados (mismo tweet no se extrae 2 veces)
- Soporte para videos de otras plataformas (Instagram, TikTok, Reddit) — yt-dlp ya lo soporta, solo cambiar el extractor
- Historial de tweets vistos en localStorage
- Botón de descarga (es un paso más allá del MVP, no se pidió)

## Reglas de contribución

- **No añadir dependencias sin justificación** — la simplicidad es prioritaria
- **No añadir frameworks de frontend** — HTML vanilla cubre el caso
- **No añadir bases de datos** — el estado es efímero, no se necesita persistir
- **Preferir funciones stdlib** — sólo `yt-dlp` y `fastapi` como deps externas

## Seguridad

- **Validar URLs en backend**: regex básico para asegurar que es Twitter/X antes de pasar a `yt-dlp`
- **No loggear URLs completas**: los IDs de tweet no son sensibles pero mejor prevenir
- **CORS abierto**: aceptable para este caso (web pública sin auth), revisar si se restringe acceso más adelante
