# Documentação Técnica da Dashboard de Indicações Geográficas da Bahia

## 1. Visão geral

Este documento descreve, passo a passo, a construção, alimentação, publicação e manutenção da dashboard de potenciais Indicações Geográficas (IGs) da Bahia.

A aplicação foi desenvolvida com:

- Python
- Streamlit
- Pandas
- GeoPandas
- Folium
- Plotly
- PostgreSQL
- Supabase
- Streamlit Community Cloud

A dashboard apresenta os ativos mapeados, estudos únicos trabalhados, critérios de análise, distribuição territorial, modalidades de proteção e IGs concedidas.

## 2. Arquitetura do projeto

O sistema possui quatro camadas principais:

```text
Planilha Excel
      |
      | carga inicial ou atualização controlada
      v
PostgreSQL hospedado no Supabase
      |
      | conexão por DATABASE_URL
      v
Aplicação Streamlit
      |
      v
Link público da dashboard
```

O Excel é utilizado como fonte de migração ou atualização dos dados. Em produção, a dashboard não lê diretamente o Excel: ela consulta as tabelas PostgreSQL.

## 3. Estrutura de arquivos

### `app_mapa_bahia.py`

Arquivo principal da aplicação Streamlit. Responsável por:

- conectar ao PostgreSQL;
- consultar as tabelas operacionais;
- normalizar os dados;
- agrupar ativos;
- deduplicar estudos;
- calcular indicadores;
- gerar filtros, mapas, gráficos e fichas;
- exibir as IGs concedidas.

### `schema.sql`

Define as tabelas, os índices e o histórico de cargas do PostgreSQL.

### `importar_excel_postgres.py`

Script responsável pela carga do Excel para o banco PostgreSQL.

### `requirements.txt`

Lista as dependências Python necessárias para executar a aplicação.

### `territorios_ba.json`

Camada geográfica dos Territórios de Identidade da Bahia usada no mapa.

### `README_POSTGRES.md`

Guia resumido de instalação e operação do banco.

## 4. Fonte original dos dados

A planilha original contém quatro abas:

1. `BD_IGs_mapeadas`: base principal de ativos e estudos.
2. `legenda_dados`: descrição das colunas.
3. `legenda_buscas`: strings e justificativas das buscas.
4. `BD_IGs_concedida_analise`: base de IGs concedidas ou em análise.

Somente as abas `BD_IGs_mapeadas` e `BD_IGs_concedida_analise` são carregadas para as tabelas operacionais do PostgreSQL.

## 5. Criação do banco PostgreSQL

O banco pode ser local ou hospedado. Para a publicação online, foi utilizado o Supabase, que fornece um PostgreSQL acessível pela internet.

No Supabase:

1. Criar um projeto.
2. Definir a senha do banco.
3. Acessar **Connect**.
4. Selecionar **Session pooler** ou outra conexão compatível com a infraestrutura.
5. Copiar a URI PostgreSQL.

A URI possui formato semelhante a:

```text
postgresql://usuario:senha@servidor:5432/banco
```

Para uso com SQLAlchemy e Psycopg, o prefixo utilizado pela aplicação é:

```text
postgresql+psycopg://usuario:senha@servidor:5432/banco?sslmode=require
```

Caracteres especiais da senha, como `@`, `#`, `/` e espaços, devem ser codificados em formato URL.

Exemplo: `@` deve ser representado por `%40`.

## 6. Configuração local

Instalar as dependências:

```powershell
cd "C:\Users\User\OneDrive\Área de Trabalho\MESTRADO\Produto\DASHBOARD\teste"
py -m pip install -r requirements.txt
```

