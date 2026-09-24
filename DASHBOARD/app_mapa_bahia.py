import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import os
import re
import html as _html
import unicodedata
from collections import Counter
import requests
from io import BytesIO

st.set_page_config(
    page_title="IGs Bahia: Diagnóstico Territorial",
    layout="wide",
    initial_sidebar_state="collapsed"
)

MOSTRAR_AUDITORIA = True

# -------------------------------------------------
# CONFIGURAÇÃO DO GITHUB
# -------------------------------------------------
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/Lima990/Banco_de_Dados_IG_Bahia/main/"
GITHUB_XLSX_URL = GITHUB_RAW_BASE + "base_de_dados_IGs.xlsx"
GITHUB_GEOJSON_URL = (
    "https://raw.githubusercontent.com/CleitonOERocha/Shapefiles/master/"
    "Shapefiles/Territorios%20de%20Identidade_BA/Terri_iden_ba_v2.json"
)

# -------------------------------------------------
# SIDEBAR STYLE
# -------------------------------------------------
st.markdown(
    """
    <style>
    [data-testid="stSidebar"]{
        background:#0d1117;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
# NUMERAÇÃO OFICIAL DOS 27 TIs
# -------------------------------------------------
NUMERACAO_TI = {
    'Irecê': 1,
    'Velho Chico': 2,
    'Chapada Diamantina': 3,
    'Sisal': 4,
    'Litoral Sul': 5,
    'Baixo Sul': 6,
    'Extremo Sul': 7,
    'Médio Sudoeste da Bahia': 8,
    'Vale do Jiquiriçá': 9,
    'Sertão do São Francisco': 10,
    'Bacia do Rio Grande': 11,
    'Bacia do Paramirim': 12,
    'Sertão Produtivo': 13,
    'Piemonte do Paraguaçu': 14,
    'Bacia do Jacuípe': 15,
    'Piemonte da Diamantina': 16,
    'Semiárido Nordeste II': 17,
    'Litoral Norte e Agreste Baiano': 18,
    'Portal do Sertão': 19,
    'Sudoeste Baiano': 20,
    'Recôncavo': 21,
    'Médio Rio de Contas': 22,
    'Bacia do Rio Corrente': 23,
    'Itaparica': 24,
    'Piemonte Norte do Itapicuru': 25,
    'Metropolitano de Salvador': 26,
    'Costa do Descobrimento': 27,
}

TERRITORIOS_27 = list(NUMERACAO_TI.keys())

COLUNAS_ESPERADAS = [
    'nome_produto','territorio_identidade','municipios_abrangidos','tipo_produto',
    'modalidade_ig','status_diagnostico','singularidade','tradicao_historica',
    'vinculo_territorial','viabilidade_economica','atores_chave','geometria_espacial'
]

NOMES_COLUNA_TITULO = ('titulo_trabalho', 'titulo', 'titulos', 'título', 'títulos')

# -------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------
def esc(v):
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return ''
    except (TypeError, ValueError):
        pass
    return _html.escape(str(v), quote=True)

def formatar_ti(nome):
    num = NUMERACAO_TI.get(nome)
    if num:
        return f"{num:02d} - {nome}"
    return nome

def norm_titulo(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    s = unicodedata.normalize('NFKD', str(v))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s or None

def detectar_coluna_titulo(colunas):
    for c in colunas:
        if str(c).strip().lower() in NOMES_COLUNA_TITULO:
            return c
    return None

def macro_tipo(val):
    v = str(val).lower()
    if 'ig registrada' in v:
        return 'IG Registrada'
    if 'artesanato' in v:
        return 'Artesanato'
    if any(x in v for x in ['bebida','vinho','cachaça','licor','destilado']):
        return 'Bebidas'
    if 'agroalimentar' in v or 'derivados' in v:
        return 'Agroalimentar'
    if 'agrícola' in v or 'agricola' in v:
        return 'Agrícola'
    if any(x in v for x in ['serviço','servico','turismo']):
        return 'Serviços'
    return 'Outros'

def macro_modalidade(val):
    v = str(val).lower().strip()
    if 'denominação de origem' in v or v == 'do':
        return 'DO'
    if 'indicação de procedência' in v or v == 'ip':
        return 'IP'
    return 'Potencial'

def extrair_coords(val):
    try:
        p = str(val).split(',')
        if len(p) >= 2:
            return float(p[0].strip()), float(p[1].strip())
    except (ValueError, TypeError):
        pass
    return None, None

CORRECAO_TERRITORIOS = {
    'Baixo Sao Francisco': 'Sertão do São Francisco',
    'Baixo São Francisco': 'Sertão do São Francisco',
    'Vale do Jiquiriça': 'Vale do Jiquiriçá',
}

def normalizar_territorios(val):
    sem_parentese = str(val).split('(')[0]
    partes = re.split(r'[;/]', sem_parentese)
    resultado = []
    for p in partes:
        nome = p.strip()
        if nome:
            resultado.append(CORRECAO_TERRITORIOS.get(nome, nome))
    return resultado

def normalizar_territorio(val):
    lst = normalizar_territorios(val)
    return lst[0] if lst else str(val)

def formatar_territorios_str(val, sep=" · "):
    if val is None or (not isinstance(val, str) and pd.isna(val)):
        return ''
    return sep.join(formatar_ti(t) for t in normalizar_territorios(val))

def limpar(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return None if s.lower() in ('nan','','none') else s

def exibir_conteudo_ficha(row, show_criteria=True):
    modal = row.get('macro_modalidade', '')
    tag = (
        '<span class="tag-ip">IP</span>' if modal == 'IP' else
        '<span class="tag-do">DO</span>' if modal == 'DO' else
        '<span class="tag-pot">Potencial</span>'
    )
    tis_exibir = normalizar_territorios(row['territorio_identidade'])
    tis_formatados = [formatar_ti(t) for t in tis_exibir]

    i1, i2 = st.columns(2)
    with i1:
        st.markdown(f"**Município(s):** {row['municipios_abrangidos']}")
        st.markdown(f"**Tipo:** {row['tipo_produto']}")
        st.markdown(f"**Modalidade:** {tag} {esc(row.get('modalidade_ig', ''))}", unsafe_allow_html=True)
        st.markdown(f"**Status:** `{row.get('status_diagnostico', '')}`")
        if len(tis_exibir) > 1:
            st.markdown(f"**Territórios:** {' · '.join(tis_formatados)}")
    with i2:
        if row.get('atores_chave'):
            st.markdown(f"**Atores-chave:** {row['atores_chave']}")
        if row.get('viabilidade_economica'):
            st.info(f"💼 {row['viabilidade_economica']}")

    if show_criteria:
        st.markdown("---")
        st.markdown("**🔍 Critérios INPI:**")
        cr1, cr2, cr3, cr4 = st.columns(4)
        criterios = [
            ("Singularidade", row.get('singularidade')),
            ("Tradição Histórica", row.get('tradicao_historica')),
            ("Vínculo Territorial", row.get('vinculo_territorial')),
            ("Viab. Econômica", row.get('viabilidade_economica')),
        ]
        for col_crit, (nome_c, val_c) in zip([cr1, cr2, cr3, cr4], criterios):
            with col_crit:
                cls = 'crit-ok' if val_c else 'crit-no'
                ico = '✅' if val_c else '❌'
                st.markdown(f'<div class="{cls}">{ico} <b>{nome_c}</b></div>', unsafe_allow_html=True)
                if val_c:
                    with st.expander("ver"):
                        st.write(val_c)

    estudos = row.get('estudos') or []
    if estudos:
        st.markdown("---")
        with st.expander(f"📚 Ver {len(estudos)} {'estudo' if len(estudos) == 1 else 'estudos'}"):
            for i_e, est in enumerate(estudos, 1):
                ano_s = f" · {est['ano']}" if est.get('ano') else ''
                bloco_titulo = (
                    f"<div style='font-size:13px;color:#E6EDF3;margin-bottom:3px'>"
                    f"<b>{esc(est.get('titulo'))}</b></div>"
                ) if est.get('titulo') else ""
                bloco_fonte = (
                    f"<div style='font-size:12px;color:#8B949E;margin-bottom:3px'>"
                    f"<b>Fonte:</b> {esc(est.get('fonte'))}</div>"
                ) if est.get('fonte') else ""
                bloco_abnt = (
                    f"<div class='abnt-box'>{esc(est.get('referencia_abnt'))}</div>"
                ) if est.get('referencia_abnt') else ""
                bloco_link = (
                    f"<div style='margin-top:7px'><a href='{esc(est.get('link'))}' target='_blank' "
                    f"style='color:#58a6ff;font-size:12px;'>🔗 Acessar trabalho completo</a></div>"
                ) if est.get('link') else ""
                st.markdown(
                    f"""
                    <div class="estudo-card">
                        <div class="estudo-badge">Estudo {i_e}{ano_s}</div>
                        {bloco_titulo}{bloco_fonte}{bloco_abnt}{bloco_link}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# -------------------------------------------------
# CARREGAMENTO
# -------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@st.cache_data(ttl=300)
def baixar_arquivo_do_github(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content

@st.cache_data(ttl=300)
def carregar_excel_atualizado():
    try:
        conteudo = baixar_arquivo_do_github(GITHUB_XLSX_URL)
        return pd.read_excel(BytesIO(conteudo), sheet_name=0)
    except Exception as e:
        st.warning(f"⚠️ Não foi possível baixar a planilha do GitHub. Usando arquivo local. Erro: {e}")
        arquivo_excel = os.path.join(BASE_DIR, "base_de_dados_IGs.xlsx")
        return pd.read_excel(arquivo_excel, sheet_name=0)

@st.cache_data(ttl=300)
def carregar_aba_excel_atualizada(sheet_name):
    try:
        conteudo = baixar_arquivo_do_github(GITHUB_XLSX_URL)
        return pd.read_excel(BytesIO(conteudo), sheet_name=sheet_name)
    except Exception:
        arquivo_excel = os.path.join(BASE_DIR, "base_de_dados_IGs.xlsx")
        return pd.read_excel(arquivo_excel, sheet_name=sheet_name)

@st.cache_data
def carregar_dados():
    try:
        df = carregar_excel_atualizado()

        ausentes = [c for c in COLUNAS_ESPERADAS if c not in df.columns]
        if ausentes:
            st.warning(f"⚠️ Colunas ausentes na planilha (preenchidas como vazias): {ausentes}")
        for c in ausentes:
            df[c] = None

        df = df[df['nome_produto'].astype(str).str.lower() != 'nome_produto'].copy()
        df = df.dropna(subset=['nome_produto']).copy()

        col_titulo = detectar_coluna_titulo(df.columns)
        df['titulo_norm'] = df[col_titulo].apply(norm_titulo) if col_titulo else None

        df[['latitude', 'longitude']] = df['geometria_espacial'].apply(
            lambda x: pd.Series(extrair_coords(x))
        )

        df['macro_tipo']       = df['tipo_produto'].apply(macro_tipo)
        df['macro_modalidade'] = df['modalidade_ig'].apply(macro_modalidade)
        df['territorio_norm']  = df['territorio_identidade'].apply(normalizar_territorio)
        if 'ano' in df.columns:
            df['ano'] = pd.to_numeric(df['ano'], errors='coerce')

        df['chave_display'] = (
            df['nome_produto'].astype(str).str.split('(').str[0]
            .str.replace(r'\s+', ' ', regex=True).str.strip()
        )
        df['chave_agrupamento'] = df['chave_display'].apply(norm_titulo)

        def agregar(grupo):
            nome_final = grupo['chave_display'].iloc[0]

            if not any(p in nome_final.lower() for p in [' de ', ' do ', ' da ']):
                primeira_linha = grupo.iloc[0]
                municipios = primeira_linha.get('municipios_abrangidos', '')
                if municipios and isinstance(municipios, str):
                    primeiro_municipio = municipios.split(',')[0].strip()
                    if primeiro_municipio.lower() not in nome_final.lower():
                        nome_final = f"{nome_final} de {primeiro_municipio}"

            principal = grupo.copy()

            def priority_score(row):
                score = row.notna().sum()
                status = str(row.get('status_diagnostico', '')).lower()
                if 'concedid' in status:
                    score += 100
                elif 'pedido em analise' in status or 'em analise' in status:
                    score += 50
                return score

            principal['_p'] = principal.apply(priority_score, axis=1)
            base = principal.sort_values('_p', ascending=False).iloc[0]

            estudos, vistos = [], set()
            for _, row in grupo.iterrows():
                titulo = limpar(row.get(col_titulo)) if col_titulo else None
                ref    = limpar(row.get('referencia_abnt'))
                link   = limpar(row.get('link'))
                fonte  = limpar(row.get('fonte_dados'))
                ano    = row.get('ano')
                chave  = norm_titulo(titulo) or norm_titulo(ref) or link or norm_titulo(fonte)
                if chave and chave not in vistos:
                    vistos.add(chave)
                    estudos.append({
                        'ano': int(ano) if pd.notna(ano) else None,
                        'titulo': titulo,
                        'fonte': fonte,
                        'link': link,
                        'referencia_abnt': ref
                    })

            return pd.Series({
                'chave':                 grupo.name,
                'nome_produto':          nome_final,
                'territorio_identidade': base['territorio_identidade'],
                'territorio_norm':       base['territorio_norm'],
                'municipios_abrangidos': base['municipios_abrangidos'],
                'tipo_produto':          base['tipo_produto'],
                'macro_tipo':            base['macro_tipo'],
                'modalidade_ig':         base['modalidade_ig'],
                'macro_modalidade':      base['macro_modalidade'],
                'singularidade':         limpar(base.get('singularidade')),
                'tradicao_historica':    limpar(base.get('tradicao_historica')),
                'vinculo_territorial':   limpar(base.get('vinculo_territorial')),
                'viabilidade_economica': limpar(base.get('viabilidade_economica')),
                'atores_chave':          limpar(base.get('atores_chave')),
                'status_diagnostico':    limpar(base.get('status_diagnostico')),
                'latitude':              base.get('latitude'),
                'longitude':             base.get('longitude'),
                'ano':                   base.get('ano'),
                'n_estudos':             len(estudos),
                'estudos':               estudos,
            })

        df_ag = (
            df.groupby('chave_agrupamento', sort=False, group_keys=False)
              .apply(agregar)
              .reset_index(drop=True)
        )

        df_of = pd.DataFrame()
        try:
            df_of = carregar_aba_excel_atualizada("BD_IGs_concedida_analise")
            df_of = df_of.dropna(subset=['nome_produto']).copy()

            if 'geometria_espacial' in df_of.columns:
                df_of[['latitude', 'longitude']] = df_of['geometria_espacial'].apply(
                    lambda v: pd.Series(extrair_coords(v))
                )
            if 'modalidade_ig' in df_of.columns:
                df_of['macro_modalidade'] = df_of['modalidade_ig'].apply(macro_modalidade)
            if 'ano' in df_of.columns:
                df_of['ano'] = pd.to_numeric(df_of['ano'], errors='coerce')

        except Exception as e:
            st.warning(f"⚠️ Não foi possível ler a aba 'BD_IGs_concedida_analise': {e}")

        return df, df_ag, df_of

    except FileNotFoundError:
        st.error("❌ Arquivo 'base_de_dados_IGs.xlsx' não encontrado.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    except PermissionError:
        st.error("❌ Permissão negada para ler o arquivo 'base_de_dados_IGs.xlsx'.")
        st.warning("**SOLUÇÃO:** feche o arquivo no Microsoft Excel e recarregue esta página.")
        st.info("O Excel bloqueia o arquivo enquanto está aberto, impedindo a leitura pelo dashboard.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    except ValueError as e:
        st.error(f"❌ Erro de valor na planilha: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    except Exception as e:
        st.error(f"❌ Erro inesperado ao carregar os dados: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_territorios():
    cache_file = os.path.join(BASE_DIR, "territorios_ba.json")
    try:
        conteudo = baixar_arquivo_do_github(GITHUB_GEOJSON_URL)
        gdf = gpd.read_file(BytesIO(conteudo))
        try:
            gdf.to_file(cache_file, driver="GeoJSON")
        except Exception:
            pass
        return gdf
    except Exception:
        try:
            if os.path.exists(cache_file):
                return gpd.read_file(cache_file)
        except Exception as e:
            st.error(f"❌ Territórios: {e}")
        return gpd.GeoDataFrame()

df_raw, df_base, df_oficial = carregar_dados()
territorios_ba = carregar_territorios()
COL_TITULO = detectar_coluna_titulo(df_raw.columns) if not df_raw.empty else None

igs_oficiais = df_oficial if not df_oficial.empty else pd.DataFrame()

n_concedidas = 0
if not igs_oficiais.empty and 'status_diagnostico' in igs_oficiais.columns:
    n_concedidas = len(
        igs_oficiais[
            igs_oficiais['status_diagnostico'].astype(str).str.contains('Concedid', na=False, case=False)
        ]
    )

def selecionar_coluna_nome_ti(gdf):
    if gdf.empty:
        return None
    prioridades = ['NM_TI', 'NOME_TI', 'NOME', 'NM_TERRIT', 'TERRITORIO']
    for col in prioridades:
        if col in gdf.columns:
            return col
    for col in gdf.columns:
        serie = gdf[col].dropna()
        if serie.empty:
            continue
        if serie.map(lambda v: isinstance(v, str) and any(ch.isalpha() for ch in v)).any():
            return col
    return None

COLUNA_TI = None
if not territorios_ba.empty:
    COLUNA_TI = selecionar_coluna_nome_ti(territorios_ba)
    if COLUNA_TI:
        territorios_ba = territorios_ba.copy()
        territorios_ba['tooltip_ti'] = territorios_ba[COLUNA_TI].apply(
            lambda nome: formatar_ti(CORRECAO_TERRITORIOS.get(str(nome).strip(), str(nome).strip()))
        )

# -------------------------------------------------
# COBERTURA TERRITORIAL
# -------------------------------------------------
territorios_cobertos = set()
if not df_base.empty:
    for val in df_base['territorio_identidade'].dropna():
        for t in normalizar_territorios(val):
            if t in TERRITORIOS_27:
                territorios_cobertos.add(t)
territorios_sem = [t for t in TERRITORIOS_27 if t not in territorios_cobertos]

# -------------------------------------------------
# CSS
# -------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=Inter:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.block-container{padding-top:1rem !important;padding-bottom:1rem !important;
    padding-left:1.5rem !important;padding-right:1.5rem !important;}
.kpi-card{background:linear-gradient(135deg,#0d1117,#161B22);padding:14px 10px !important;
    border-radius:12px;text-align:center;border-left:4px solid #F2B705;
    box-shadow:0 4px 16px rgba(0,0,0,0.3);height:96px !important;max-height:96px !important;
    overflow:hidden !important;display:flex !important;flex-direction:column;
    justify-content:center;box-sizing:border-box !important;}
.kpi-title{font-size:10px;color:#8B949E;letter-spacing:.06em;text-transform:uppercase;
    margin-bottom:4px;line-height:1.3;}
.kpi-value{font-size:28px;font-weight:700;color:#F2B705;font-family:'Sora',sans-serif;line-height:1.1;}
.kpi-sub{font-size:10px;color:#6E7681;margin-top:3px;line-height:1.3;}
.sec-title{font-family:'Sora',sans-serif;font-size:16px;font-weight:600;
    color:#E6EDF3;margin-bottom:2px;margin-top:8px;}
.tag-ip{background:#1a3a5c;color:#58a6ff;border-radius:5px;padding:2px 7px;font-size:11px;font-weight:600;}
.tag-do{background:#2d3b1e;color:#56d364;border-radius:5px;padding:2px 7px;font-size:11px;font-weight:600;}
.tag-pot{background:#3b2a0e;color:#e3b341;border-radius:5px;padding:2px 7px;font-size:11px;font-weight:600;}
.info-box{background:#161B22;border:1px solid #30363d;border-radius:10px;
    padding:12px 14px;font-size:12px;color:#ccc;line-height:1.6;}
.info-box b{color:#F2B705;}
.estudo-card{background:#0d1117;border:1px solid #30363d;border-radius:8px;
    padding:10px 14px;margin-bottom:6px;}
.estudo-badge{display:inline-block;background:#1f2937;color:#F2B705;border-radius:16px;
    padding:1px 9px;font-size:11px;font-weight:600;margin-bottom:5px;}
.abnt-box{background:#0a0e14;border-left:3px solid #30363d;padding:8px 12px;
    font-size:11px;color:#8B949E;font-style:italic;border-radius:0 6px 6px 0;margin-top:4px;}
.crit-ok{background:#0d2318;border:1px solid #2d3b1e;border-radius:8px;padding:8px 10px;
    font-size:11px;color:#56d364;}
.crit-no{background:#161B22;border:1px solid #30363d;border-radius:8px;padding:8px 10px;
    font-size:11px;color:#6E7681;}
.ig-card-ok{background:#0d1117;border:1px solid #2d3b1e;border-radius:10px;
    padding:12px 16px;margin-bottom:8px;border-left:4px solid #56d364;}
.about-box{background:#161B22;border:1px solid #30363d;border-radius:12px;
    padding:20px 24px;font-size:13px;color:#ccc;line-height:1.7;}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# SIDEBAR
# -------------------------------------------------
with st.sidebar:
    st.markdown("## 🔎 Filtros")
    df_filtrado = pd.DataFrame()

    if not df_base.empty:
        tis_individuais = set()
        for v in df_base['territorio_identidade'].dropna():
            for t in normalizar_territorios(v):
                tis_individuais.add(t)
        lista_ti = sorted(tis_individuais, key=lambda t: (NUMERACAO_TI.get(t, 99), t))
        display_to_original = {formatar_ti(t): t for t in lista_ti}
        opcoes_display = ["Todos"] + list(display_to_original.keys())

        ti_sel_display = st.selectbox("Território de Identidade", opcoes_display)
        ti_sel = "Todos" if ti_sel_display == "Todos" else display_to_original[ti_sel_display]

        lista_macro = sorted(df_base['macro_tipo'].dropna().unique().tolist())
        macro_sel   = st.multiselect("Categoria", lista_macro, default=lista_macro)

        lista_modal = sorted(df_base['macro_modalidade'].dropna().unique().tolist())
        modal_sel   = st.multiselect("Modalidade", lista_modal, default=lista_modal)

        max_est = int(df_base['n_estudos'].max()) if not df_base.empty else 1
        min_est = st.slider("Nº mínimo de estudos (0 = todos)", 0, max_est, 0) if max_est > 0 else 0

        busca = st.text_input("🔍 Buscar por nome ou município")

        df_filtrado = df_base.copy()
        if ti_sel != "Todos":
            df_filtrado = df_filtrado[
                df_filtrado['territorio_identidade'].apply(lambda x: ti_sel in normalizar_territorios(x))
            ]
        if macro_sel:
            df_filtrado = df_filtrado[df_filtrado['macro_tipo'].isin(macro_sel)]
        if modal_sel:
            df_filtrado = df_filtrado[df_filtrado['macro_modalidade'].isin(modal_sel)]
        if min_est > 0:
            df_filtrado = df_filtrado[df_filtrado['n_estudos'] >= min_est]
        if busca:
            df_filtrado = df_filtrado[
                df_filtrado['nome_produto'].astype(str).str.contains(busca, case=False, na=False) |
                df_filtrado['municipios_abrangidos'].astype(str).str.contains(busca, case=False, na=False)
            ]

        st.divider()
        t_est = int(df_filtrado['n_estudos'].sum()) if not df_filtrado.empty else 0
        st.caption(f"**{len(df_filtrado)}** ativos · **{t_est}** estudos (soma por ativo)")

        if st.button("🗑️ Limpar filtros"):
            st.session_state.clear()
            st.rerun()

# -------------------------------------------------
# CABEÇALHO
# -------------------------------------------------
st.markdown("""
<div style='margin-bottom:4px;'>
  <span style='font-family:Sora,sans-serif;font-size:22px;font-weight:700;color:#E6EDF3;'>
    🛡️ Diagnóstico de Indicações Geográficas na Bahia
  </span><br>
  <span style='color:#8B949E;font-size:12px;'>
    Mapeamento de potenciais IGs nos 27 Territórios de Identidade &nbsp;·&nbsp; PROFNIT / UFRB 2026
  </span>
</div>
""", unsafe_allow_html=True)
st.divider()

# -------------------------------------------------
# KPIs
# -------------------------------------------------
soma_estudos_por_ativo = int(df_base['n_estudos'].sum()) if not df_base.empty else 0

if COL_TITULO is not None and not df_raw.empty and df_raw['titulo_norm'].notna().any():
    total_estudos = int(df_raw['titulo_norm'].nunique())
else:
    total_estudos = soma_estudos_por_ativo

n_multi_estudos = len(df_base[df_base['n_estudos'] > 1]) if not df_base.empty else 0
n_ti_coberto = len(territorios_cobertos)
cobertura_pct = round(n_ti_coberto / 27 * 100)

if not df_base.empty:
    mask_ja_oficial_no_base = df_base['status_diagnostico'].astype(str).str.contains(
        r'Concedid|em\s+an[aá]lise', na=False, case=False, regex=True
    )
    df_potenciais = df_base[~mask_ja_oficial_no_base]
else:
    df_potenciais = pd.DataFrame()

n_potenciais = len(df_potenciais)
n_ip_pot = len(df_potenciais[df_potenciais['macro_modalidade'] == 'IP']) if not df_potenciais.empty else 0
n_do_pot = len(df_potenciais[df_potenciais['macro_modalidade'] == 'DO']) if not df_potenciais.empty else 0

n_notoriedade = (
    len(df_potenciais[df_potenciais['status_diagnostico'].astype(str).str.contains(
        'notoriedade', na=False, case=False
    )]) if not df_potenciais.empty else 0
)
pct_notoriedade = round(n_notoriedade / n_potenciais * 100) if n_potenciais > 0 else 0

top3_estudos = (
    df_base.nlargest(3, 'n_estudos')[['nome_produto', 'n_estudos']].values.tolist()
    if not df_base.empty else []
)

st.markdown("##### Panorama Geral do Mapeamento")
k1, k2, k3, k4 = st.columns(4)
kpis_row1 = [
    (k1, "Potenciais Identificados", n_potenciais, "mapeados neste TCC"),
    (k2, "Potenciais com Notoriedade", n_notoriedade, f"{pct_notoriedade}% dos potenciais"),
    (k3, "Estudos Referenciados", total_estudos, f"trabalhos distintos · {n_multi_estudos} ativos com múltiplos estudos"),
    (k4, "Cobertura Territorial", f"{n_ti_coberto}/27", f"{cobertura_pct}% dos territórios"),
]
for col, titulo, valor, sub in kpis_row1:
    with col:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">{titulo}</div>
                <div class="kpi-value">{valor}</div>
                <div class="kpi-sub">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

k5, k6, k7, k8 = st.columns(4)
pct_ip_pot = round(n_ip_pot / n_potenciais * 100) if n_potenciais > 0 else 0
pct_do_pot = round(n_do_pot / n_potenciais * 100) if n_potenciais > 0 else 0

for col, titulo, valor, sub in [
    (k5, "Potenciais para IP", n_ip_pot, f"{pct_ip_pot}% dos potenciais"),
    (k6, "Potenciais para DO", n_do_pot, f"{pct_do_pot}% dos potenciais"),
    (k7, "IGs Concedidas", n_concedidas, "registradas no INPI"),
]:
    with col:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">{titulo}</div>
                <div class="kpi-value">{valor}</div>
                <div class="kpi-sub">{sub}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

with k8:
    linhas_top3 = ""
    for i, (nome, qtd) in enumerate(top3_estudos, start=1):
        nome_curto = nome if len(nome) <= 20 else nome[:18] + "…"
        linhas_top3 += (
            f"<div style='display:flex;justify-content:space-between;"
            f"align-items:center;font-size:10px;margin-top:2px;line-height:1.2;' title='{esc(nome)}'>"
            f"<span style='color:#ccc'>{i}º · {esc(nome_curto)}</span>"
            f"<span style='color:#F2B705;font-weight:600;flex-shrink:0;margin-left:6px;'>{int(qtd)}</span></div>"
        )
    if not linhas_top3:
        linhas_top3 = "<div style='font-size:10px;color:#6E7681;margin-top:2px;'>Sem dados</div>"

    st.markdown(
        f"""
        <div class="kpi-card" style="text-align:left;">
            <div class="kpi-title" style="text-align:center;margin-bottom:0;font-size:9.5px;">Top 3 IGs com Mais Estudos</div>
            {linhas_top3}
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------
# AUDITORIA
# -------------------------------------------------
if MOSTRAR_AUDITORIA and not df_raw.empty:
    with st.expander("🧪 Auditoria de estudos (temporário)"):
        if COL_TITULO is None:
            st.error(f"Coluna de título não encontrada. Colunas disponíveis: {list(df_raw.columns)}")
        else:
            aud = df_raw.copy()
            n_linhas = len(aud)
            n_sem_titulo = int(aud['titulo_norm'].isna().sum())
            n_distintos = int(aud['titulo_norm'].nunique())

            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Linhas na planilha", n_linhas)
            a2.metric("Linhas sem título", n_sem_titulo)
            a3.metric("Títulos distintos (global)", n_distintos)
            a4.metric("Soma de n_estudos por ativo", soma_estudos_por_ativo)

            por_ativo = (
                aud.dropna(subset=['titulo_norm'])
                .groupby('chave_agrupamento')['titulo_norm'].nunique()
                .rename('titulos_distintos')
            )
            linhas_ativo = aud.groupby('chave_agrupamento').size().rename('linhas')

            comp = (
                df_base.set_index('chave')[['nome_produto', 'n_estudos']]
                .join(linhas_ativo, how='left')
                .join(por_ativo, how='left')
            )
            comp['titulos_distintos'] = comp['titulos_distintos'].fillna(0).astype(int)
            comp['diverge'] = comp['n_estudos'] != comp['titulos_distintos']

            st.markdown("**Por ativo** (`diverge = True` indica contagem atual diferente da contagem por título)")
            st.dataframe(comp.sort_values('diverge', ascending=False), use_container_width=True, hide_index=True)

            dup = (
                aud.dropna(subset=['titulo_norm'])
                .groupby('titulo_norm')['chave_agrupamento'].nunique()
            )
            titulos_multi = dup[dup > 1]
            st.write("Títulos que aparecem em mais de um ativo:", int(len(titulos_multi)))
            if len(titulos_multi) > 0:
                st.dataframe(titulos_multi.rename('n_ativos').reset_index(), use_container_width=True, hide_index=True)

            sem_titulo_df = aud[aud['titulo_norm'].isna()][['nome_produto']]
            if not sem_titulo_df.empty:
                st.markdown("**Linhas sem título (podem ser perdidas ou mal contadas):**")
                st.dataframe(sem_titulo_df, use_container_width=True, hide_index=True)

st.divider()

# -------------------------------------------------
# ABAS
# -------------------------------------------------
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "🗺️ Mapa Territorial",
    "📊 Análise",
    "📋 Fichas dos Ativos",
    "🏅 IGs Registradas",
    "ℹ️ Sobre o Projeto"
])

COR_MARCADOR = {
    'Agroalimentar':'green','Artesanato':'purple','Bebidas':'blue',
    'Agrícola':'cadetblue','Serviços':'pink','Outros':'gray',
    'IG Registrada':'darkgreen'
}
HEX_LEGENDA = {
    'Agroalimentar':'#72b026','Artesanato':'#d252b9','Bebidas':'#38aadd',
    'Agrícola':'#436978','Serviços':'#ff8e7f'
}
CORES_GRAFICO = {
    'Agroalimentar':'#28a745','Artesanato':'#9c27b0','Bebidas':'#2C7BE5',
    'Agrícola':'#F2B705','Serviços':'#e83e8c','Outros':'#6c757d',
    'IG Registrada':'#56d364'
}

# =================================================
# ABA 1: MAPA
# =================================================
with aba1:
    st.markdown('<div class="sec-title">📍 Distribuição Espacial dos Ativos</div>', unsafe_allow_html=True)
    st.caption("🟡 Territórios com ativos filtrados (intensidade = quantidade)")

    mapa = folium.Map(location=[-12.5,-41.5], zoom_start=6, tiles="cartodbpositron")

    ti_com = set()
    cont_ti = {}
    if not df_filtrado.empty:
        for _, row in df_filtrado.iterrows():
            for t in normalizar_territorios(row['territorio_identidade']):
                ti_com.add(t)
                cont_ti[t] = cont_ti.get(t, 0) + 1

    def estilo_ti(feat):
        esta, qtd = False, 0
        if COLUNA_TI and feat.get('properties'):
            nm = str(feat['properties'].get(COLUNA_TI,'')).split('(')[0].split('/')[0].strip()
            for t in normalizar_territorios(nm):
                if t in ti_com:
                    esta = True
                    qtd  = max(qtd, cont_ti.get(t, 0))
        if esta:
            return {"fillColor":"#F2B705","color":"#F2B705","weight":2,
                    "fillOpacity":min(0.25+qtd*0.08,0.85)}
        return {"fillColor":"#2C7BE5","color":"#cccccc","weight":0.5,"fillOpacity":0.07}

    if not territorios_ba.empty and COLUNA_TI:
        folium.GeoJson(
            territorios_ba,
            style_function=estilo_ti,
            tooltip=folium.GeoJsonTooltip(fields=['tooltip_ti'], aliases=["Território:"], sticky=True)
        ).add_to(mapa)

    n_marcadores_erro = 0
    if not df_filtrado.empty:
        for _, row in df_filtrado[df_filtrado['latitude'].notna() & df_filtrado['longitude'].notna()].iterrows():
            try:
                if row['macro_tipo'] == 'IG Registrada':
                    tooltip_ig = f"⭐ {row['nome_produto']}"
                    ano_txt = f"Concedida em: <b>{esc(row['ano'])}</b>" if pd.notna(row.get('ano')) else ''
                    popup_ig = f"""
                    <div style='font-family:sans-serif;min-width:210px'>
                        <b>{esc(tooltip_ig)}</b><br>
                        <b style='color:#28a745'>{esc(row['status_diagnostico'])}</b><br>
                        Modalidade: <b>{esc(row['macro_modalidade'])}</b><br>
                        {ano_txt}
                    </div>
                    """
                    folium.Marker(
                        location=[row['latitude'], row['longitude']],
                        popup=folium.Popup(popup_ig, max_width=260),
                        tooltip=tooltip_ig,
                        icon=folium.Icon(color='darkgreen', icon='star', prefix='glyphicon')
                    ).add_to(mapa)
                else:
                    n = int(row.get('n_estudos', 1))
                    cor = 'red' if n >= 3 else ('orange' if n == 2 else COR_MARCADOR.get(row['macro_tipo'], 'gray'))
                    popup = f"""
                    <div style='font-family:sans-serif;min-width:240px;max-width:320px'>
                        <b style='font-size:13px;color:#333'>{esc(row['nome_produto'])}</b><br>
                        <span style='color:#777;font-size:11px'>📍 {esc(row['municipios_abrangidos'])}</span><br>
                        <hr style='margin:6px 0;border-color:#eee'>
                        <b>Modalidade:</b> {esc(row['macro_modalidade'])} &nbsp; <b>Categoria:</b> {esc(row['macro_tipo'])}<br>
                    </div>
                    """
                    folium.Marker(
                        location=[row['latitude'], row['longitude']],
                        popup=folium.Popup(popup, max_width=340),
                        tooltip=f"📌 {row['nome_produto']} · {row['macro_tipo']} · {n} {'estudos' if n > 1 else 'estudo'}",
                        icon=folium.Icon(color=cor, icon='leaf', prefix='glyphicon')
                    ).add_to(mapa)
            except Exception:
                n_marcadores_erro += 1
                continue

    st_folium(mapa, use_container_width=True, height=560)
    if n_marcadores_erro:
        st.caption(f"⚠️ {n_marcadores_erro} marcador(es) não puderam ser desenhados por erro nos dados.")

    def _bolinha(cor):
        return (
            f"<span style='display:inline-block;width:10px;height:10px;border-radius:50%;"
            f"background:{cor};margin-right:4px;'></span>"
        )

    st.markdown(
        f"""
        <div style='display:flex;gap:20px;flex-wrap:wrap;padding:8px 0;
        font-size:12px;color:#8B949E;border-top:1px solid #30363d;margin-top:4px;align-items:center;'>
            <span>{_bolinha(HEX_LEGENDA['Agroalimentar'])}Agroalimentar</span>
            <span>{_bolinha(HEX_LEGENDA['Artesanato'])}Artesanato</span>
            <span>{_bolinha(HEX_LEGENDA['Bebidas'])}Bebidas</span>
            <span>{_bolinha(HEX_LEGENDA['Agrícola'])}Agrícola</span>
            <span>{_bolinha(HEX_LEGENDA['Serviços'])}Serviços</span>
            <span>{_bolinha('#f69730')}Notoriedade moderada (2 estudos)</span>
            <span>{_bolinha('#d33d29')}Alta notoriedade (3+ estudos)</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    if not df_filtrado.empty:
        gc2, gc3 = st.columns(2)
        with gc2:
            st.markdown("**Distribuição por Categoria**")
            cc = df_filtrado['macro_tipo'].value_counts().reset_index()
            cc.columns = ['Cat','Qtd']
            fig_c = px.pie(
                cc, names='Cat', values='Qtd', hole=0.45,
                color='Cat', template='plotly_dark',
                color_discrete_map=CORES_GRAFICO
            )
            fig_c.update_layout(
                height=300,
                margin=dict(l=0,r=0,t=5,b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation='h', y=-0.1, font=dict(size=10))
            )
            st.plotly_chart(fig_c, use_container_width=True)

        with gc3:
            st.markdown("**Modalidade de Proteção**")
            mc = df_filtrado['macro_modalidade'].value_counts().reset_index()
            mc.columns = ['Modalidade','Qtd']
            total_mc = mc['Qtd'].sum()
            mc['texto'] = mc.apply(lambda r: f"{r['Qtd']} ({round(r['Qtd']/total_mc*100)}%)", axis=1)
            fig_m = px.bar(
                mc, x='Modalidade', y='Qtd', color='Modalidade',
                text='texto', template='plotly_dark',
                color_discrete_map={'IP':'#58a6ff','DO':'#56d364','Potencial':'#e3b341'}
            )
            fig_m.update_traces(textposition='outside')
            fig_m.update_layout(
                height=300,
                margin=dict(l=0,r=0,t=5,b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
                xaxis_title='',
                yaxis_title='Qtd',
                font=dict(size=11)
            )
            st.plotly_chart(fig_m, use_container_width=True)

# =================================================
# ABA 2: ANÁLISE
# =================================================
with aba2:
    st.markdown('<div class="sec-title">📊 Análise dos Dados</div>', unsafe_allow_html=True)
    st.divider()

    if not df_filtrado.empty:
        st.markdown("**Notoriedade: top 15 ativos por nº de estudos**")
        top_n = (
            df_filtrado.nlargest(15,'n_estudos')[['nome_produto','n_estudos','macro_tipo']]
            .sort_values('n_estudos',ascending=False)
        )
        top_n['label'] = top_n['nome_produto'].apply(lambda x: x[:38]+'…' if len(x)>38 else x)
        fig_n = px.bar(
            top_n,
            x='n_estudos',
            y='label',
            orientation='h',
            color='macro_tipo',
            text='n_estudos',
            category_orders={'label': top_n['label'].tolist()},
            color_discrete_map=CORES_GRAFICO,
            labels={'label':'','n_estudos':'Nº estudos','macro_tipo':'Categoria'},
            template='plotly_dark'
        )
        fig_n.update_traces(textposition='outside')
        fig_n.update_layout(
            height=420,
            margin=dict(l=0,r=0,t=5,b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            legend=dict(orientation='h', y=-0.12, font=dict(size=10)),
            xaxis_title='Nº de estudos',
            font=dict(size=10)
        )
        st.plotly_chart(fig_n, use_container_width=True)

        st.divider()

        anos_estudos = [
            e['ano'] for est in df_filtrado['estudos']
            if isinstance(est, list)
            for e in est if e.get('ano')
        ]
        if anos_estudos:
            st.markdown("**Estudos por Ano de Publicação**")
            cont_anos = Counter(anos_estudos)
            ac = (
                pd.DataFrame({'ano': list(cont_anos.keys()), 'Qtd': list(cont_anos.values())})
                .sort_values('ano')
            )
            ac['ano'] = ac['ano'].astype(int).astype(str)
            fig_a = px.area(
                ac,
                x='ano',
                y='Qtd',
                markers=True,
                template='plotly_dark',
                color_discrete_sequence=['#F2B705']
            )
            fig_a.update_traces(line_width=2.5, marker_size=8, fillcolor='rgba(242,183,5,0.15)')
            fig_a.update_layout(
                height=200,
                margin=dict(l=0,r=0,t=5,b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis_title='',
                yaxis_title='Estudos',
                font=dict(size=10)
            )
            st.plotly_chart(fig_a, use_container_width=True)
            st.caption("Contagem por estudo. Um estudo referenciado em mais de um ativo é contado em cada um.")

            st.divider()

        st.markdown("**Cobertura dos 27 Territórios**")
        cob = pd.DataFrame({
            'Território': TERRITORIOS_27,
            'Label': [formatar_ti(t) for t in TERRITORIOS_27],
            'Status': [
                '✅ Mapeado' if t in territorios_cobertos else '⚠️ Sem ativo'
                for t in TERRITORIOS_27
            ],
            'Ativos': [
                sum(
                    1 for _, row in df_filtrado.iterrows()
                    if t in normalizar_territorios(row['territorio_identidade'])
                )
                for t in TERRITORIOS_27
            ]
        })
        cob_ordenado = cob.sort_values('Ativos', ascending=False)
        fig_cob = px.bar(
            cob_ordenado,
            x='Ativos',
            y='Label',
            orientation='h',
            color='Status',
            text='Ativos',
            category_orders={'Label': cob_ordenado['Label'].tolist()},
            color_discrete_map={'✅ Mapeado':'#F2B705','⚠️ Sem ativo':'#30363d'},
            template='plotly_dark'
        )
        fig_cob.update_layout(
            height=650,
            margin=dict(l=0,r=0,t=5,b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=True,
            xaxis_title='Nº de ativos',
            legend=dict(orientation='h', y=-0.08),
            font=dict(size=9)
        )
        st.plotly_chart(fig_cob, use_container_width=True)

# =================================================
# ABA 3: FICHAS
# =================================================
with aba3:
    st.markdown('<div class="sec-title">📋 Fichas dos Ativos</div>', unsafe_allow_html=True)
    st.caption("Critérios do INPI · Tradição histórica · Vínculo territorial · Referências ABNT")
    st.divider()

    if not df_filtrado.empty:
        col_ord, col_pag_placeholder = st.columns([3, 1])
        with col_ord:
            ordem = st.selectbox(
                "Ordenar por",
                ["Notoriedade (mais estudos primeiro)", "Nome", "Território"]
            )

        if ordem == "Território":
            st.caption("Clique em um território para expandir e ver os ativos. Produtos com mais de um território aparecem em cada um deles.")
            territorios_unicos = sorted(territorios_cobertos, key=lambda ti: NUMERACAO_TI.get(ti, 99))

            for ti in territorios_unicos:
                mask_ti = df_filtrado['territorio_identidade'].apply(
                    lambda val: ti in normalizar_territorios(val)
                )
                df_ti = df_filtrado[mask_ti].sort_values('nome_produto')
                contagem = len(df_ti)
                if contagem == 0:
                    continue
                label_expander = f"{formatar_ti(ti)} ({contagem} {'ativo' if contagem == 1 else 'ativos'})"

                with st.expander(label_expander):
                    for _, row in df_ti.iterrows():
                        n = int(row.get('n_estudos', 1))
                        badge = "🔴 Alta notoriedade" if n >= 3 else "🟡 Moderada" if n == 2 else "⚪ 1 estudo"
                        with st.expander(f"📌 {row['nome_produto']} · {badge}"):
                            exibir_conteudo_ficha(row, show_criteria=False)

        else:
            df_ord = (
                df_filtrado.sort_values('n_estudos', ascending=False)
                if "Notoriedade" in ordem else
                df_filtrado.sort_values('nome_produto')
            )

            total = len(df_ord)
            por_pag = 8
            n_pag = max(1, -(-total // por_pag)) if total > 0 else 1
            pag = 1
            with col_pag_placeholder:
                if n_pag > 1:
                    pag = st.number_input(f"Página (1 a {n_pag})", min_value=1, max_value=n_pag, value=1, step=1)

            inicio = (pag - 1) * por_pag
            st.caption(f"Mostrando {inicio+1} a {min(inicio+por_pag,total)} de {total} ativos")

            for _, row in df_ord.iloc[inicio:inicio + por_pag].iterrows():
                n = int(row.get('n_estudos', 1))
                badge = "🔴 Alta notoriedade" if n >= 3 else "🟡 Moderada" if n == 2 else "⚪ 1 estudo"
                tis_str = formatar_territorios_str(row['territorio_identidade'])

                with st.expander(f"📌 {row['nome_produto']}  ·  {tis_str}  ·  {badge}"):
                    exibir_conteudo_ficha(row, show_criteria=True)

    st.divider()
    with st.expander("🗂️ Base de Dados Completa + Download CSV"):
        if not df_filtrado.empty:
            cols_e = [
                'nome_produto','territorio_identidade','municipios_abrangidos',
                'macro_tipo','macro_modalidade','n_estudos',
                'viabilidade_economica','status_diagnostico'
            ]
            cols_e = [c for c in cols_e if c in df_filtrado.columns]
            st.dataframe(df_filtrado[cols_e], use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Baixar dados filtrados (.csv)",
                data=df_filtrado[cols_e].to_csv(index=False).encode('utf-8'),
                file_name="igs_bahia_filtrado.csv",
                mime="text/csv"
            )

# =================================================
# ABA 4: IGs REGISTRADAS
# =================================================
with aba4:
    st.markdown('<div class="sec-title">🏅 IGs Registradas na Bahia (INPI)</div>', unsafe_allow_html=True)
    st.caption("Fonte: INPI, Instituto Nacional da Propriedade Industrial (2025)")
    st.divider()

    if not igs_oficiais.empty and 'status_diagnostico' in igs_oficiais.columns:
        concedidas = igs_oficiais[
            igs_oficiais['status_diagnostico'].astype(str).str.contains('Concedid', case=False, na=False)
        ].sort_values('nome_produto')
    else:
        concedidas = pd.DataFrame()

    st.markdown(f"### ✅ Concedidas ({len(concedidas)})")
    col_c1, col_c2 = st.columns(2)

    for i, (_, ig) in enumerate(concedidas.iterrows()):
        col_atual = col_c1 if i % 2 == 0 else col_c2
        with col_atual:
            tag_m = (
                '<span class="tag-do">DO</span>'
                if ig.get('macro_modalidade') == 'DO'
                else '<span class="tag-ip">IP</span>'
            )
            territorio_fmt = formatar_territorios_str(ig.get('territorio_identidade'))
            ano_str = f"Concedida em {int(ig['ano'])}" if pd.notna(ig.get('ano')) else 'Concedida'

            st.markdown(
                f"""
                <div class="ig-card-ok">
                    <b style='color:#E6EDF3;font-size:13px'>{esc(ig['nome_produto'])}</b><br>
                    {tag_m} &nbsp;<span style='color:#6E7681;font-size:12px'>{ano_str}</span><br>
                    <span style='color:#8B949E;font-size:12px'>📍 {esc(territorio_fmt)}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.divider()
    total_pot = n_potenciais
    st.markdown("**Contexto: registradas × potenciais mapeados por este TCC**")

    fig_ctx = go.Figure(go.Bar(
        x=['IGs Concedidas', 'Potenciais Mapeados (TCC)'],
        y=[len(concedidas), total_pot],
        marker_color=['#56d364', '#F2B705'],
        text=[len(concedidas), total_pot],
        textposition='outside',
        width=[0.4, 0.4]
    ))

    if len(concedidas) > 0:
        razao = total_pot / len(concedidas)
        razao_str = f"{razao:.1f}".rstrip('0').rstrip('.') if razao % 1 else f"{razao:.0f}"
        texto_razao = (
            f"Este TCC identificou um potencial ~{razao_str}x "
            f"maior que as IGs já concedidas na Bahia"
        )
    else:
        texto_razao = (
            "Este TCC identificou um número expressivo de potenciais "
            "ativos ainda não certificados na Bahia"
        )

    fig_ctx.update_layout(
        template='plotly_dark',
        height=280,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=20, b=40),
        yaxis_title='Quantidade',
        showlegend=False,
        annotations=[dict(
            text=texto_razao,
            xref="paper",
            yref="paper",
            x=0.5,
            y=-0.22,
            showarrow=False,
            font=dict(size=11, color='#8B949E')
        )]
    )
    st.plotly_chart(fig_ctx, use_container_width=True)

# =================================================
# ABA 5: SOBRE
# =================================================
with aba5:
    st.markdown('<div class="sec-title">ℹ️ Sobre o Projeto</div>', unsafe_allow_html=True)
    st.divider()

    cs1, cs2 = st.columns([3,2])
    with cs1:
        st.markdown(
            """
            <div class="about-box">
                <b style='color:#F2B705;font-size:15px'>Mapeamento de Potenciais Indicações Geográficas
                por Território de Identidade no Estado da Bahia</b><br><br>
                Trabalho de Conclusão de Curso do <b>PROFNIT (Programa de Pós-Graduação em
                Propriedade Intelectual e Transferência de Tecnologia para Inovação)</b>,
                pelo ponto focal da <b>UFRB (Universidade Federal do Recôncavo da Bahia)</b>.<br><br>
                <b>Objetivo:</b> Identificar, catalogar e analisar produtos e serviços com
                características territoriais distintivas, passíveis de proteção como IGs nos 27
                Territórios de Identidade baianos, por meio de banco de dados georreferenciado
                e plataforma digital interativa.<br><br>
                <b>Metodologia:</b> Revisão sistemática e pesquisa documental, com critérios de
                seleção baseados nos 4 pilares exigidos pelo INPI: singularidade, tradição
                histórica, vínculo territorial e viabilidade econômica.<br><br>
                <b>Produto tecnológico:</b> Dashboard desenvolvido em Python (Streamlit), ferramenta
                inédita de inteligência territorial para a gestão da PI no estado da Bahia.
            </div>
            """,
            unsafe_allow_html=True
        )
    with cs2:
        st.markdown(
            """
            <div class="about-box">
                <b style='color:#F2B705'>Informações Acadêmicas</b><br><br>
                👤 <b>Discente:</b> Vinícius de Jesus Almeida Lima<br>
                🎓 <b>Orientador:</b> Dr. Luís Oscar Silva Martins<br>
                🏛️ <b>Instituição:</b> UFRB / PROFNIT<br>
                📅 <b>Período:</b> 2025 a 2026<br>
                🔗 <b>Projeto Integrador:</b> IGs e Marcas Coletivas e Inovação Associada
                ao Desenvolvimento Sustentável<br><br>
                <b style='color:#F2B705'>Critérios de Seleção (INPI)</b><br><br>
                ⭐ Singularidade do produto<br>
                📜 Tradição histórica e cultural<br>
                📍 Vínculo territorial<br>
                💼 Viabilidade econômica<br><br>
                <b style='color:#F2B705'>Tecnologias</b><br><br>
                🐍 Python · Streamlit · Folium<br>
                📊 Plotly · GeoPandas · Pandas<br>
                ☁️ Streamlit Community Cloud
            </div>
            """,
            unsafe_allow_html=True
        )

    st.divider()
    st.markdown(
        """
        <div style='background:#161B22;border-radius:10px;padding:14px 18px;
        border-left:4px solid #F2B705;font-size:12px;color:#ccc;'>
            <b style='color:#F2B705'>📋 Como citar este produto tecnológico</b><br><br>
            LIMA, Vinícius de Jesus Almeida.
            <i><b>Prospecção de indicações geográficas na Bahia:</b> mapeamento por Territórios de Identidade.</i>
            Dashboard, produto tecnológico do Trabalho de Conclusão de Curso. PROFNIT/UFRB. Feira de Santana, 2026.
        </div>
        """,
        unsafe_allow_html=True
    )

# -------------------------------------------------
# RODAPÉ
# -------------------------------------------------
st.divider()
st.markdown(
    """
    <div style='text-align:center;color:#6E7681;font-size:11px;'>
        Projeto acadêmico <b>PROFNIT</b>: Diagnóstico Territorial de IGs | Bahia &nbsp;·&nbsp;
        Desenvolvido por: <b>Vinícius de Jesus Almeida Lima</b> · 2026
    </div>
    """,
    unsafe_allow_html=True
)
