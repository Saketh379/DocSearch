# backend/pdf_reader.py
import os
import fitz
import pdfplumber
from PIL import Image
from pathlib import Path

class PDF_Reader:

    def __init__(self, file_path):
        self.file_path = file_path    
        self.global_image_dir = "image_data"
        self.file_name = Path(file_path).name.split(".")[0]
    
    def extract_text(self):
        """
        Extract all text from the PDF.
        Returns a single string containing the text from all pages.
        """
        full_text = []

        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()     
                full_text.append(text or "")

        return "\n".join(full_text)

    def extract_images(self, output_dir=None):
        """
        Extract all images embedded in the PDF, saves every image to disk.
        Returns a list of file paths of extracted images.
        """
        output_dir = self.global_image_dir + f"/{output_dir if output_dir is not None else self.file_name}"
        os.makedirs(output_dir, exist_ok=True)

        image_paths = []

        doc = fitz.open(self.file_path)
        for page_index in range(len(doc)):
            page = doc[page_index]

            image_list = page.get_images(full=True)

            for img_index, img in enumerate(image_list):

                xref = img[0]                        # Image reference ID
                base_image = doc.extract_image(xref) # Extract actual image data
                image_bytes = base_image["image"]    # Raw image bytes
                image_ext = base_image["ext"]        # Image file extension

                image_filename = f"page{page_index+1}_img{img_index+1}.{image_ext}"
                image_filepath = os.path.join(output_dir, image_filename)

                with open(image_filepath, "wb") as f:
                    f.write(image_bytes)

                image_paths.append(image_filepath)

        return image_paths
