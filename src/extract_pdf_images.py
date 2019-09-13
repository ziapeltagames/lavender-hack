# -*- coding: utf-8 -*-
"""
Simple script to extract images from a pdf.

Created on Tue Sep 10 21:07:50 2019

@author: phill
"""

from __future__ import print_function
"""
The MIT License (MIT)
Copyright (c) 2018 Louis Abraham <louis.abraham@yahoo.fr>
Copyright ©2016 Ronan Paixão
Copyright (c) 2018 Gerald Storer
\x1B[34m\033[F\033[F
Extract the images from a pdf
\x1B[0m\x1B[36m\033[F\033[F
Supports most formats, but has some bugs (even pdfimages has).
For example, with encoding /CCITTFaxDecode, the image is sometimes flipped.
If you have a bug, see
https://stackoverflow.com/questions/2693820/extract-images-from-pdf-without-resampling-in-python
for other solutions or drop me an email with your pdf file attached
\x1B[0m\x1B[35m\033[F\033[F
TODO:
    - add support for range queries
\x1B[0m\033[1m\033[F\033[F
Links:
    PDF format: http://www.adobe.com/content/dam/Adobe/en/devnet/acrobat/pdfs/pdf_reference_1-7.pdf
    CCITT Group 4: https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-T.6-198811-I!!PDF-E&type=items
    Extract images from pdf: http://stackoverflow.com/questions/2693820/extract-images-from-pdf-without-resampling-in-python
    Extract images coded with CCITTFaxDecode in .net: http://stackoverflow.com/questions/2641770/extracting-image-from-pdf-with-ccittfaxdecode-filter
    TIFF format and tags: http://www.awaresystems.be/imaging/tiff/faq.html
    /Index support: https://github.com/ronanpaixao/PyPDFTK/blob/master/pdf_images.py
Usage:
    PDF_extract_images file.pdf page1 page2 page3 …
\033[0m\033[F\033[F
"""

# https://stackoverflow.com/questions/2693820/extract-images-from-pdf-without-resampling-in-python

import PyPDF2

from PIL import Image, ImageOps

import sys
import struct
from os import path
import warnings
import io
from collections import namedtuple
warnings.filterwarnings("ignore")

img_modes = {'/DeviceRGB': 'RGB', '/DefaultRGB': 'RGB',
             '/DeviceCMYK': 'CMYK', '/DefaultCMYK': 'CMYK',
             '/DeviceGray': 'L', '/DefaultGray': 'L',
             '/Indexed': 'P', '/CalRGB': 'RGB'}

PdfImage = namedtuple('PdfImage', ['data', 'format','image_name'])

def tiff_header_for_CCITT(width, height, img_size, CCITT_group=4):
    # http://www.fileformat.info/format/tiff/corion.htm
    fields = 8
    tiff_header_struct = '<' + '2s' + 'H' + 'L' + 'H' + 'HHLL' * fields + 'L'
    return struct.pack(tiff_header_struct,
                       b'II',  # Byte order indication: Little indian
                       42,  # Version number (always 42)
                       8,  # Offset to first IFD
                       fields,  # Number of tags in IFD
                       256, 4, 1, width,  # ImageWidth, LONG, 1, width
                       257, 4, 1, height,  # ImageLength, LONG, 1, lenght
                       258, 3, 1, 1,  # BitsPerSample, SHORT, 1, 1
                       259, 3, 1, CCITT_group,  # Compression, SHORT, 1, 4 = CCITT Group 4 fax encoding
                       262, 3, 1, 0,  # Threshholding, SHORT, 1, 0 = WhiteIsZero
                       # StripOffsets, LONG, 1, len of header
                       273, 4, 1, struct.calcsize(tiff_header_struct),
                       278, 4, 1, height,  # RowsPerStrip, LONG, 1, length
                       279, 4, 1, img_size,  # StripByteCounts, LONG, 1, size of image
                       0  # last IFD
                       )


def extract_images_from_pdf_page(xObject):
    image_list = []

    xObject = xObject['/Resources']['/XObject'].getObject()

    for obj in xObject:
        o = xObject[obj]
        if xObject[obj]['/Subtype'] == '/Image':
            size = (xObject[obj]['/Width'], xObject[obj]['/Height'])
            # getData() does not work for CCITTFaxDecode or DCTDecode
            # as of 1 Aug 2018. Not sure about JPXDecode.
            data = xObject[obj]._data
            
            color_space = xObject[obj]['/ColorSpace']
            if '/FlateDecode' in xObject[obj]['/Filter']:
                if isinstance(color_space, PyPDF2.generic.ArrayObject) and color_space[0] == '/Indexed':
                    color_space, base, hival, lookup = [v.getObject() for v in color_space] # pg 262
                
                if type(color_space) is PyPDF2.generic.ArrayObject:
                    color_space = color_space[0]
                mode = img_modes[color_space]

                data = xObject[obj].getData() # need to use getData() here
                img = Image.frombytes(mode, size, data)
                if color_space == '/Indexed':
                    img.putpalette(lookup.getData())
                    img = img.convert('RGB')
                imgByteArr = io.BytesIO()
                img.save(imgByteArr,format='PNG')
                image_list.append(PdfImage(data=imgByteArr,
                                   format='PNG',
                                   image_name=obj[1:]))
                    
            elif '/DCTDecode' in xObject[obj]['/Filter']:
                image_list.append(PdfImage(data=io.BytesIO(data),
                                   format='JPG',
                                   image_name=obj[1:]))
            elif '/JPXDecode' in xObject[obj]['/Filter']:
                image_list.append(PdfImage(data=io.BytesIO(data),
                                   format='JP2',
                                   image_name=obj[1:]))
            elif '/CCITTFaxDecode' in xObject[obj]['/Filter']:
                if xObject[obj]['/DecodeParms']['/K'] == -1:
                    CCITT_group = 4
                else:
                    CCITT_group = 3
                data = xObject[obj]._data 
                img_size = len(data)
                tiff_header = tiff_header_for_CCITT(
                    size[0], size[1], img_size, CCITT_group)
                im = Image.open(io.BytesIO(tiff_header + data))

                if xObject[obj].get('/BitsPerComponent') == 1:
                    # experimental condition
                    # http://users.fred.net/tds/leftdna/sciencetiff.html
                    im = ImageOps.flip(im)

                imgByteArr = io.BytesIO()
                im.save(imgByteArr,format='PNG')
                image_list.append(PdfImage(data=imgByteArr,
                                   format='PNG',
                                   image_name=obj[1:]))
            else:
                print ('Unhandled image type: {}'.format(xObject[obj]['/Filter']))
        else:
            image_list += extract_images_from_pdf_page(xObject[obj])
    
    return image_list

if __name__ == '__main__':
    try:
        filename = 'C:\\Users\\phill\\Downloads\\pg\\pantagruel.pdf' # sys.argv[1]
#        pages = sys.argv[2:]
#        pages = list(map(int, pages))
        abspath = path.abspath(filename)
    except BaseException:
        print(__doc__, file=sys.stderr)
        sys.exit()

    file = PyPDF2.PdfFileReader(open(filename, "rb"))

    number = 0

    for p in range(file.getNumPages()):
        page0 = file.getPage(p - 1)
        image_list = extract_images_from_pdf_page(page0)
        number += len(image_list)
        
        for pdf_image in image_list:
            img = Image.open(pdf_image.data)
            image_path = "{} - p. {} - {}.{}".format(
                abspath[:-4], p, pdf_image.image_name,pdf_image.format)
            img.save(image_path)

    print('-' * 20)
    print('{} extracted images'.format(number))
    print('-' * 20)