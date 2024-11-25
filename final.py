import requests
from requests_html import HTMLSession
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

def download_image(img_url):
    """Descargar imagen desde URL"""
    try:
        response = requests.get(img_url)
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
    """Raspar documento de Scribd"""
    base_url = f"https://www.scribd.com/document/{document_id}/{title}"

    try:
        # Usar requests-html para renderizar JavaScript
        session = HTMLSession()
        response = session.get(base_url)
        response.html.render(timeout=30)

        # Analizar contenido con BeautifulSoup
        soup = BeautifulSoup(response.html.html, 'html.parser')

        # Preparar directorios
        os.makedirs('images', exist_ok=True)

        # Extraer texto y preparar contenido
        text_content = ""
        images_list = []

        # Buscar elementos de texto
        text_elements = soup.find_all(['p', 'div'], class_=re.compile('text|content'))

        for element in text_elements:
            # Extraer texto
            element_text = element.get_text(strip=True)
            if element_text:
                text_content += element_text + '\n'

            # Extraer imágenes
            images = element.find_all('img')
            for img in images:
                img_url = img.get('src')
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
        description='Scrapeador y Generador de PDF de Scribd',
        epilog='Ejemplo: python script.py 123456/Título-del-Documento'
    )
    parser.add_argument('url', help='URL de Scribd en formato: document_id/title')

    args = parser.parse_args()

    # Separar document_id y title
    document_id, title = args.url.split('/')

    # Ejecutar scraping y generación de PDF
    scrape_scribd_document(document_id, title)

if __name__ == "__main__":
    main()
