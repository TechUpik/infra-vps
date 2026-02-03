from prefect import flow, task
from datetime import datetime
import time


@task(retries=3, retry_delay_seconds=10)
def extrair_dados():
    print("Extraindo dados...")
    time.sleep(2)
    return {"data": datetime.utcnow().isoformat()}


@task
def processar_dados(dados):
    print("Processando:", dados)
    return dados["data"]


@task
def salvar_resultado(resultado):
    print("Salvando resultado:", resultado)


@flow(name="pipeline-exemplo")
def pipeline_exemplo():
    dados = extrair_dados()
    resultado = processar_dados(dados)
    salvar_resultado(resultado)


if __name__ == "__main__":
    pipeline_exemplo()
