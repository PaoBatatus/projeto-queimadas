from datetime import datetime
from pathlib import Path
import time
import zipfile

import pandas as pd
import requests


ANOS = [2018, 2019, 2020]
URL_BASE = (
    "https://dataserver-coids.inpe.br/queimadas/queimadas/"
    "focos/csv/anual/Brasil_todos_sats"
)

# Encontra a raiz do repositório a partir deste arquivo.
RAIZ = Path(__file__).resolve().parents[1]
PASTA_BRONZE = RAIZ / "data" / "bronze"
PASTA_DOCS = RAIZ / "docs"
ARQUIVO_METADADOS = PASTA_DOCS / "metadados_coleta.csv"


def baixar_arquivo(url: str, destino: Path, tentativas: int = 3) -> None:
    """Baixa um arquivo, repetindo a tentativa se houver falha."""
    temporario = destino.with_suffix(destino.suffix + ".part")

    for tentativa in range(1, tentativas + 1):
        try:
            resposta = requests.get(url, stream=True, timeout=(20, 180))
            resposta.raise_for_status()

            with temporario.open("wb") as arquivo:
                for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                    if bloco:
                        arquivo.write(bloco)

            temporario.replace(destino)
            return

        except requests.RequestException:
            temporario.unlink(missing_ok=True)
            if tentativa == tentativas:
                raise
            time.sleep(3)


def contar_linhas_e_colunas(caminho_zip: Path) -> tuple[int, int]:
    """Conta as linhas do CSV em blocos, sem carregar o arquivo inteiro."""
    with zipfile.ZipFile(caminho_zip) as pacote:
        arquivos_csv = [
            nome for nome in pacote.namelist()
            if nome.lower().endswith(".csv")
        ]

        if not arquivos_csv:
            raise ValueError(f"Nenhum CSV encontrado em {caminho_zip.name}")

        total_linhas = 0
        total_colunas = None

        with pacote.open(arquivos_csv[0]) as arquivo:
            for lote in pd.read_csv(
                arquivo,
                sep=",",
                chunksize=250_000,
                low_memory=False
            ):
                total_linhas += len(lote)
                if total_colunas is None:
                    total_colunas = len(lote.columns)

    return total_linhas, total_colunas


def main() -> None:
    PASTA_BRONZE.mkdir(parents=True, exist_ok=True)
    PASTA_DOCS.mkdir(parents=True, exist_ok=True)

    registros = []

    for ano in ANOS:
        nome = f"focos_br_todos-sats_{ano}.zip"
        destino = PASTA_BRONZE / f"focos_{ano}.zip"
        url = f"{URL_BASE}/{nome}"

        if destino.exists():
            print(f"{ano}: ZIP já existe; vou reutilizá-lo.")
        else:
            print(f"{ano}: baixando...")
            baixar_arquivo(url, destino)

        linhas, colunas = contar_linhas_e_colunas(destino)

        registros.append({
            "ano": ano,
            "url": url,
            "data_download": datetime.fromtimestamp(
                destino.stat().st_mtime
            ).astimezone().isoformat(timespec="seconds"),
            "arquivo": destino.name,
            "linhas": linhas,
            "colunas": colunas,
            "tamanho_bytes": destino.stat().st_size,
        })

        print(f"{ano}: {linhas:,} linhas, {colunas} colunas")

    metadados = pd.DataFrame(registros)
    metadados.to_csv(ARQUIVO_METADADOS, index=False)

    print(f"\nTotal de linhas: {metadados['linhas'].sum():,}")
    print(f"Metadados salvos em: {ARQUIVO_METADADOS}")


if __name__ == "__main__":
    main()
