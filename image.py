import os
import argparse
import json
from PIL import Image, ImageDraw

def create_output_directory(path):
    """Creates a directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")

def process_images_in_folder(input_folder, output_folder, specific_files=None):
    """
    Processes all images in a folder: crops them to a 3:4 aspect ratio,
    adds a rounded border, and places them on a slightly larger 3:4 black canvas.
    """
    print(f"Starting image processing from '{input_folder}'...")
    
    # Ensure the output directory exists
    create_output_directory(output_folder)
    allowed_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.avif')

    if specific_files:
        candidates = specific_files
    else:
        candidates = os.listdir(input_folder)

    for filename in candidates:
        if filename.lower().endswith(allowed_extensions):
            try:
                # Construct full file path
                image_path = os.path.join(input_folder, filename)
                if not os.path.exists(image_path):
                    print(f"Skipping '{filename}' (not found in input folder)")
                    continue
                
                # Open the original image
                with Image.open(image_path) as original_image:
                    original_image = original_image.convert("RGBA")
                    original_width, original_height = original_image.size
                    target_ratio = 3 / 4
                    image_ratio = original_width / original_height

                    if image_ratio > target_ratio:
                        print(f"Cropping width of '{filename}' to 3:4 aspect ratio.")
                        new_width = int(original_height * target_ratio)
                        crop_margin = (original_width - new_width) // 2
                        crop_box = (crop_margin, 0, original_width - crop_margin, original_height)
                        original_image = original_image.crop(crop_box)

                    elif image_ratio < target_ratio:
                        print(f"Cropping height of '{filename}' to 3:4 aspect ratio.")
                        new_height = int(original_width / target_ratio)
                        crop_box = (0, 0, original_width, new_height)
                        original_image = original_image.crop(crop_box)

                    # If the ratio is already correct, no cropping is done.
                    # IMPORTANT: Update the dimensions after any potential cropping for subsequent steps
                    original_width, original_height = original_image.size
                    border_color = (255, 255, 255, 38)  # White with 15% opacity
                    background_color = (0, 0, 0)        # Black
                    radius = int(original_width * (16 / 360))
                    border_size = max(1, round(original_width * (2 / 360)))
                    bordered_img_size = (original_width + border_size * 2, original_height + border_size * 2)
                    bordered_img = Image.new('RGBA', bordered_img_size, (0, 0, 0, 0))
                    draw = ImageDraw.Draw(bordered_img)


                    draw.rounded_rectangle(
                        (0, 0, bordered_img_size[0], bordered_img_size[1]),
                        radius=radius,
                        fill=border_color
                    )

                    # a mask to round the corners of the original image
                    mask = Image.new('L', (original_width, original_height), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.rounded_rectangle((0, 0, original_width, original_height), radius=radius, fill=255)
                    bordered_img.paste(original_image, (border_size, border_size), mask)
                    
                    target_height = original_height * 1.2
                    new_height = round(target_height / 4) * 4
                    new_width = (new_height // 4) * 3
                    
                    content_width = bordered_img.width
                    if new_width < content_width:
                        new_width = content_width
                        new_height = round((new_width * 4 / 3) / 4) * 4

                    final_image = Image.new("RGB", (new_width, new_height), background_color)
                    paste_x = (new_width - bordered_img.width) // 2
                    paste_y = 0 
                    
                    final_image.paste(bordered_img, (paste_x, paste_y), bordered_img)
                    
                    output_path = os.path.join(output_folder, ''.join([str(filename.split('.')[0]),".jpeg"]))
                    final_image.save(output_path, 'JPEG', quality=95, subsampling=0, optimize=True)
                    print(f"Successfully processed and saved '{filename}' to '{output_folder}'")

            except Exception as e:
                print(f"Could not process {filename}. Reason: {e}")
                
    print("\nImage processing complete.")

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_INPUT_FOLDER = os.path.join(BASE_DIR, "input_images")
    DEFAULT_OUTPUT_FOLDER = os.path.join(BASE_DIR, "output_images")

    parser = argparse.ArgumentParser(description="Process images into 3:4 spotlight format.")
    parser.add_argument('--input-folder', default=DEFAULT_INPUT_FOLDER, help='Folder containing input images')
    parser.add_argument('--output-folder', default=DEFAULT_OUTPUT_FOLDER, help='Folder where processed images are saved')
    parser.add_argument('--files-json', help='JSON array of specific filenames to process')
    args = parser.parse_args()

    input_folder = args.input_folder
    output_folder = args.output_folder

    if not os.path.exists(input_folder):
        print(f"Input folder '{input_folder}' not found. Creating it for you.")
        os.makedirs(input_folder)
        try:
            # Create a placeholder image that is WIDER than 3:4 to demonstrate the new cropping
            placeholder = Image.new('RGB', (600, 360), (180, 70, 130)) 
            placeholder.save(os.path.join(input_folder, 'wide_placeholder_image.png'))
            print(f"Created a wide placeholder image in '{input_folder}'.")
            print("Please add your own images to this folder and run the script again.")
        except Exception as e:
            print(f"Could not create placeholder image. Please check permissions. Error: {e}")

    specific_files = None
    if args.files_json:
        try:
            parsed = json.loads(args.files_json)
            if isinstance(parsed, list):
                specific_files = parsed
            else:
                print("Expected --files-json to contain a JSON array of filenames.")
                exit(1)
        except json.JSONDecodeError:
            print("Could not decode --files-json argument. Ensure it is valid JSON.")
            exit(1)

    process_images_in_folder(input_folder, output_folder, specific_files)