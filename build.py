"""Publicar únicamente los assets estáticos para la CDN de Vercel."""

from pathlib import Path
from shutil import copytree


def main():
    root = Path(__file__).resolve().parent
    copytree(root / "compilando" / "static", root / "public" / "static", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
