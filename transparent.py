from pathlib import Path

from PIL import Image


SOURCE_FILE = Path(__file__).resolve().parent / "Company_logo.png"
OUTPUT_FILE = Path(__file__).resolve().parent / "company_logo_transparent.png"

# Increase this if some white background remains.
# Lower it if pale logo details become transparent.
WHITE_THRESHOLD = 245


def make_white_background_transparent(source_file, output_file):
    image = Image.open(source_file).convert("RGBA")
    pixels = []

    for red, green, blue, alpha in image.getdata():
        if red >= WHITE_THRESHOLD and green >= WHITE_THRESHOLD and blue >= WHITE_THRESHOLD:
            pixels.append((red, green, blue, 0))
        else:
            pixels.append((red, green, blue, alpha))

    image.putdata(pixels)
    image.save(output_file)


if __name__ == "__main__":
    make_white_background_transparent(SOURCE_FILE, OUTPUT_FILE)
    print(f"Created: {OUTPUT_FILE}")