Definir a conexão do banco na sessão atual do PowerShell:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://usuario:senha@servidor:5432/banco?sslmode=require"
```

A variável existe somente na janela atual do PowerShell. Se uma nova janela for aberta, ela deverá ser configurada novamente.

## 7. Modelo relacional

### Tabela `estudos_igs`

Armazena as linhas da base principal, incluindo informações do ativo, localização, critérios, referências e estudos.

Principais campos:

- `id`: identificador interno.
- `origem_id`: identificador original da planilha.
- `nome_produto`: nome do ativo ou produto.
- `territorio_identidade`: território associado.
- `municipios_abrangidos`: municípios relacionados.
- `tipo_produto`: categoria original.
- `modalidade_ig`: modalidade informada.
- `geometria_espacial`: coordenadas armazenadas como texto.
- `titulo_trabalho`: título do estudo.
- `link`: link do estudo.
- `ano`: ano de publicação.
- `referencia_abnt`: referência bibliográfica.
- `status_diagnostico`: situação do ativo.
- `estudo_key`: chave normalizada do estudo.
- `chave_agrupamento`: chave normalizada do produto.

### Tabela `igs_concedidas`

Armazena as IGs concedidas ou analisadas na aba oficial da base.

### Tabela `carga_dados`

Registra cada importação realizada, incluindo:

- nome do arquivo de origem;
- data e hora da carga;
- quantidade de linhas de estudos;
- quantidade de linhas de IGs concedidas.

## 8. Criação das tabelas

O arquivo `schema.sql` pode ser executado no PostgreSQL ou é executado automaticamente pelo script de importação.

Exemplo usando `psql`:

```powershell
psql "$env:DATABASE_URL" -f schema.sql
```

Caso o comando `psql` não esteja no PATH, utilize o caminho completo do executável PostgreSQL.

## 9. Alimentação do banco

A carga inicial é feita com:

```powershell
py importar_excel_postgres.py base_de_dados_IGs.xlsx
```

O processo realiza as seguintes etapas:

1. abre as abas operacionais do Excel;
2. remove linhas sem nome de produto;
3. converte os anos para números inteiros;
4. cria a chave normalizada do estudo;
5. cria a chave normalizada do produto;
6. cria as tabelas caso ainda não existam;
7. limpa as tabelas operacionais;
8. insere os dados atualizados;
9. registra a operação em `carga_dados`.

A carga atual é do tipo substituição completa. Portanto, o banco é recarregado com a versão integral da planilha a cada execução.

## 10. Chave de estudo e deduplicação

O mesmo estudo pode aparecer em várias linhas porque um ativo pode estar associado a mais de um registro ou território. Para evitar contagem duplicada, a aplicação cria uma chave baseada em:

```text
título do trabalho + link + referência ABNT
```

Na aplicação, essa chave é normalizada para minúsculas e armazenada no campo `estudo_key`.

A métrica exibida como **Estudos Únicos Trabalhados** utiliza a quantidade de valores únicos dessa chave.

A soma das linhas brutas não deve ser usada como total de estudos únicos, pois pode inflar o resultado.

## 11. Chave de agrupamento dos ativos

Os ativos são agrupados pela coluna `chave_agrupamento`.

Essa chave remove o trecho entre parênteses do nome do produto e espaços excedentes. Isso permite tratar pequenas variações de escrita como o mesmo ativo.

O nome final exibido na interface pode receber o município para melhorar a identificação visual, mas a chave interna permanece estável.

## 12. Conexão da aplicação ao PostgreSQL

No arquivo `app_mapa_bahia.py`, a conexão é obtida pela variável `DATABASE_URL`:

```python
@st.cache_resource
def obter_conexao_postgres():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        database_url = st.secrets['DATABASE_URL']
    return create_engine(database_url, pool_pre_ping=True)
```

As tabelas são consultadas com SQL:

```python
estudos = pd.read_sql_query(
    'SELECT * FROM estudos_igs ORDER BY id', engine)

concedidas = pd.read_sql_query(
    'SELECT * FROM igs_concedidas ORDER BY id', engine)
