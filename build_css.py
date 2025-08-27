import subprocess
import os
import sys

def build_css():
    try:
        # Garantir que o diretório dist existe
        os.makedirs('./static/css/dist', exist_ok=True)

        # Encontrar o executável do tailwindcss
        tailwind_path = os.path.join('node_modules', '.bin', 'tailwindcss')
        if sys.platform == 'win32':
            tailwind_path += '.cmd'

        if not os.path.exists(tailwind_path):
            print(f"Tailwind não encontrado em {tailwind_path}")
            print("Tentando instalar o tailwindcss...")
            subprocess.run(['npm', 'install', 'tailwindcss'], check=True)

        # Executar o tailwindcss
        subprocess.run([
            'node',
            tailwind_path,
            '-i', './static/css/main.css',
            '-o', './static/css/dist/styles.css',
            '--minify'
        ], check=True)
        print("CSS compilado com sucesso!")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao compilar CSS: {e}")
        raise
    except Exception as e:
        print(f"Erro inesperado: {e}")
        raise

if __name__ == "__main__":
    build_css()