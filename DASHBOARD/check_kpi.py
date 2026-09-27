import pandas as pd
import urllib.request
import hashlib
import re
import unicodedata

url = 'https://raw.githubusercontent.com/Lima990/Banco_de_Dados_IG_Bahia/main/DASHBOARD/base_de_dados_IGs.xlsx'
urllib.request.urlretrieve(url, 'base_de_dados_IGs.xlsx')

def limpar(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    return None if s.lower() in ('nan', '', 'none') else s

def normalizar_texto_bibliografico(val):
    texto = limpar(val)
    if not texto:
        return ''
    texto = unicodedata.normalize('NFKD', texto.lower())
    texto = ''.join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', ' ', texto).strip()

def gerar_estudo_id(row):
    titulo = normalizar_texto_bibliografico(row.get('titulo_trabalho'))
    ano = pd.to_numeric(row.get('ano'), errors='coerce')
    referencia = normalizar_texto_bibliografico(row.get('referencia_abnt'))
    link = normalizar_texto_bibliografico(row.get('link'))
    if titulo:
        ano_chave = str(int(ano)) if pd.notna(ano) else ''
        chave = f'titulo:{titulo}|ano:{ano_chave}'
    elif referencia:
        chave = f'referencia:{referencia}'
    elif link:
        chave = f'link:{link}'
    else:
        return None
    return 'EST-' + hashlib.sha1(chave.encode('utf-8')).hexdigest()[:12]

def extrair_coords(val):
    try:
        p = str(val).split(',')
        if len(p) >= 2:
            return float(p[0].strip()), float(p[1].strip())
    except Exception:
        pass
    return None, None

def macro_tipo(val):
    v = str(val).lower()
    if 'ig registrada' in v:
        return 'IG Registrada'
    if 'artesanato' in v:
        return 'Artesanato'
    if any(x in v for x in ['bebida','vinho','cacha�a','licor','destilado']):
        return 'Bebidas'
    if 'agroalimentar' in v or 'derivados' in v:
        return 'Agroalimentar'
    if 'agr�cola' in v or 'agricola' in v:
        return 'Agr�cola'
    if any(x in v for x in ['servi�o','servico','turismo']):
        return 'Servi�os'
    return 'Outros'

def macro_modalidade(val):
    v = str(val).lower().strip()
    if 'denomina��o de origem' in v or v == 'do':
        return 'DO'
    if 'indica��o de proced�ncia' in v or v == 'ip':
        return 'IP'
    return 'Potencial'

df = pd.read_excel('base_de_dados_IGs.xlsx', sheet_name=0)
df = df[df['nome_produto'].astype(str).str.lower() != 'nome_produto'].copy()
df = df.dropna(subset=['nome_produto']).copy()
df[['latitude','longitude']] = df['geometria_espacial'].apply(lambda v: pd.Series(extrair_coords(v)))
df['macro_tipo'] = df['tipo_produto'].apply(macro_tipo)
df['macro_modalidade'] = df['modalidade_ig'].apply(macro_modalidade)
df['estudo_id'] = df.apply(gerar_estudo_id, axis=1)


def agregar(grupo):
    nome_final = grupo.name
    principal = grupo.copy()
    principal['_p'] = principal.apply(
        lambda row: row.notna().sum()
        + (100 if 'concedid' in str(row.get('status_diagnostico', '')).lower() else 0)
        + (50 if 'pedido em analise' in str(row.get('status_diagnostico', '')).lower() or 'em analise' in str(row.get('status_diagnostico', '')).lower() else 0),
        axis=1,
    )
    base = principal.sort_values('_p', ascending=False).iloc[0]
    return pd.Series({'nome_produto': nome_final,
                      'n_estudos': grupo['estudo_id'].dropna().nunique()})

df['chave_agrupamento'] = df['nome_produto'].str.split('(').str[0].str.strip()
df_ag = df.groupby('chave_agrupamento', sort=False).apply(agregar).reset_index(drop=True)
print('estudos_unicos', int(df['estudo_id'].nunique()))
print('associacoes_ativo_estudo', int(df_ag['n_estudos'].sum()))
print('multi_estudos', int((df_ag['n_estudos'] > 1).sum()))
