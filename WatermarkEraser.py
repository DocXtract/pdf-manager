from pypdf import PdfWriter, PdfReader

path = "disburse-watermark.pdf"

# writer = PdfWriter()
# reader = PdfReader(path)
# writer.append_pages_from_reader(reader)
# writer.remove_images()

# with open(path, "wb") as output_stream:
#     writer.write(output_stream)
# output_stream.close()


def remove_image(pdf_path, page_num, image_num):
    # Open the PDF file for reading
    with open(pdf_path, "rb") as in_file:
        # Create a PdfFileReader object
        pdf_reader = PdfReader(in_file)

        # Get the specified page object
        page = pdf_reader.pages[page_num]

        # Get the page's content stream object
        content = page['/Annots'].get_object()

        # Remove the specified image content stream
        print(page['/Annots'][0])
        content.pop(image_num)

        # Update the page object with the modified content stream
        page.__setitem__('/Contents', content)

        # Create a PdfFileWriter object for writing the modified PDF
        pdf_writer = PdfWriter()
        pdf_writer.add_page(page)

        # Write the modified PDF to a new file with -decrypted appended to the name
        with open(pdf_path.replace('.pdf', '-decrypted.pdf'), "wb") as out_file:
            pdf_writer.write(out_file)

    return pdf_path.replace('.pdf', '-decrypted.pdf')
remove_image(path, 0, 0)