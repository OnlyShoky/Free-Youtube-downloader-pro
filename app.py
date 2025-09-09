from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import yt_dlp
import os
import threading
from pathlib import Path
import json
from datetime import datetime
import logging
import platform

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

class YouTubeDownloader:
    def __init__(self):
        self.downloads_folder = "downloads"
        self.crear_carpeta_descargas()
    
    def crear_carpeta_descargas(self):
        """Crea la carpeta de descargas si no existe"""
        Path(self.downloads_folder).mkdir(exist_ok=True)
    
    def obtener_ruta_cookies_automatica(self):
        """Intenta detectar automáticamente la ruta de cookies del navegador"""
        sistema = platform.system()
        
        # Rutas comunes para Chrome en diferentes sistemas
        if sistema == "Windows":
            rutas_posibles = [
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data"),
                os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data"),
                os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles"),
            ]
        elif sistema == "Darwin":  # macOS
            rutas_posibles = [
                os.path.expanduser("~/Library/Application Support/Google/Chrome"),
                os.path.expanduser("~/Library/Application Support/Microsoft Edge"),
                os.path.expanduser("~/Library/Application Support/Firefox/Profiles"),
            ]
        else:  # Linux
            rutas_posibles = [
                os.path.expanduser("~/.config/google-chrome"),
                os.path.expanduser("~/.config/microsoft-edge"),
                os.path.expanduser("~/.mozilla/firefox"),
            ]
        
        # Verificar qué rutas existen
        for ruta in rutas_posibles:
            if os.path.exists(ruta):
                return ruta
        
        return None
    
    def obtener_info_video(self, url, navegador=None):
        """Obtiene información del video"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        # Agregar cookies si se especifica un navegador
        if navegador and navegador != 'ninguno':
            ydl_opts['cookiesfrombrowser'] = (navegador,)
        else:
            # Intentar automáticamente si no se especifica navegador
            try:
                ydl_opts['cookiesfrombrowser'] = ('chrome',)
            except:
                # Si falla, continuar sin cookies
                pass
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Obtener formatos disponibles
                formatos = []
                for fmt in info.get('formats', []):
                    if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':  # Video con audio
                        if fmt.get('height') and fmt.get('ext') in ['mp4', 'webm']:
                            formatos.append({
                                'calidad': f"{fmt['height']}p",
                                'resolucion': fmt['height'],
                                'formato': fmt.get('ext', 'mp4'),
                                'id': fmt['format_id']
                            })
                
                # Eliminar duplicados y ordenar
                formatos_unicos = {}
                for fmt in formatos:
                    if fmt['calidad'] not in formatos_unicos:
                        formatos_unicos[fmt['calidad']] = fmt
                
                formatos_ordenados = sorted(
                    formatos_unicos.values(), 
                    key=lambda x: int(x['resolucion']), 
                    reverse=True
                )
                
                return {
                    'titulo': info.get('title', 'Sin título'),
                    'duracion': info.get('duration', 0),
                    'autor': info.get('uploader', 'Desconocido'),
                    'thumbnail': info.get('thumbnail', ''),
                    'vistas': info.get('view_count', 0),
                    'formatos_video': formatos_ordenados,
                    'formato_audio': {
                        'calidad': '192kbps',
                        'formato': 'mp3',
                        'id': 'bestaudio/best'
                    },
                    'success': True
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo info: {e}")
            # Intentar sin cookies si falla con cookies
            if 'cookies' in str(e).lower():
                try:
                    return self.obtener_info_video_sin_cookies(url)
                except Exception as e2:
                    return {'success': False, 'error': f"{e2} (también sin cookies)"}
            return {'success': False, 'error': str(e)}
    
    def obtener_info_video_sin_cookies(self, url):
        """Intenta obtener información sin usar cookies"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'titulo': info.get('title', 'Sin título'),
                    'duracion': info.get('duration', 0),
                    'autor': info.get('uploader', 'Desconocido'),
                    'thumbnail': info.get('thumbnail', ''),
                    'vistas': info.get('view_count', 0),
                    'success': True,
                    'advertencia': 'Información obtenida sin cookies, algunas descargas pueden fallar'
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def descargar_video(self, url, formato, calidad, id_formato, navegador=None):
        """Descarga el video o audio"""
        try:
            nombre_archivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            ydl_opts = {
                'outtmpl': os.path.join(self.downloads_folder, f'{nombre_archivo}.%(ext)s'),
                'quiet': False,
            }
            
            # Configurar formato
            if formato == 'mp3':
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            else:
                ydl_opts['format'] = id_formato
                ydl_opts['merge_output_format'] = 'mp4'
            
            # Agregar cookies si se especifica
            if navegador and navegador != 'ninguno':
                ydl_opts['cookiesfrombrowser'] = (navegador,)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                nombre_final = ydl.prepare_filename(info)
                
                # Ajustar extensión para audio
                if formato == 'mp3':
                    nombre_final = nombre_final.rsplit('.', 1)[0] + '.mp3'
                
                return {
                    'success': True,
                    'archivo': os.path.basename(nombre_final),
                    'titulo': info.get('title', 'descarga')
                }
                
        except Exception as e:
            logger.error(f"Error en descarga: {e}")
            # Intentar sin cookies si falla
            if 'cookies' in str(e).lower():
                try:
                    return self.descargar_video(url, formato, calidad, id_formato, 'ninguno')
                except Exception as e2:
                    return {'success': False, 'error': f"{e2} (también sin cookies)"}
            return {'success': False, 'error': str(e)}

