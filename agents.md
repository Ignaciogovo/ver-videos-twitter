# AGENTS.md

## Contexto del proyecto
Web simple para ver videos, imágenes y contenido completo de tweets de X/Twitter sin necesidad de tener la app ni cuenta de Twitter. El usuario pega la URL del tweet y la web muestra el texto completo, autor, fecha, stats (likes, retweets, replies, views) y reproduce el contenido multimedia directamente en el navegador, con opción de descarga.

**Stack:**
- **Backend**: FastAPI (ASGI) + `yt-dlp` para extracción de medios y metadata
- **Frontend**: HTML/CSS/JS vanilla, sin frameworks, sin build step
- **Hosting**: Vercel (serverless, zero-config, auto-detecta `app.py`)

**Convenciones:**
- No añadir dependencias sin justificación — la simplicidad es prioritaria
- No añadir frameworks de frontend — HTML vanilla cubre el caso
- No añadir bases de datos — el estado es efímero
- Preferir funciones stdlib — sólo `yt-dlp` y `fastapi` como deps externas
- Validar URLs en backend antes de pasar a `yt-dlp`
- CORS abierto (web pública sin auth)

**Estructura:**
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

---

## 1. Flujo de Trabajo por Fases

### Estructura de Ramas
- `master` → producción estable
- `develop` → integración de fases completadas
- `feature/fase-X-descripcion` → desarrollo de cada fase

### Proceso por Fase
1. Crear rama `feature/fase-X-descripcion` desde `develop`
2. Dividir fase en **todos** específicos (el usuario los define)
3. Trabajar cada todo con autonomía
4. Al completar un todo → preguntar antes de continuar
5. Al completar la fase → esperar validación explícita del usuario
6. Validación completada → merge a `develop`

### Regla de Oro
**Ninguna fase está completa hasta que el usuario lo confirme explícitamente.**
Sin validación del usuario = sin merge, sin avanzar.

---

## 2. Autonomía y Comunicación

### Dentro de un Todo
- **Autonomía total** para implementar
- Tomar decisiones técnicas (estructura, librerías, patrones)
- Hacer commits intermedios si necesario

### Entre Todos o Fases
- **OBLIGATORIO preguntar** antes de:
  - Pasar al siguiente todo
  - Iniciar nueva fase
  - Cambiar arquitectura o diseño
  - Modificar archivos críticos sin contexto

### Planes Detallados
- **Siempre mostrar plan detallado antes de ejecutar**
- Incluir: qué se va a hacer, por qué, archivos afectados
- Esperar confirmación antes de proceder

---

## 3. Reglas de seguridad
- Nunca hardcodear secretos, tokens o credenciales en el código.
- Nunca hacer commit de archivos `.env`.
- Antes de instalar una dependencia nueva, verificar que sea necesaria y de fuente confiable.
- No ejecutar `git push --force` sobre ramas compartidas (`master`/`develop`) sin confirmación explícita.

## 4. Uso de herramientas
- Usar **codebase-memory-mcp** para preguntas estructurales (dónde se llama X, impacto de cambiar Y)
  en vez de grep/leer archivo por archivo cuando el proyecto ya esté indexado.
- **Ponytail** está activo en modo `full` por defecto: prioriza soluciones simples,
  evita añadir dependencias o abstracciones no solicitadas.

## 5. Flujo de trabajo (commits)
- Commits pequeños y descriptivos, alineados a un todo.
- Antes de cerrar un todo o fase, correr los tests si existen.