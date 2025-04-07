import requests
from bs4 import BeautifulSoup
import argparse
import os
import re
import base64
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import time
import random

# Configurar headers para simular un navegador real
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'
]

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }

def download_image(img_url):
    """Descargar imagen desde URL"""
    try:
        response = requests.get(img_url, headers=get_headers())
        if response.status_code == 200:
            # Guardar imagen
            filename = os.path.basename(img_url)
            filepath = os.path.join('images', filename)
            os.makedirs('images', exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(response.content)
            return filepath
    except Exception as e:
        print(f"Error descargando imagen {img_url}: {e}")
    return None

def extract_table_of_contents(text):
    """Extraer tabla de contenidos"""
    toc_pattern = r'(\d+(?:\.\d+)?)\s*([^\n]+)'
    matches = re.findall(toc_pattern, text)
    return [(section, title.strip()) for section, title in matches]

def scrape_scribd_document(document_id, title):
    """Raspar documento de Scribd sin usar Chromium"""
    base_url = f"https://www.scribd.com/document/{document_id}/{title}"
    print(f"Iniciando scraping de {base_url}")
    
    try:
        # Realizar múltiples intentos para obtener el contenido
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                print(f"Intento {attempt+1} de {max_attempts}")
                # Obtener la página con requests
                response = requests.get(base_url, headers=get_headers(), timeout=30)
                response.raise_for_status()  # Verificar si hay errores HTTP
                
                # Analizar con BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Verificar si tenemos contenido significativo
                if len(soup.text) < 500 and attempt < max_attempts - 1:
                    print("Contenido insuficiente, reintentando...")
                    time.sleep(2)  # Esperar antes de reintentar
                    continue
                
                break  # Si llegamos aquí, tenemos contenido
            except requests.RequestException as e:
                print(f"Error en la solicitud: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)  # Esperar antes de reintentar
                else:
                    raise
        
        # Preparar directorios
        os.makedirs('images', exist_ok=True)

        # Extraer texto y preparar contenido
        text_content = ""
        images_list = []

        # Buscar elementos de texto - intentar diferentes selectores que podrían contener el contenido
        text_elements = []
        text_elements.extend(soup.find_all(['p', 'div'], class_=re.compile('text|content')))
        text_elements.extend(soup.find_all(['p', 'div'], id=re.compile('text|content')))
        text_elements.extend(soup.select('.document-content .page'))
        
        # Si no encontramos nada específico, intentar con todos los párrafos
        if not text_elements:
            text_elements = soup.find_all('p')

        for element in text_elements:
            # Extraer texto
            element_text = element.get_text(strip=True)
            if element_text:
                # Agregar salto de línea después de URLs
                element_text = re.sub(r'(https?://\S+)', r'\1\n', element_text)
                text_content += element_text + '\n'

            # Extraer imágenes
            images = element.find_all('img')
            for img in images:
                img_url = img.get('src') or img.get('data-src')
                if img_url and img_url.startswith(('http', 'https')):
                    downloaded_img = download_image(img_url)
                    if downloaded_img:
                        images_list.append(downloaded_img)

        # Generar nombre de archivo
        sanitized_title = re.sub(r'[^\w\-_\. ]', '_', title)
        txt_output = f"{sanitized_title}_sinfotos.txt"

        # Guardar contenido de texto
        with open(txt_output, 'w', encoding='utf-8') as f:
            f.write(text_content)

        # Convertir a PDF
        pdf_output = f"{sanitized_title}.pdf"
        create_pdf_with_toc_and_images(txt_output, pdf_output, images_list)

        print(f"Documento extraído, guardado como {txt_output} y {pdf_output}")
        return txt_output, pdf_output

    except Exception as e:
        print(f"Error de raspado: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def create_pdf_with_toc_and_images(input_file, output_file, images_list=None):
    """Crear PDF con tabla de contenidos e imágenes"""
    # Leer contenido del archivo
    with open(input_file, 'r', encoding='utf-8') as f:
        text_content = f.read()

    # Configurar documento PDF
    doc = SimpleDocTemplate(output_file, pagesize=letter,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)

    styles = getSampleStyleSheet()

    # Estilos personalizados
    toc_header_style = ParagraphStyle(
        'TOCHeader',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.darkblue
    )

    # Preparar historia del documento
    story = []

    # Tabla de contenidos
    toc_entries = extract_table_of_contents(text_content)
    if toc_entries:
        story.append(Paragraph("Tabla de Contenidos", toc_header_style))
        story.append(Spacer(1, 12))

        toc_data = [[entry[0], entry[1]] for entry in toc_entries]
        toc_table = Table(toc_data, colWidths=[1*inch, 5*inch])
        toc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        story.append(toc_table)
        story.append(Spacer(1, 20))

    # Procesar contenido
    paragraphs = text_content.split('\n')
    for para in paragraphs:
        if para.strip():
            # Asegurar que las URLs tengan saltos de línea en el PDF
            para = re.sub(r'(https?://\S+)', r'\1<br/>', para)
            story.append(Paragraph(para, styles['Normal']))
            story.append(Spacer(1, 6))  # Espaciado entre párrafos

    # Agregar imágenes
    if images_list:
        for img_path in images_list:
            try:
                # Ajustar tamaño de imagen
                img = Image(img_path, width=4*inch, height=None)
                story.append(img)
                story.append(Spacer(1, 12))
            except Exception as e:
                print(f"Error al agregar imagen {img_path}: {e}")

    # Construir PDF
    doc.build(story)
    print(f"PDF creado exitosamente: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description='Scrapeador y Generador de PDF de Scribd (Sin Chromium)',
        epilog='Ejemplo: python final2.py 123456/Título-del-Documento'
    )
    parser.add_argument('url', help='URL de Scribd en formato: document_id/title')

    args = parser.parse_args()

    # Separar document_id y title
    document_id, title = args.url.split('/')

    # Ejecutar scraping y generación de PDF
    scrape_scribd_document(document_id, title)

if __name__ == "__main__":
    main()