# Instancia global del downloader
downloader = YouTubeDownloader()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/navegadores', methods=['GET'])
def obtener_navegadores():
    """Devuelve la lista de navegadores disponibles"""
    navegadores = [
        {'id': 'chrome', 'nombre': 'Google Chrome', 'default': True},
        {'id': 'firefox', 'nombre': 'Mozilla Firefox'},
        {'id': 'edge', 'nombre': 'Microsoft Edge'},
        {'id': 'brave', 'nombre': 'Brave Browser'},
        {'id': 'opera', 'nombre': 'Opera'},
        {'id': 'ninguno', 'nombre': 'Sin cookies (modo básico)'}
    ]
    
    # Detectar sistema operativo
    sistema = platform.system()
    return jsonify({
        'navegadores': navegadores,
        'sistema': sistema,
        'ruta_auto': downloader.obtener_ruta_cookies_automatica()
    })

@app.route('/api/info', methods=['POST'])
def obtener_info():
    data = request.json
    url = data.get('url')
    navegador = data.get('navegador', 'chrome')
    
    if not url:
        return jsonify({'success': False, 'error': 'URL no proporcionada'})
    
    info = downloader.obtener_info_video(url, navegador)
    return jsonify(info)

@app.route('/api/download', methods=['POST'])
def descargar():
    data = request.json
    url = data.get('url')
    formato = data.get('formato')
    calidad = data.get('calidad')
    id_formato = data.get('id_formato')
    navegador = data.get('navegador', 'chrome')
    
    if not all([url, formato]):
        return jsonify({'success': False, 'error': 'Parámetros incompletos'})
    
    resultado = downloader.descargar_video(url, formato, calidad, id_formato, navegador)
    
    if resultado['success']:
        return jsonify(resultado)
    else:
        return jsonify(resultado)

@app.route('/api/download-file/<filename>')
def descargar_archivo(filename):
    try:
        ruta_archivo = os.path.join(downloader.downloads_folder, filename)
        if os.path.exists(ruta_archivo):
            return send_file(ruta_archivo, as_attachment=True)
        else:
            return jsonify({'success': False, 'error': 'Archivo no encontrado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cleanup', methods=['POST'])
def cleanup():
    """Limpiar archivos descargados"""
    try:
        for archivo in os.listdir(downloader.downloads_folder):
            ruta_archivo = os.path.join(downloader.downloads_folder, archivo)
            try:
                os.remove(ruta_archivo)
            except:
                pass
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)