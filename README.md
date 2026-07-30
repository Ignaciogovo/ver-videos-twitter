# Ver videos de X/Twitter

Web simple para ver videos e imágenes de tweets de X/Twitter sin app ni cuenta. Solo pegas la URL del tweet y ves el contenido.

## Demo

[URL tras deploy en Vercel]

## Stack

- **Backend**: FastAPI + yt-dlp (extracción de medios)
- **Frontend**: HTML/CSS/JS vanilla
- **Hosting**: [Vercel](https://vercel.com) (gratis)

## Deploy en Vercel

1. Sube el código a un repositorio en GitHub
2. Ve a [vercel.com/new](https://vercel.com/new), importa el repo
3. Vercel detecta FastAPI automáticamente y despliega
4. Cada push a `main` redespliega automáticamente

## Desarrollo local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install uvicorn
uvicorn app:app --reload
```

Abre http://localhost:8000 en el navegador.
