"""Carga inicial da planilha para PostgreSQL.

Uso:
    $env:DATABASE_URL = "postgresql+psycopg://usuario:senha@host:5432/banco"
    py importar_excel_postgres.py base_de_dados_IGs.xlsx
"""

import sys
import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


COLUNAS_ESTUDOS = [
    'origem_id', 'nome_produto', 'territorio_identidade', 'municipios_abrangidos',
    'tipo_produto', 'modalidade_ig', 'singularidade', 'tradicao_historica',
    'vinculo_territorial', 'viabilidade_economica', 'atores_chave',
    'geometria_espacial', 'fonte_dados', 'titulo_trabalho', 'link', 'ano',
    'referencia_abnt', 'status_diagnostico', 'string_busca', 'fonte_busca',
]
COLUNAS_IGS = [
    'nome_produto', 'territorio_identidade', 'municipios_abrangidos',
    'tipo_produto', 'modalidade_ig', 'status_diagnostico',
    'geometria_espacial', 'ano',
]


def valor_texto(valor):
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    return texto or None


def normalizar_texto_bibliografico(valor):
    texto = valor_texto(valor)
    if not texto:
        return ''
    texto = unicodedata.normalize('NFKD', texto.lower())
    texto = ''.join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()


def valor_id_origem(valor):
    if pd.isna(valor):
        return None
    try:
        numero = float(valor)
        if numero.is_integer():
            return str(int(numero))
    except (TypeError, ValueError):
        pass
    return str(valor).strip() or None


def chave_estudo(linha):
    titulo = normalizar_texto_bibliografico(linha.get('titulo_trabalho'))
    ano = pd.to_numeric(linha.get('ano'), errors='coerce')
    referencia = normalizar_texto_bibliografico(linha.get('referencia_abnt'))
    link = normalizar_texto_bibliografico(linha.get('link'))

    if titulo:
        ano_chave = str(int(ano)) if pd.notna(ano) else ''
        chave = f'titulo:{titulo}|ano:{ano_chave}'
    elif referencia:
        chave = f'referencia:{referencia}'
    elif link:
        chave = f'link:{link}'
    else:
        return None

    digest = hashlib.sha1(chave.encode('utf-8')).hexdigest()[:12]
    return f'EST-{digest}'


def chave_produto(valor):
    return str(valor).split('(')[0].strip()


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Uso: py importar_excel_postgres.py caminho\base_de_dados_IGs.xlsx')

    database_url = __import__('os').environ.get('DATABASE_URL')
    if not database_url:
        raise SystemExit('Defina DATABASE_URL antes de executar a carga.')

    arquivo = Path(sys.argv[1])
    if not arquivo.exists():
        raise SystemExit(f'Arquivo não encontrado: {arquivo}')

    estudos = pd.read_excel(arquivo, sheet_name='BD_IGs_mapeadas')
    concedidas = pd.read_excel(arquivo, sheet_name='BD_IGs_concedida_analise')

    estudos = estudos[estudos['nome_produto'].notna()].copy()
    concedidas = concedidas[concedidas['nome_produto'].notna()].copy()
    estudos['origem_id'] = estudos['id'].map(valor_id_origem)
    estudos['estudo_key'] = estudos.apply(chave_estudo, axis=1)
    estudos['chave_agrupamento'] = estudos['nome_produto'].map(chave_produto)
    estudos['ano'] = pd.to_numeric(estudos.get('ano'), errors='coerce').astype('Int64')
    concedidas['ano'] = pd.to_numeric(concedidas.get('ano'), errors='coerce').astype('Int64')

    engine = create_engine(database_url, pool_pre_ping=True)
    schema = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
    with engine.begin() as conexao:
        for comando in schema.split(';'):
            if comando.strip():
                conexao.execute(text(comando))
        conexao.execute(text('TRUNCATE TABLE estudos_igs, igs_concedidas RESTART IDENTITY'))

    estudos = estudos[[col for col in COLUNAS_ESTUDOS if col in estudos.columns]]
    concedidas = concedidas[[col for col in COLUNAS_IGS if col in concedidas.columns]]
    estudos.to_sql('estudos_igs', engine, if_exists='append', index=False, method='multi')
    concedidas.to_sql('igs_concedidas', engine, if_exists='append', index=False, method='multi')

    with engine.begin() as conexao:
        conexao.execute(text(
            'INSERT INTO carga_dados (arquivo_origem, linhas_estudos, linhas_igs_concedidas) '
            'VALUES (:arquivo, :estudos, :concedidas)'
        ), {
            'arquivo': arquivo.name,
            'estudos': len(estudos),
            'concedidas': len(concedidas),
        })

    print(f'Carga concluída: {len(estudos)} estudos e {len(concedidas)} IGs concedidas.')


if __name__ == '__main__':
    main()
