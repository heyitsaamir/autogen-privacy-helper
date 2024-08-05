import sys

from svg_to_png.svg_to_png import convert_svg_to_png

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 script.py <input_file> <output_filename>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_filename = sys.argv[2]
    convert_svg_to_png(file=input_file, out_file=output_filename)

if __name__ == "__main__":
    main()