```

O uso de `pool_pre_ping=True` ajuda a detectar conexões encerradas antes de reutilizá-las.

## 13. Transformação dos dados na aplicação

Após a consulta SQL, a aplicação:

1. valida as colunas obrigatórias;
2. remove linhas inválidas;
3. extrai latitude e longitude;
4. classifica categorias amplas;
5. classifica modalidades `IP`, `DO` ou `Potencial`;
6. normaliza os territórios;
7. calcula as chaves de estudo;
8. agrupa os ativos;
9. seleciona a linha principal com maior completude;
10. monta a lista de estudos únicos de cada ativo.

## 14. Indicadores apresentados

A dashboard apresenta, entre outros:

- potenciais identificados;
- potenciais com notoriedade;
- estudos únicos trabalhados;
- ativos com múltiplos estudos;
- cobertura dos 27 territórios;
- potenciais para IP;
- potenciais para DO;
- IGs concedidas;
- ranking dos ativos com maior número de estudos.

## 15. Mapa territorial

O mapa utiliza:

- Folium;
- OpenStreetMap como mapa base;
- GeoJSON dos Territórios de Identidade;
- coordenadas dos ativos;
- cores por categoria;
- destaque para ativos com maior quantidade de estudos.

A camada territorial é carregada pelo arquivo `territorios_ba.json`, evitando depender de uma nova consulta ao serviço geográfico a cada execução.

## 16. Execução local do Streamlit

Com o banco acessível e `DATABASE_URL` configurada:

```powershell
py -m streamlit run app_mapa_bahia.py
```

A aplicação normalmente fica disponível em:

```text
http://localhost:8501
```

Para parar o servidor:

```text
Ctrl + C
```

## 17. Publicação no GitHub

O repositório principal é:

```text
https://github.com/Lima990/Banco_de_Dados_IG_Bahia
```

O arquivo principal publicado está em:

```text
DASHBOARD/app_mapa_bahia.py
```

Os arquivos necessários para o deploy estão na mesma pasta `DASHBOARD`.

Nunca publicar:

- senhas;
- `DATABASE_URL` preenchida;
- tokens;
- arquivos `.env`;
- caches Python;
- credenciais do Supabase.

## 18. Configuração no Streamlit Cloud

No aplicativo principal do Streamlit Cloud:

1. abrir **App settings**;
2. acessar **General**;
3. configurar:

```text
Repository: Lima990/Banco_de_Dados_IG_Bahia
Branch: main
Main file path: DASHBOARD/app_mapa_bahia.py
```

Em **Secrets**, informar:

```toml
DATABASE_URL = "postgresql+psycopg://usuario:senha@servidor:5432/banco?sslmode=require"
```

Depois:

1. clicar em **Save changes**;
2. aguardar a atualização;
3. reiniciar o aplicativo;
4. verificar os logs de execução.

A conexão não pode usar `localhost`, porque no Streamlit Cloud `localhost` representa o servidor da nuvem, e não o computador local.

## 19. Atualização dos dados

Para atualizar a base:

1. editar a planilha original;
2. salvar uma cópia atualizada;
3. executar o importador apontando para o novo arquivo;
4. verificar a mensagem de carga concluída;
5. atualizar ou reiniciar o Streamlit Cloud.

Comando:

```powershell
py importar_excel_postgres.py base_de_dados_IGs.xlsx
```

A dashboard consulta o banco em cada carregamento de dados. Portanto, não é necessário alterar o código para atualizar os registros.

## 20. Verificações após a carga

Verificar a quantidade de linhas diretamente no PostgreSQL:

```sql
SELECT COUNT(*) AS linhas_estudos FROM estudos_igs;
SELECT COUNT(*) AS linhas_igs_concedidas FROM igs_concedidas;
SELECT * FROM carga_dados ORDER BY carregado_em DESC LIMIT 5;
```

Verificar estudos únicos:

```sql
SELECT COUNT(DISTINCT estudo_key) AS estudos_unicos
FROM estudos_igs
WHERE estudo_key IS NOT NULL;
```

Verificar ativos com múltiplos estudos:

```sql
SELECT chave_agrupamento, COUNT(DISTINCT estudo_key) AS quantidade_estudos
FROM estudos_igs
WHERE estudo_key IS NOT NULL
GROUP BY chave_agrupamento
HAVING COUNT(DISTINCT estudo_key) > 1
ORDER BY quantidade_estudos DESC;
```

## 21. Segurança

A senha do banco nunca deve ser inserida no código-fonte ou enviada ao GitHub.

Boas práticas:

- usar Secrets no Streamlit Cloud;
- usar variáveis de ambiente localmente;
- redefinir senhas que tenham sido expostas;
- conceder apenas os acessos necessários;
- utilizar `sslmode=require` em conexões hospedadas;
- não compartilhar a URI completa de conexão;
- manter o banco com backups quando possível.

## 22. Manutenção futura recomendada

A carga atual substitui completamente as duas tabelas operacionais. Para um ambiente de produção mais robusto, recomenda-se evoluir para:

- carga incremental;
- `UPSERT` por identificador estável;
- tabelas de histórico;
- validação automática dos dados;
- testes de qualidade antes da publicação;
- backup automático;
- controle de versões da base;
- migrações com ferramentas como Alembic;
- separação entre tabelas de ativos e estudos.

## 23. Fluxo resumido de operação

```text
Atualizar Excel
      |
      v
Executar importar_excel_postgres.py
      |
      v
PostgreSQL/Supabase atualizado
      |
      v
Streamlit consulta as tabelas
      |
      v
Dashboard online atualizada
```

## 24. Resultado final

Com essa arquitetura:

- o dashboard deixa de depender da leitura direta do Excel em produção;
- os dados ficam centralizados em PostgreSQL;
- a aplicação pode ser publicada no Streamlit Cloud;
- filtros e indicadores consultam uma fonte única;
- o histórico de cargas pode ser auditado;
- a atualização dos dados ocorre sem alterar o código da dashboard.
