import os
import sys
import shutil
import json
import re
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from rich.text import Text
from PIL import Image
from fontTools.ttLib import TTFont

console = Console()

def load_template():
    template_path = os.path.abspath("brim.html")
    if not os.path.exists(template_path):
        console.print("[bold red]Error:[/bold red] Template 'brim.html' not found!")
        sys.exit(1)
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

def extract_brim_tags(template):
    brim_tags = {}
    brim_pattern = re.compile(r"<brim:(.*?)>(.*?)</brim:\1>", re.DOTALL)
    matches = brim_pattern.findall(template)
    for tag, value in matches:
        tag = tag.lower().strip()
        value = value.strip()
        if tag not in brim_tags:
            brim_tags[tag] = []
        brim_tags[tag].append(value)
    return brim_tags

def replace_placeholders(template, data):
    def evaluate_expression(match):
        expression = match.group(1).strip()

        if expression.startswith("# "):
            return ""
        
        try:
            return str(eval(expression, {}, data))
        except Exception as e:
            if not (("is not defined") in str(e)):
                console.print(f"[bold red]Error evaluating expression:[/bold red] {expression} -> {e}")
            return f"{{{expression}}}"

    template = re.sub(r"\{(.*?)\}", evaluate_expression, template)

    def handle_loops(template, data):
        while '{#' in template and '#}' in template:
            start_tag = template.find('{#')
            end_tag = template.find('#}', start_tag)
            loop_block = template[start_tag + 2:end_tag].strip()
            match = re.match(r"for (\w+) in (\w+)", loop_block)
            if match:
                var_name = match.group(1)
                list_name = match.group(2)

                if list_name in data:
                    loop_content = template[end_tag + 2:template.find('{# endfor #}', end_tag)].strip()
                    loop_result = ''
                    for item in data[list_name]:
                        loop_result += loop_content.replace(f'{{{var_name}}}', str(item))

                    template = template[:start_tag] + loop_result + template[template.find('{# endfor #}', end_tag) + len('{# endfor #}'):]

        return template

    template = handle_loops(template, data)
    
    # Remove unwanted newlines, excessive whitespaces
    template = re.sub(r"\n\s*\n", "\n", template)  # Replace multiple newlines with a single newline
    template = re.sub(r">\s*<", "><", template)    # Remove spaces between tags
    return template

def remove_brim_tags(html):
    return re.sub(r"<brim:.*?>.*?</brim:.*?>", "", html, flags=re.DOTALL).strip()

def compress_image(image_path):
    try:
        original_size = os.path.getsize(image_path)
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img.save(image_path, "JPEG", quality=85, optimize=True)
        compressed_size = os.path.getsize(image_path)
        file_name = os.path.basename(image_path)
        console.print(f"[bold cyan]{file_name}[/bold cyan]  [dim]({original_size / 1024:.2f} KB)[/dim] "
                      f"→ [bold green]{compressed_size / 1024:.2f} KB[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error optimizing image {image_path}: {e}[/bold red]")

def compress_font(font_path):
    try:
        font = TTFont(font_path)
        compressed_font_path = f"{font_path}_compressed.ttf"
        font.save(compressed_font_path)
        console.print(f"[bold green]Compressed font saved:[/bold green] {compressed_font_path}")
    except Exception as e:
        console.print(f"[bold red]Error compressing font {font_path}: {e}[/bold red]")

def optimize_images_in_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_path = os.path.join(root, file)
                compress_image(image_path)

def optimize_fonts_in_directory(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.ttf', '.otf')):
                font_path = os.path.join(root, file)
                compress_font(font_path)

def process_json_files(source_dir, dest_dir, template):
    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.endswith(".json"):
                json_path = os.path.join(root, file)
                rel_path = os.path.relpath(json_path, source_dir)
                new_html_path = os.path.join(dest_dir, rel_path).replace(".json", ".html")
                os.makedirs(os.path.dirname(new_html_path), exist_ok=True)
                with open(json_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                        html_content = replace_placeholders(template, data)
                        html_content = remove_brim_tags(html_content)
                        with open(new_html_path, "w", encoding="utf-8") as html_file:
                            html_file.write(html_content)
                    except json.JSONDecodeError:
                        console.print(f"[bold red]Invalid JSON:[/bold red] {json_path}")

def copy_files(source_dir, dest_dir):
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
    total_files = sum(len(files) for _, _, files in os.walk(source_dir))
    with Progress() as progress:
        task = progress.add_task("[cyan]Copying files...[/cyan]", total=total_files)
        for root, _, files in os.walk(source_dir):
            rel_path = os.path.relpath(root, source_dir)
            target_dir = os.path.join(dest_dir, rel_path) if rel_path != "." else dest_dir
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            for file in files:
                if not file.endswith(".json"):
                    src_path = os.path.join(root, file)
                    dest_path = os.path.join(target_dir, file)
                    shutil.copy2(src_path, dest_path)
                progress.update(task, advance=1)
        progress.update(task, completed=total_files)

def display_brim_tags(brim_tags):
    table = Table(show_header=True, header_style="bold magenta", show_edge=False)
    table.add_column("Key", style="bold cyan", width=25)
    table.add_column("Value", style="bold green", width=50)
    
    for key, values in brim_tags.items():
        for value in values:
            table.add_row(key, value)
    
    console.print(table)

def main():
    try:
        template = load_template()
        brim_tags = extract_brim_tags(template)
        
        console.print("[bold cyan]Brim Tags Found:[/bold cyan]")
        display_brim_tags(brim_tags)
        
        if "pre" in brim_tags:
            for pre in brim_tags["pre"]:
                exec(pre)
        
        source_dir = sys.argv[1] if len(sys.argv) > 1 else "."
        source_dir = os.path.abspath(source_dir)
        dest_dir = os.path.abspath("brim")
        
        if not os.path.exists(source_dir):
            console.print(f"[bold red]Error:[/bold red] Directory '{source_dir}' not found!")
            sys.exit(1)
        
        if "optimize:image" in brim_tags and brim_tags["optimize:image"][0].lower() == "true":
            optimize_images_in_directory(source_dir)
        
        if "optimize:font" in brim_tags and brim_tags["optimize:font"][0].lower() == "true":
            optimize_fonts_in_directory(source_dir)
        
        copy_files(source_dir, dest_dir)
        process_json_files(source_dir, dest_dir, template)
        
        if "post" in brim_tags:
            for post in brim_tags["post"]:
                exec(post)
        
        console.print("[bold green]Done![/bold green] ✅")
    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
