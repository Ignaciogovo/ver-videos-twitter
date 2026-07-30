# Ver tweets de X/Twitter

Web para ver tweets de X/Twitter sin necesidad de iniciar sesión.

## Por qué existe esto

Últimamente X limita mucho la visualización de tweets para usuarios sin cuenta: corta el texto, bloquea fotos/videos y exige login. Me pasan tweets por chat y no puedo verlos bien, así que construí esta herramienta.

## Qué hace

- Pega una URL de tweet y ves el **texto completo**, el **autor**, **fecha** y **stats** (likes, retweets, etc.)
- Reproduce **videos** e **imágenes** directamente, sin app de X
- Botón de **descarga** para guardar el contenido
- Sin login, sin cuentas, sin cookies

## Stack

- **Backend**: FastAPI + yt-dlp
- **Frontend**: HTML/CSS/JS vanilla
- **Hosting**: Vercel

## Desarrollo local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install uvicorn
uvicorn app:app --reload
```

Abre http://localhost:8000

## Deploy en Vercel

1. Push a GitHub
2. Importar repo en [vercel.com/new](https://vercel.com/new)
3. Vercel detecta FastAPI automáticamente
4. Cada push a `main` redespliega

## Limitaciones

- Tweets NSFW, privados o borrados: no se pueden extraer sin autenticación
- Algunos videos vienen en HLS (m3u8): se reproducen pero no se descargan
- Timeout de Vercel: tweets con muchos medios pueden tardar más de 10s