import subprocess

def compress_pdf(input_path, output_path, gs_path, quality='ebook'):
    """
    Compress PDF using Ghostscript.

    quality: one of 'screen', 'ebook', 'printer', 'prepress', 'default'
    """
    settings_map = {
        'screen': '/screen',
        'ebook': '/ebook',
        'printer': '/printer',
        'prepress': '/prepress',
        'default': '/default'
    }
    gs_quality = settings_map.get(quality, '/ebook')

    cmd = [
        gs_path,
        '-sDEVICE=pdfwrite',
        '-dCompatibilityLevel=1.4',
        f'-dPDFSETTINGS={gs_quality}',
        '-dNOPAUSE',
        '-dQUIET',
        '-dBATCH',
        f'-sOutputFile={output_path}',
        input_path
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"Ghostscript error: {result.stderr.decode()}")

    return output_path
